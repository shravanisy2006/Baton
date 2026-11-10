"""After the demo has been analysed once with the real Gemini key, save its AI responses to
seed/eventapp/llm_cache.json so every fresh deployment can serve the demo without using quota.

Run from the backend folder:   python scripts/export_demo_cache.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import LLMCache  # noqa: E402

out = Path(__file__).resolve().parent.parent / "seed" / "eventapp" / "llm_cache.json"
with SessionLocal() as db:
    rows = [r for r in db.query(LLMCache).all() if r.model.startswith("gemini:")]
data = [{"key": r.key, "task": r.task, "model": r.model, "response": r.response} for r in rows]
out.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"Saved {len(data)} cached Gemini responses to {out}")
