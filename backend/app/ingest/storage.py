"""Raw file storage: private Supabase Storage bucket when configured, otherwise local disk."""
import logging
import re

import httpx

from ..config import get_settings

log = logging.getLogger("baton.storage")


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]


def save_raw(project_id: str, source_id: str, filename: str, data: bytes) -> str:
    s = get_settings()
    path = f"{project_id}/{source_id}/{_safe(filename)}"
    if s.supabase_storage_enabled:
        url = f"{s.supabase_url}/storage/v1/object/{s.supabase_bucket}/{path}"
        r = httpx.post(url, content=data, timeout=30, headers={
            "Authorization": f"Bearer {s.supabase_service_key}",
            "x-upsert": "true",
            "Content-Type": "application/octet-stream",
        })
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase Storage upload failed ({r.status_code}): {r.text[:200]}")
        return f"supabase://{s.supabase_bucket}/{path}"
    target = s.local_storage_dir / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return f"local://{path}"
