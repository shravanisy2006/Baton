"""DEV/TEST ONLY: run the API with the scripted fake AI from conftest, for UI testing without a Gemini key.
Never use for the real deployment.   python tests/run_with_fake_ai.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(Path(__file__).resolve().parent.parent / "dev-fake.db"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from app.llm.provider import FakeProvider, set_providers_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from conftest import fake_llm  # noqa: E402

set_providers_for_tests([FakeProvider(fake_llm)])
uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
