"""Email delivery through Resend (https://resend.com) over its HTTPS API.

Configure RESEND_API_KEY and EMAIL_FROM (a sender on a domain verified in Resend), plus APP_URL for links.
Every attempt is recorded in email_log with its real outcome. Without configuration nothing is sent and the
caller is told so (status "not_configured"); the UI then shows the link to copy instead. Delivery is never
simulated.
"""

import logging

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import EmailLog

log = logging.getLogger("baton.email")
RESEND_URL = "https://api.resend.com/emails"
_transport: httpx.BaseTransport | None = None  # tests inject a mock transport here


def set_transport_for_tests(t: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = t


def mask(addr: str) -> str:
    name, _, domain = (addr or "").partition("@")
    return (name[:1] + "***@" + domain)[:80] if domain else "***"


def send(db: Session, to: str, subject: str, text: str, kind: str, project_id: str | None = None) -> str:
    """Send one plain-text email. Returns "sent", "failed" or "not_configured". Never raises."""
    s = get_settings()
    entry = EmailLog(project_id=project_id, kind=kind, to_hint=mask(to), subject=subject[:200], status="not_configured")
    if s.email_configured:
        try:
            with httpx.Client(timeout=15, transport=_transport) as c:
                r = c.post(
                    RESEND_URL,
                    headers={"Authorization": f"Bearer {s.resend_api_key}"},
                    json={"from": s.email_from, "to": [to], "subject": subject, "text": text},
                )
            if r.status_code < 300:
                entry.status = "sent"
            else:
                entry.status, entry.error = "failed", f"Resend {r.status_code}: {r.text[:300]}"
        except Exception as e:  # noqa: BLE001 — network problems must not break the action that triggered email
            entry.status, entry.error = "failed", str(e)[:300]
        if entry.status == "failed":
            log.warning("Email (%s) to %s failed: %s", kind, entry.to_hint, entry.error)
    db.add(entry)
    db.flush()
    return entry.status


def link(path: str) -> str:
    return f"{get_settings().app_url}{path}"


FOOTER = (
    "\n\n--\nSent by Baton, evidence-backed project handovers. You received this because someone added you to a handover project."
)
