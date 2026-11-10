"""Remove secrets and phone numbers before text is stored or sent to the AI."""
import re

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("phone", re.compile(r"(?<![\w-])(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w-])")),
    ("phone", re.compile(r"(?<![\w-])\+\d{1,3}[\s-]\d{2,4}[\s-]\d{3,4}[\s-]\d{3,4}(?![\w-])")),
]
ASSIGNMENT = re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|token)\b(\s*[:=]\s*)(\S{6,})")


def redact(text: str) -> tuple[str, int]:
    count = 0
    for label, pattern in PATTERNS:
        text, n = pattern.subn(f"[{label} redacted]", text)
        count += n

    def _assign(m: re.Match) -> str:
        nonlocal count
        if "redacted]" in m.group(3):
            return m.group(0)
        count += 1
        return f"{m.group(1)}{m.group(2)}[secret redacted]"

    text = ASSIGNMENT.sub(_assign, text)
    return text, count
