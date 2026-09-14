"""Redis-backed session history and metadata storage."""
import json
import time
from typing import Any, List, Optional

Message = dict[str, Any]
Metadata = dict[str, Any]


class SessionStore:
    def load(self, user_id: str, session_id: str) -> List[Message]:
        raise NotImplementedError

    def save(self, user_id: str, session_id: str, messages: List[Message], ttl: int = 0,
             title: Optional[str] = None) -> None:
        raise NotImplementedError

    def list_sessions(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Metadata]:
        raise NotImplementedError

    def get_metadata(self, user_id: str, session_id: str) -> Optional[Metadata]:
        raise NotImplementedError

    def delete(self, user_id: str, session_id: str) -> None:
        raise NotImplementedError

    def clear(self, user_id: str, session_id: str) -> None:
        raise NotImplementedError


class RedisSessionStore(SessionStore):
    def __init__(self, url: str, prefix: str = "harness:session:") -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Redis storage requires redis package") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.prefix = prefix

    def _key(self, user_id: str, session_id: str) -> str:
        return f"{self.prefix}{user_id}:{session_id}"

    def _meta_key(self, user_id: str, session_id: str) -> str:
        return f"{self._key(user_id, session_id)}:meta"

    def _index_key(self, user_id: str) -> str:
        return f"{self.prefix}{user_id}:index"

    def load(self, user_id: str, session_id: str) -> List[Message]:
        raw = self.client.get(self._key(user_id, session_id))
        if not isinstance(raw, str) or not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.delete(user_id, session_id)
            return []
        return data if isinstance(data, list) else []

    def save(self, user_id: str, session_id: str, messages: List[Message], ttl: int = 0,
             title: Optional[str] = None) -> None:
        now = time.time()
        key = self._key(user_id, session_id)
        meta_key = self._meta_key(user_id, session_id)
        payload = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
        existing = self.get_metadata(user_id, session_id) or {}
        if not title:
            title = existing.get("title") or self._title(messages)
        metadata = {
            "session_id": session_id,
            "title": title,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "message_count": len(messages),
        }
        pipe = self.client.pipeline()
        if ttl > 0:
            pipe.setex(key, ttl, payload)
            pipe.setex(meta_key, ttl, json.dumps(metadata, ensure_ascii=False))
        else:
            pipe.set(key, payload)
            pipe.set(meta_key, json.dumps(metadata, ensure_ascii=False))
        pipe.zadd(self._index_key(user_id), {session_id: now})
        pipe.execute()

    def list_sessions(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Metadata]:
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)
        ids_result = self.client.zrevrange(self._index_key(user_id), offset, offset + limit - 1)
        ids = list(ids_result) if isinstance(ids_result, (list, tuple)) else []
        result: List[Metadata] = []
        for session_id in ids:
            metadata = self.get_metadata(user_id, session_id)
            if metadata is not None and self.client.exists(self._key(user_id, session_id)):
                result.append(metadata)
        return result

    def get_metadata(self, user_id: str, session_id: str) -> Optional[Metadata]:
        raw = self.client.get(self._meta_key(user_id, session_id))
        if not isinstance(raw, str) or not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def delete(self, user_id: str, session_id: str) -> None:
        pipe = self.client.pipeline()
        pipe.delete(self._key(user_id, session_id))
        pipe.delete(self._meta_key(user_id, session_id))
        pipe.zrem(self._index_key(user_id), session_id)
        pipe.execute()

    def clear(self, user_id: str, session_id: str) -> None:
        self.save(user_id, session_id, [], ttl=0)

    def acquire_lock(self, user_id: str, session_id: str, timeout: int = 5) -> Optional[object]:
        lock = self.client.lock(
            f"{self._key(user_id, session_id)}:lock",
            timeout=max(timeout, 30),
            blocking_timeout=timeout,
        )
        return lock if lock.acquire(blocking=True) else None

    def release_lock(self, lock: object) -> None:
        release = getattr(lock, "release", None)
        if callable(release):
            try:
                release()
            except Exception:
                pass

    def ping(self) -> bool:
        return bool(self.client.ping())

    @staticmethod
    def _title(messages: List[Message]) -> str:
        for message in messages:
            if message.get("role") == "user" and message.get("content"):
                title = " ".join(str(message["content"]).split())
                return title[:80] + ("..." if len(title) > 80 else "")
        return "新会话"
