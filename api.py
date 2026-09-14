"""HTTP API entrypoint for production integrations."""
import json
import queue
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi.responses import StreamingResponse

from fastapi import Depends, FastAPI, Header, HTTPException, Response
try:
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - API extras are optional for CLI usage
    raise RuntimeError("HTTP API requires the api dependency group; run pip install -e .") from exc

from .config import settings
from .core.agent import Agent
from .core.hooks import make_default_hooks
from .core.repository_analysis import ANALYSIS_ROLES, RepositoryAnalyzer
from .core.session_store import RedisSessionStore
from .core.registry import registry
from .core.skills import load_skills_for
from .tools import load_all

load_all()
app = FastAPI(title="Agent Harness", version="0.2.0")
_session_store = RedisSessionStore(settings.REDIS_URL, settings.REDIS_PREFIX)
_rate_state: Dict[str, tuple[float, int]] = {}
_rate_guard = threading.Lock()
_metrics = {"requests_total": 0, "errors_total": 0, "stream_requests_total": 0}
_request_slots = threading.BoundedSemaphore(max(1, settings.MAX_CONCURRENT_REQUESTS))


def rate_limit(client_key: str) -> None:
    limit = settings.RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return
    now = time.monotonic()
    with _rate_guard:
        start, count = _rate_state.get(client_key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        if count >= limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        _rate_state[client_key] = (start, count + 1)


_session_locks: Dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()


def session_lock(session_id: str) -> threading.Lock:
    with _session_locks_guard:
        return _session_locks.setdefault(session_id, threading.Lock())


# Redis lock provides cross-process protection; this map is retained for compatibility.


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., min_length=1, max_length=100)
    max_iterations: Optional[int] = Field(default=None, ge=1, le=100)
    session_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    stream: bool = False

    @classmethod
    def validate_messages(cls, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if sum(len(str(message.get("content", ""))) for message in messages) > 200_000:
            raise ValueError("messages are too large")
        if not messages:
            raise ValueError("messages must not be empty")
        for message in messages:
            if message.get("role") != "user":
                raise ValueError("only user messages are accepted")
            if not isinstance(message.get("content"), str) or not message["content"].strip():
                raise ValueError("user content must be a non-empty string")
        return messages

    def model_post_init(self, __context: object) -> None:
        self.messages = self.validate_messages(self.messages)


class ChatResponse(BaseModel):
    content: str
    messages: List[Dict[str, Any]]
    stats: str


class RepositoryAnalysisRequest(BaseModel):
    repository: str = Field(default=".", min_length=1, max_length=500)
    focus: Optional[List[str]] = None
    max_workers: int = Field(default=4, ge=1, le=4)

    def model_post_init(self, __context: object) -> None:
        if self.focus is not None and (not self.focus or any(role not in ANALYSIS_ROLES for role in self.focus)):
            raise ValueError(f"focus must contain only: {', '.join(ANALYSIS_ROLES)}")


class RepositoryAnalysisResponse(BaseModel):
    analysis_id: str
    repository: str
    summary: str
    findings: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    elapsed_seconds: float
    status: str


class SessionMetadata(BaseModel):
    session_id: str
    title: str
    created_at: float
    updated_at: float
    message_count: int


class SessionListResponse(BaseModel):
    items: List[SessionMetadata]
    limit: int
    offset: int


def validate_user_id(user_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", user_id):
        raise HTTPException(status_code=400, detail="invalid user_id")
    return user_id


def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected and settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid authorization")


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> StreamingResponse:
    body = "\n".join(
        f"harness_{name} {value}" for name, value in _metrics.items()
    ) + "\n"
    return StreamingResponse(iter([body]), media_type="text/plain; version=0.0.4")


@app.get("/readyz")
def readyz() -> Dict[str, str]:
    if not settings.API_KEY:
        raise HTTPException(status_code=503, detail="LLM API key is not configured")
    try:
        _session_store.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc
    return {"status": "ready"}


Event = dict[str, object]
EventQueue = queue.Queue[Event | None]


def _run_chat(request: ChatRequest, events: Optional[EventQueue] = None,
              request_id: Optional[str] = None, user_id: str = "anonymous") -> ChatResponse:
    messages = [dict(message) for message in request.messages]
    user_id = validate_user_id(user_id)
    if any(message.get("role") == "system" for message in messages):
        raise HTTPException(status_code=400, detail="system messages are managed by the harness")
    if request.session_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", request.session_id):
        raise HTTPException(status_code=400, detail="invalid session_id")
    rate_limit(request.session_id or "global")
    if not _request_slots.acquire(timeout=5):
        raise HTTPException(status_code=429, detail="too many concurrent requests")
    _metrics["requests_total"] += 1
    if request.session_id:
        try:
            lock = _session_store.acquire_lock(user_id, request.session_id, timeout=5)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Redis is unavailable") from exc
        if lock is None:
            raise HTTPException(status_code=409, detail="session is busy")
        previous = _session_store.load(user_id, request.session_id)
        messages = previous + messages
    else:
        lock = None

    agent = Agent(
        registry=registry,
        hooks=make_default_hooks(settings),
        settings=settings,
        skill_loader=lambda query: load_skills_for(query, settings.SKILLS_DIR),
        on_text=lambda text: events.put({"event": "text", "data": text}, timeout=5) if events else None,
        on_tool=lambda name, output: events.put({"event": "tool", "data": {"name": name, "output": output}}, timeout=5) if events else None,
    )
    agent.request_id = request_id
    try:
        content = agent.run(messages, max_iterations=request.max_iterations)
        if request.session_id:
            _session_store.save(user_id, request.session_id, messages, ttl=settings.SESSION_TTL)
        if events:
            events.put({"event": "done", "data": {"content": content, "stats": agent.stats.summary()}})
        return ChatResponse(content=content, messages=messages, stats=agent.stats.summary())
    except Exception as exc:
        _metrics["errors_total"] += 1
        if events:
            events.put({"event": "error", "data": "LLM request failed"})
        raise HTTPException(status_code=502, detail="LLM request failed") from exc
    finally:
        if lock is not None:
            _session_store.release_lock(lock)
        _request_slots.release()


@app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_auth)])
def chat(request: ChatRequest, response: Response, x_user_id: Optional[str] = Header(default=None)) -> ChatResponse:
    request_id = str(uuid.uuid4())
    result = _run_chat(request, request_id=request_id, user_id=x_user_id or "anonymous")
    response.headers["X-Request-ID"] = request_id
    return result


@app.post("/v1/repository/analyze", response_model=RepositoryAnalysisResponse,
          dependencies=[Depends(require_auth)])
def analyze_repository(request: RepositoryAnalysisRequest,
                       x_user_id: Optional[str] = Header(default=None)) -> RepositoryAnalysisResponse:
    validate_user_id(x_user_id or "anonymous")
    try:
        analyzer_agent = Agent(
            registry=registry,
            hooks=make_default_hooks(settings),
            settings=settings,
            skill_loader=lambda query: load_skills_for(query, settings.SKILLS_DIR),
        )
        report = RepositoryAnalyzer(analyzer_agent, max_workers=request.max_workers).analyze(
            request.repository, request.focus
        )
        return RepositoryAnalysisResponse(**report.as_dict())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _metrics["errors_total"] += 1
        raise HTTPException(status_code=400, detail="repository analysis failed") from exc


@app.post("/v1/repository/analyze/markdown", dependencies=[Depends(require_auth)])
def analyze_repository_markdown(request: RepositoryAnalysisRequest,
                                x_user_id: Optional[str] = Header(default=None)) -> Response:
    validate_user_id(x_user_id or "anonymous")
    try:
        analyzer_agent = Agent(
            registry=registry,
            hooks=make_default_hooks(settings),
            settings=settings,
            skill_loader=lambda query: load_skills_for(query, settings.SKILLS_DIR),
        )
        report = RepositoryAnalyzer(analyzer_agent, max_workers=request.max_workers).analyze(
            request.repository, request.focus
        )
        return Response(content=report.to_markdown(), media_type="text/markdown")
    except Exception as exc:
        _metrics["errors_total"] += 1
        raise HTTPException(status_code=400, detail="repository analysis failed") from exc


def chat_stream(request: ChatRequest, x_user_id: Optional[str] = Header(default=None)) -> StreamingResponse:
    _metrics["stream_requests_total"] += 1
    request_id = str(uuid.uuid4())
    events: EventQueue = queue.Queue(maxsize=1000)

    def worker() -> None:
        try:
            _run_chat(request, events, request_id=request_id, user_id=x_user_id or "anonymous")
        except Exception:
            pass
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def generate():
        while True:
            event = events.get()
            if event is None:
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Request-ID": request_id},
    )


@app.get("/v1/sessions", response_model=SessionListResponse, dependencies=[Depends(require_auth)])
def list_sessions(limit: int = 50, offset: int = 0,
                  x_user_id: Optional[str] = Header(default=None)) -> SessionListResponse:
    user_id = validate_user_id(x_user_id or "anonymous")
    try:
        items = _session_store.list_sessions(user_id, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc
    metadata_items = [SessionMetadata(**item) for item in items]
    return SessionListResponse(items=metadata_items, limit=min(max(limit, 1), 100), offset=max(offset, 0))


@app.get("/v1/sessions/{session_id}", response_model=SessionMetadata,
         dependencies=[Depends(require_auth)])
def get_session(session_id: str, x_user_id: Optional[str] = Header(default=None)) -> SessionMetadata:
    user_id = validate_user_id(x_user_id or "anonymous")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id):
        raise HTTPException(status_code=400, detail="invalid session_id")
    metadata = _session_store.get_metadata(user_id, session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionMetadata(**metadata)


@app.delete("/v1/sessions/{session_id}", status_code=204,
            dependencies=[Depends(require_auth)])
def delete_session(session_id: str, x_user_id: Optional[str] = Header(default=None)) -> None:
    user_id = validate_user_id(x_user_id or "anonymous")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id):
        raise HTTPException(status_code=400, detail="invalid session_id")
    _session_store.delete(user_id, session_id)


@app.post("/v1/sessions/{session_id}/clear", response_model=SessionMetadata,
          dependencies=[Depends(require_auth)])
def clear_session(session_id: str, x_user_id: Optional[str] = Header(default=None)) -> SessionMetadata:
    user_id = validate_user_id(x_user_id or "anonymous")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id):
        raise HTTPException(status_code=400, detail="invalid session_id")
    if _session_store.get_metadata(user_id, session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    _session_store.clear(user_id, session_id)
    metadata = _session_store.get_metadata(user_id, session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionMetadata(**metadata)
