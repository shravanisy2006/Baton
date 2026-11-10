"""Exports with one record per message or item: chat logs and JSON.

- Chat text exports (WhatsApp Android/iOS and "[2026-10-28 18:04] Name: text" style) become one evidence
  unit per message, with the sender as author and the message time as timestamp.
- JSON exports: GitHub issues/PRs (REST API or `gh issue list --json`), Slack channel exports,
  Discord exports (DiscordChatExporter), or any list of records.
"""
import json
import re
from datetime import datetime, timezone

from .parsers import MIN_UNIT_CHARS, ParsedSource, ParseError, Unit

MAX_RECORDS = 2000

_CHAT_PATTERNS = [
    # WhatsApp Android: 28/10/2026, 18:04 - Priya Nair: message
    re.compile(r"^(?P<d>\d{1,2}/\d{1,2}/\d{2,4}),? (?P<t>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?) - (?P<who>[^:]{1,60}): (?P<msg>.*)$"),
    # WhatsApp iOS: [28/10/26, 18:04:12] Priya Nair: message
    re.compile(r"^\[(?P<d>\d{1,2}/\d{1,2}/\d{2,4}),? (?P<t>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\] (?P<who>[^:]{1,60}): (?P<msg>.*)$"),
    # ISO style: [2026-10-28 18:04] Priya: message   or   2026-10-28 18:04 Priya: message
    re.compile(r"^\[?(?P<d>\d{4}-\d{2}-\d{2})[ T](?P<t>\d{1,2}:\d{2}(?::\d{2})?)\]? (?P<who>[^:]{1,60}): (?P<msg>.*)$"),
]


def _iso(d: str, t: str) -> str | None:
    t = t.strip().upper()
    try:
        if "-" in d:
            day = datetime.strptime(d, "%Y-%m-%d")
        else:
            a, b, y = d.split("/")
            y = int(y) + (2000 if len(y) == 2 else 0)
            a, b = int(a), int(b)
            dd, mm = (b, a) if b > 12 else (a, b)  # day/month by default; month/day if it can't be a month
            day = datetime(y, mm, dd)
        clock = datetime.strptime(t.replace(" ", ""), "%I:%M%p" if t.endswith("M") else "%H:%M:%S" if t.count(":") == 2 else "%H:%M")
        return f"{day:%Y-%m-%d} {clock:%H:%M}"
    except ValueError:
        return None


def looks_like_chat(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    hits = sum(1 for ln in lines if any(p.match(ln.strip()) for p in _CHAT_PATTERNS))
    return hits >= 3 and hits >= 0.5 * len(lines)


def parse_chat(text: str) -> ParsedSource:
    out = ParsedSource()
    current: dict | None = None
    n = 0

    def flush():
        nonlocal current, n
        if current and len(current["msg"].strip()) >= MIN_UNIT_CHARS and "<Media omitted>" not in current["msg"]:
            n += 1
            out.units.append(Unit(kind="chat_message", text=current["msg"].strip()[:1500], author=current["who"],
                                  occurred_at=current["at"], location={"message": n, "time": current["at"]}))
        elif current:
            out.skipped.append(f"short message from {current['who']}")
        current = None

    for raw in text.splitlines():
        line = raw.rstrip()
        m = next((p.match(line.strip()) for p in _CHAT_PATTERNS if p.match(line.strip())), None)
        if m:
            flush()
            current = {"who": m.group("who").strip()[:160], "msg": m.group("msg"), "at": _iso(m.group("d"), m.group("t"))}
        elif current and line.strip():
            current["msg"] += " " + line.strip()  # continuation of a multi-line message
    flush()
    return out


# ---------- JSON ----------

def _get(obj: dict, *paths: str):
    for path in paths:
        cur = obj
        for part in path.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return None


def _date(v) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and re.fullmatch(r"\d{9,11}(\.\d+)?", v)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    s = str(v)
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", s)
    return (m.group(1) + (f" {m.group(2)}" if m.group(2) else "")) if m else None


def _records(data) -> tuple[str, list]:
    if isinstance(data, dict):
        if isinstance(data.get("messages"), list):
            return "discord", data["messages"]
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return "generic", v
        return "generic", [data]
    if isinstance(data, list):
        return "list", data
    raise ParseError("JSON must be a list of records or an object containing one.")


def _issue_units(rec: dict) -> list[Unit]:
    number = rec.get("number")
    is_pr = "pull_request" in rec or "headRefName" in rec or rec.get("isPullRequest")
    state = str(rec.get("state", "")).lower() or "unknown"
    if str(rec.get("state_reason") or rec.get("stateReason") or "").lower() == "reopened":
        state = "reopened"
    body = (rec.get("body") or "").strip()
    url = rec.get("html_url") or rec.get("url")
    label = "Pull request" if is_pr else "Issue"
    units = [Unit(kind="github_pr" if is_pr else "github_issue",
                  text=(f"{label} #{number} [{state}]: {rec.get('title', '')}" + (f" — {body}" if body else ""))[:1500],
                  author=_get(rec, "user.login", "author.login", "author.name", "author"),
                  occurred_at=_date(_get(rec, "updated_at", "updatedAt", "created_at", "createdAt")),
                  location={"number": number, "url": url})]
    comments = rec.get("comments")
    if isinstance(comments, dict):
        comments = comments.get("nodes") or comments.get("edges") or []
    for c in comments if isinstance(comments, list) else []:
        if not isinstance(c, dict):
            continue
        c = c.get("node", c)
        cbody = (c.get("body") or "").strip()
        if len(cbody) >= MIN_UNIT_CHARS:
            units.append(Unit(kind="github_comment", text=f"Comment on #{number}: {cbody}"[:1500],
                              author=_get(c, "user.login", "author.login", "author"),
                              occurred_at=_date(_get(c, "created_at", "createdAt")),
                              location={"number": number, "url": c.get("html_url") or c.get("url") or url}))
    return units


def parse_json(data: bytes) -> ParsedSource:
    try:
        parsed = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ParseError(f"Not valid JSON: {e}") from e
    kind, records = _records(parsed)
    out = ParsedSource()
    for i, rec in enumerate(records[:MAX_RECORDS], start=1):
        if not isinstance(rec, dict):
            out.skipped.append(f"record {i}: not an object")
            continue
        if "number" in rec and "title" in rec:  # GitHub issue / PR
            out.units += _issue_units(rec)
            continue
        if kind == "discord" or ("content" in rec and isinstance(rec.get("author"), dict)):
            text = (rec.get("content") or "").strip()
            if len(text) >= MIN_UNIT_CHARS:
                out.units.append(Unit(kind="chat_message", text=text[:1500],
                                      author=_get(rec, "author.nickname", "author.name"),
                                      occurred_at=_date(rec.get("timestamp")), location={"message": i}))
            continue
        if "text" in rec and ("ts" in rec or rec.get("type") == "message"):  # Slack export
            text = (rec.get("text") or "").strip()
            if len(text) >= MIN_UNIT_CHARS:
                out.units.append(Unit(kind="chat_message", text=text[:1500],
                                      author=_get(rec, "user_profile.real_name", "user_name", "user"),
                                      occurred_at=_date(rec.get("ts")), location={"message": i}))
            continue
        # Any other record: its simple fields, "key: value | ...".
        pairs = [f"{k}: {v}" for k, v in rec.items() if isinstance(v, (str, int, float, bool)) and str(v).strip()]
        text = " | ".join(pairs)
        if len(text) < MIN_UNIT_CHARS:
            out.skipped.append(f"record {i}: empty")
            continue
        author = next((str(rec[k]) for k in ("author", "owner", "assignee", "user", "created_by") if isinstance(rec.get(k), str)), None)
        when = next((_date(rec[k]) for k in rec if re.search(r"date|time|created|updated", k, re.I) and _date(rec[k])), None)
        out.units.append(Unit(kind="json_record", text=text[:1500], author=author, occurred_at=when, location={"record": i}))
    if len(records) > MAX_RECORDS:
        out.skipped.append(f"only the first {MAX_RECORDS} records were read")
    return out
