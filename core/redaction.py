"""Best-effort redaction for logs and tool output."""
import re

_PATTERNS = (
    (re.compile(r"(?i)(sk-[A-Za-z0-9_-]{16,})"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [^-]+ PRIVATE KEY-----[\s\S]*?-----END [^-]+ PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
)


def redact(value: object, max_chars: int = 0) -> str:
    text = str(value)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "...[redacted output truncated]"
    return text
