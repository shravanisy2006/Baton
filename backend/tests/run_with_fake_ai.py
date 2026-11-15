"""DEV/TEST ONLY: run the API with the scripted fake AI from conftest, for UI testing without a Gemini key.
Never use for the real deployment.   python tests/run_with_fake_ai.py"""

import os
import sys
from pathlib import Path

_db = Path(__file__).resolve().parent.parent / "dev-fake.db"
if os.environ.get("BATON_FRESH_DB") == "1" and _db.exists():
    _db.unlink()  # browser tests start from an empty database
os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(_db))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

_keep = {k: os.environ.get(k) for k in ("DATABASE_URL", "LOCAL_STORAGE_DIR", "GEMINI_API_KEY")}
from conftest import fake_llm  # noqa: E402  (conftest sets test-only environment; undo that below)

for k, v in _keep.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v
for k in ("BATON_SKIP_DEMO_CACHE", "BATON_JOBS_INLINE", "BATON_RUN_WORKER", "APP_URL"):
    os.environ.pop(k, None)

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()  # settings were first read with the test environment
from app.llm.provider import FakeProvider, set_providers_for_tests  # noqa: E402
from app.main import app  # noqa: E402

set_providers_for_tests([FakeProvider(fake_llm)])
uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
