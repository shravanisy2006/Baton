"""The handover as a real PDF file (not the browser's print dialog), built from exactly what the reader may see."""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")
ACCENT = colors.HexColor("#4F46E5")
LINE = colors.HexColor("#E5E7EB")
AMBER = colors.HexColor("#92400E")

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK, spaceAfter=4)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
ITEM = ParagraphStyle("i", parent=BODY, fontName="Helvetica-Bold", fontSize=9.6)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
QUOTE = ParagraphStyle(
    "q", parent=BODY, fontName="Helvetica-Oblique", fontSize=8.4, leading=11, leftIndent=8, textColor=colors.HexColor("#374151")
)
FLAG = ParagraphStyle("f", parent=SMALL, textColor=AMBER)

CONF = {
    "verified": "Verified",
    "corroborated": "Corroborated",
    "weak": "Weak",
    "conflicting": "Conflicting",
    "leaver_attested": "Leaver-attested",
    "reviewer_asserted": "Reviewer-asserted",
    "unverified": "Unverified",
}
LEVEL = {1: "Team", 2: "Leads", 3: "Restricted"}


def _e(x) -> str:
    return escape(str(x or ""))


def _loc(loc: dict) -> str:
    parts = []
    for k, label in (("section", ""), ("page", "page "), ("row", "row "), ("number", "#"), ("message", "message ")):
        if loc.get(k):
            parts.append(f"{label}{loc[k]}")
    if loc.get("transcribed"):
        parts.append("AI transcription of a scan")
    return " · ".join(parts)


def build_pdf(data: dict) -> bytes:
    c = data["content"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Handover — {c.get('project', '')}",
        author="Baton",
    )
    s = [
        Paragraph(f"Handover: {_e(c.get('project'))}", H1),
        Paragraph(
            f"For {_e(c.get('incoming') or 'the new member')}, from {_e(c.get('departing') or 'the person leaving')}. "
            f"Version {data['version']} ({_e(data['status'])})"
            + (f", approved by {_e(data.get('approved_by'))}" if data.get("approved_by") else "")
            + ". "
            f"Prepared for {_e(data['viewer']['name'])} ({_e(LEVEL.get(data['viewer']['access_level'], ''))} access).",
            SMALL,
        ),
        Spacer(1, 4),
        Paragraph(
            "Every line comes from a claim a reviewer approved, and every quote was found word for word in its "
            "source. Lines from sources above the reader's access level are left out"
            + (f" ({c.get('hidden_count')} here)." if c.get("hidden_count") else "."),
            SMALL,
        ),
    ]
    for sec in c.get("sections", []):
        s.append(Paragraph(f"{_e(sec['title'])} ({len(sec['items'])})", H2))
        if not sec["items"]:
            s.append(Paragraph("Nothing here.", SMALL))
        for it in sec["items"]:
            block = [Paragraph(_e(it.get("action") or it.get("text")), ITEM)]
            meta = []
            if it.get("status"):
                meta.append(f"Status: {_e(it['status']).replace('_', ' ')}")
            if it.get("owner"):
                meta.append(f"Owner: {_e(it['owner'])}")
            if it.get("confidence"):
                meta.append(CONF.get(it["confidence"], it["confidence"]))
            if it.get("change"):
                meta.append("New in this version" if it["change"] == "added" else "Updated in this version")
            if meta:
                block.append(Paragraph(" · ".join(meta), SMALL))
            if it.get("rationale"):
                block.append(Paragraph(f"Why: {_e(it['rationale'])}", BODY))
            if it.get("changed_since_approval"):
                block.append(Paragraph(f"Changed since approval: {_e(it['changed_since_approval'])}", FLAG))
            if it.get("leaver_note"):
                block.append(Paragraph(f"Leaver's note: {_e(it['leaver_note'])}", BODY))
            for ev in it.get("evidence", [])[:3]:
                block.append(Paragraph(f"“{_e(ev.get('quote'))}”", QUOTE))
                src = " · ".join(
                    x
                    for x in (
                        f"{ev.get('code')} {ev.get('source')}",
                        _loc(ev.get("location") or {}),
                        ev.get("author") or "",
                        ev.get("date") or "",
                    )
                    if x
                )
                block.append(Paragraph(_e(src), ParagraphStyle("src", parent=SMALL, leftIndent=8)))
            t = Table([[block]], colWidths=[doc.width])
            t.setStyle(
                TableStyle(
                    [
                        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            s.append(KeepTogether([t]))
    doc.build(s)
    return buf.getvalue()
