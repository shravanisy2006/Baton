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
        # Storage (optional Supabase Storage; falls back to local disk)
        self.supabase_url: str = env("SUPABASE_URL", "").rstrip("/")
        self.supabase_service_key: str = env("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase_bucket: str = env("SUPABASE_BUCKET", "sources")
        self.supabase_jwt_secret: str = env("SUPABASE_JWT_SECRET", "")
        self.local_storage_dir: Path = Path(env("LOCAL_STORAGE_DIR", str(BACKEND_DIR / "storage")))
        # GitHub
        self.github_token: str = env("GITHUB_TOKEN", "")
        # Limits
        self.max_upload_mb: int = int(env("MAX_UPLOAD_MB", "10"))
        self.github_max_items: int = int(env("GITHUB_MAX_ITEMS", "60"))

    @property
    def ai_configured(self) -> bool:
        return self.ai_provider == "gemini" and bool(self.gemini_api_key)

    @property
    def supabase_storage_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
