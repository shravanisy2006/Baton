"""Check that your Gemini key works and that Baton's strict JSON format is accepted.

Run from the backend folder:   python scripts/check_ai.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.extract.service import SYSTEM, ExtractionResult  # noqa: E402
from app.llm.provider import call_json  # noqa: E402

s = get_settings()
if not s.gemini_api_key:
    sys.exit("GEMINI_API_KEY is empty. Put it in backend/.env first.")
init_db()
prompt = ("Evidence:\n\n[E-1] (source: notes.md | date: 2026-09-15)\n"
          "Decision: keep online payments disabled until the sponsor MoU is signed, because the sponsor asked us to pause.")
try:
    with SessionLocal() as db:
        result, provider = call_json(db, "check", SYSTEM, prompt, ExtractionResult)
except Exception as e:  # noqa: BLE001
    msg = str(e)
    hint = ""
    if "API_KEY_INVALID" in msg or "API key not valid" in msg or "400" in msg:
        hint = "Your GEMINI_API_KEY looks wrong. Copy it again from https://aistudio.google.com/apikey"
    elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        hint = "The free Gemini limit was reached. Wait a minute and try again."
    elif "403" in msg or "PERMISSION_DENIED" in msg:
        hint = "Google refused the key. Check it is an AI Studio key and the Gemini API is enabled for it."
    sys.exit(f"FAILED: {msg[:400]}\n{hint}")
print(f"OK — {provider} returned {len(result.claims)} claim(s):")
for c in result.claims:
    print(f"  [{c.type}] {c.statement}  <- {[(x.evidence_id, x.quote) for x in c.citations]}")
