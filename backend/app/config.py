"""Application settings, read from environment variables (see backend/.env.example)."""

import os
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Minimal .env loader so local runs work without extra packages."""
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def env(key: str, default: str = "") -> str:
    """Read an environment variable; an empty value (e.g. `DATABASE_URL=` in .env) counts as not set."""
    value = os.getenv(key, "").strip()
    return value if value else default


class Settings:
    def __init__(self) -> None:
        self.database_url: str = env("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'baton.db'}")
        self.app_secret: str = env("APP_SECRET", "dev-only-secret-change-me-in-production-please")
        self.cors_origins: list[str] = [
            o.strip() for o in env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
        ]
        # AI
        self.ai_provider: str = env("AI_PROVIDER", "gemini")
        self.gemini_api_key: str = env("GEMINI_API_KEY", "")
        self.gemini_model: str = env("GEMINI_MODEL", "gemini-3.8-flash")
        self.backup_provider: str = env("BACKUP_AI_PROVIDER", "")
        # GitHub
        self.github_token: str = env("GITHUB_TOKEN", "")
        # Email (Resend, https://resend.com). Without these, Baton says plainly that email isn't set up and shows
        # the link to copy instead; it never pretends an email was sent.
        self.resend_api_key: str = env("RESEND_API_KEY", "")
        self.email_from: str = env("EMAIL_FROM", "")  # e.g. "Baton <handover@yourdomain.com>"
        self.app_url: str = env("APP_URL", "http://localhost:5173").rstrip("/")  # the website, for links in emails
        # Background jobs: run in a worker thread inside the API process (default) or in `python -m app.worker`.
        self.run_worker: bool = env("BATON_RUN_WORKER", "1") == "1"
        self.worker_threads: int = int(env("WORKER_THREADS", "2"))
        self.ai_concurrency: int = int(env("AI_CONCURRENCY", "3"))
        # Limits
        self.max_upload_mb: int = int(env("MAX_UPLOAD_MB", "10"))
        self.max_files_per_upload: int = int(env("MAX_FILES_PER_UPLOAD", "10"))
        self.max_sources_per_project: int = int(env("MAX_SOURCES_PER_PROJECT", "200"))
        self.github_max_items: int = int(env("GITHUB_MAX_ITEMS", "60"))

    @property
    def ai_configured(self) -> bool:
        return self.ai_provider == "gemini" and bool(self.gemini_api_key)

    @property
    def email_configured(self) -> bool:
        return bool(self.resend_api_key and self.email_from)

    @property
    def is_production(self) -> bool:
        # Render sets RENDER=true on its servers; BATON_ENV=production marks any other host.
        return os.getenv("RENDER", "").lower() == "true" or os.getenv("BATON_ENV", "").lower() == "production"

    def check(self) -> None:
        """Refuse to start a production server with an unsafe configuration."""
        if self.is_production and (self.app_secret.startswith("dev-only") or len(self.app_secret) < 32):
            raise RuntimeError(
                "APP_SECRET must be set to a long random value (32+ characters) in production. "
                "On Render it is generated automatically by render.yaml."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
