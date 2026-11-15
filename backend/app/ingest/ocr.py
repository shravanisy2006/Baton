"""Scanned PDF pages and images: transcribe them with the AI, then treat the text like any other evidence.

The transcription becomes the evidence text. Every later quote is checked word for word against it, and
each unit is labelled as an AI transcription of a scan (with its page), so a reviewer knows to compare it
with the original if a line matters.
"""
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..llm.provider import AIUnavailable, InvalidAIOutput, call_json
from .parsers import ParsedSource, _parse_lines

SYSTEM = """You transcribe scanned documents, photos of notes, whiteboards and screenshots, exactly as written.
Rules: copy the words exactly (keep spelling, names, numbers and dates); keep line breaks between paragraphs and
list items; do not summarise, translate, correct or add anything; write [illegible] for words you cannot read.
If a page has no readable text, return an empty string for it."""


class PageText(BaseModel):
    page: int
    text: str = Field(default="")


class Transcription(BaseModel):
    pages: list[PageText] = Field(default_factory=list)


def transcribe(db: Session, parsed: ParsedSource, filename: str) -> None:
    """Fill `parsed.units` from its scanned pages. On AI failure, record why in `skipped`."""
    if not parsed.needs_ocr:
        return
    pages = [n for n, _, _ in parsed.needs_ocr]
    prompt = (f"File: {filename}. The images are pages {', '.join(map(str, pages))} in that order. "
              "Return one entry per page with its number and exact text.")
    try:
        result, model = call_json(db, "ocr", SYSTEM, prompt, Transcription,
                                  images=[(b, mime) for _, b, mime in parsed.needs_ocr])
    except (AIUnavailable, InvalidAIOutput) as e:
        for n in pages:
            parsed.skipped.append(f"page {n}: scanned image could not be transcribed right now ({str(e)[:80]}). "
                                  "Upload it again in a minute.")
        parsed.unreadable = not parsed.units
        parsed.needs_ocr = []
        return
    got = {p.page: p.text for p in result.pages}
    for n in pages:
        text = (got.get(n) or "").strip()
        if not text or text.lower() == "[illegible]":
            parsed.skipped.append(f"page {n}: no readable text in the scan")
            continue
        _parse_lines(text.splitlines() + [""], "ocr", {"page": n, "transcribed": "AI transcription of a scan"}, parsed)
    parsed.unreadable = not parsed.units
    parsed.needs_ocr = []
