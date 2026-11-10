"""Turn uploaded files into small evidence units.

Each parser returns ParsedSource(units=[...], meta). A unit is one addressable piece of evidence:
a paragraph, a bullet, a table row, a CSV row. Small units make quotes precise and easy to verify.
"""
import io
import re
from dataclasses import dataclass, field

import pymupdf as fitz  # PyMuPDF
import pandas as pd
from docx import Document

MIN_UNIT_CHARS = 12
MAX_UNIT_CHARS = 1500

META_RE = re.compile(r"^\s*(?:\*\*)?(date|author|written by|attendees|owner)(?:\*\*)?\s*:\s*(.+?)\s*$", re.I)
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
BULLET_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")


@dataclass
class Unit:
    kind: str
    text: str
    location: dict
    author: str | None = None
    occurred_at: str | None = None


@dataclass
class ParsedSource:
    units: list[Unit] = field(default_factory=list)
    author: str | None = None
    occurred_at: str | None = None
    skipped: list[str] = field(default_factory=list)
    unreadable: bool = False


class ParseError(Exception):
    pass


SUPPORTED = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md", ".csv": "csv",
             ".json": "json"}


def kind_for(filename: str) -> str | None:
    name = filename.lower()
    for ext, kind in SUPPORTED.items():
        if name.endswith(ext):
            return kind
    return None


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace(" ", " ")).strip()


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_UNIT_CHARS:
        return [text]
    parts, cur = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if cur and len(cur) + len(sentence) > MAX_UNIT_CHARS:
            parts.append(cur.strip())
            cur = ""
        cur += sentence + " "
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _date_from_name(filename: str) -> str | None:
    m = DATE_RE.search(filename)
    return m.group(1) if m else None


def _parse_lines(lines: list[str], kind: str, base_loc: dict, out: ParsedSource) -> None:
    """Shared logic for text-like content: metadata lines, headings, paragraphs and bullets.

    "Date:" / "Author:" lines at the top describe the whole file; the same lines right under a
    heading describe that section only (e.g. one GitHub issue inside an export).
    """
    section = None
    headings = 0
    sec_author: str | None = None
    sec_date: str | None = None
    para: list[str] = []
    para_no = 0

    def flush():
        nonlocal para, para_no
        if not para:
            return
        text = _clean(" ".join(para))
        para = []
        if len(text) < MIN_UNIT_CHARS:
            if text:
                out.skipped.append(f"too short: {text[:40]!r}")
            return
        para_no += 1
        for i, piece in enumerate(_split_long(text)):
            loc = dict(base_loc, paragraph=para_no)
            if section:
                loc["section"] = section
            if i:
                loc["part"] = i + 1
            out.units.append(Unit(kind=kind, text=piece, location=loc, author=sec_author, occurred_at=sec_date))

    for raw in lines:
        line = raw.rstrip()
        meta = META_RE.match(line)
        if meta and not para:
            key, value = meta.group(1).lower(), meta.group(2).strip()
            d = DATE_RE.search(value)
            at_top = headings <= 1 and not out.units
            if key == "date":
                if at_top:
                    out.occurred_at = d.group(1) if d else value[:40]
                else:
                    sec_date = d.group(1) if d else value[:40]
            elif key in ("author", "written by"):
                if at_top:
                    out.author = value[:160]
                else:
                    sec_author = value[:160]
            continue
        heading = HEADING_RE.match(line)
        if heading:
            flush()
            section = _clean(heading.group(1))[:120] or None
            headings += 1
            sec_author = sec_date = None
            continue
        if not line.strip():
            flush()
            continue
        if BULLET_RE.match(line):
            flush()
            para.append(BULLET_RE.sub("", line))
            flush()
            continue
        para.append(line)
    flush()


def parse_text(data: bytes, filename: str, kind: str) -> ParsedSource:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    out = ParsedSource(occurred_at=_date_from_name(filename))
    _parse_lines(text.splitlines(), "paragraph", {}, out)
    return out


def parse_pdf(data: bytes, filename: str) -> ParsedSource:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Could not open PDF: {e}") from e
    out = ParsedSource(occurred_at=_date_from_name(filename))
    meta_author = (doc.metadata or {}).get("author")
    if meta_author:
        out.author = meta_author[:160]
    empty_pages = 0
    for page_no, page in enumerate(doc, start=1):
        blocks = [b[4] for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        if not blocks:
            empty_pages += 1
            out.skipped.append(f"page {page_no}: no readable text (scanned image?)")
            continue
        lines: list[str] = []
        for i, block in enumerate(blocks):
            text = " ".join(block.split())
            # A short first block on page 1 is the document title, not evidence.
            if page_no == 1 and i == 0 and len(text) < 80 and not text.endswith("."):
                lines += ["# " + text, ""]
            else:
                lines += [text, ""]
        _parse_lines(lines, "paragraph", {"page": page_no}, out)
    if doc.page_count and empty_pages == doc.page_count:
        out.unreadable = True
    return out


def parse_docx(data: bytes, filename: str) -> ParsedSource:
    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Could not open Word file: {e}") from e
    out = ParsedSource(occurred_at=_date_from_name(filename))
    if doc.core_properties.author:
        out.author = doc.core_properties.author[:160]
    lines: list[str] = []
    for p in doc.paragraphs:
        style = (p.style.name or "").lower() if p.style is not None else ""
        text = p.text
        if style.startswith("heading") or style == "title":
            lines += ["", "# " + text, ""]
        elif "list" in style:
            lines.append("- " + text)
        else:
            lines += [text, ""]
    _parse_lines(lines, "paragraph", {}, out)
    for t_no, table in enumerate(doc.tables, start=1):
        rows = table.rows
        if not rows:
            continue
        header = [c.text.strip() for c in rows[0].cells]
        for r_no, row in enumerate(rows[1:], start=1):
            cells = [c.text.strip() for c in row.cells]
            text = " | ".join(f"{h}: {v}" if h else v for h, v in zip(header, cells) if v)
            if len(text) >= MIN_UNIT_CHARS:
                out.units.append(Unit(kind="table_row", text=text, location={"table": t_no, "row": r_no}))
    return out


DATE_COLS = ("updated", "last updated", "date", "modified", "due", "closed")


def parse_csv(data: bytes, filename: str) -> ParsedSource:
    try:
        df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    except Exception as e:  # noqa: BLE001
        raise ParseError(f"Could not read CSV: {e}") from e
    if df.empty:
        raise ParseError("CSV has a header but no rows.")
    out = ParsedSource(occurred_at=_date_from_name(filename))
    cols = list(df.columns)
    date_col = next((c for c in cols if c.strip().lower() in DATE_COLS), None)
    for i, row in df.iterrows():
        pairs = [f"{c.strip()}: {str(row[c]).strip()}" for c in cols if str(row[c]).strip()]
        text = " | ".join(pairs)
        if len(text) < MIN_UNIT_CHARS:
            out.skipped.append(f"row {i + 1}: empty")
            continue
        occurred = None
        if date_col and str(row[date_col]).strip():
            d = DATE_RE.search(str(row[date_col]))
            occurred = d.group(1) if d else None
        out.units.append(Unit(kind="csv_row", text=text, location={"row": int(i) + 1}, occurred_at=occurred))
    return out


def parse_file(data: bytes, filename: str) -> tuple[str, ParsedSource]:
    kind = kind_for(filename)
    if not kind:
        raise ParseError("Unsupported file type. Use PDF, DOCX, TXT, MD, CSV or JSON.")
    if not data:
        raise ParseError("The file is empty.")
    if kind == "pdf":
        return kind, parse_pdf(data, filename)
    if kind == "docx":
        return kind, parse_docx(data, filename)
    if kind == "csv":
        return kind, parse_csv(data, filename)
    from .structured import looks_like_chat, parse_chat, parse_json

    if kind == "json":
        return kind, parse_json(data)
    if kind == "txt":
        text = data.decode("utf-8-sig", errors="replace")
        if looks_like_chat(text):
            return "chat", parse_chat(text)
    return kind, parse_text(data, filename, kind)
