"""Regenerate the synthetic demo PDF and DOCX (all content is invented). Run: python scripts/make_seed_files.py"""
from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent.parent / "seed" / "eventapp"


def runbook() -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUT / "deploy-runbook.pdf"), pagesize=A4, title="EventApp deploy runbook",
                            author="Riya Sharma")
    story = [
        Paragraph("EventApp deploy runbook", styles["Title"]),
        Paragraph("Date: 2026-09-30", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("The backend runs on Render and deploys automatically from the main branch.", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("Known issue: the CI build fails every Monday because the test API token expires weekly. "
                  "Refresh TEST_API_TOKEN in the repository secrets and re-run the build.", styles["Normal"]),
        Spacer(1, 8),
        Paragraph("The mobile check-in app depends on the /v2/attendees endpoint. Do not rename or remove it "
                  "before the fest.", styles["Normal"]),
    ]
    doc.build(story)


def handover_notes() -> None:
    d = Document()
    d.core_properties.author = "Riya Sharma"
    d.add_heading("Riya's handover notes (draft)", 0)
    d.add_paragraph("Date: 2026-10-20")
    d.add_heading("Deploy scripts", level=1)
    d.add_paragraph("I own the deploy scripts in scripts/deploy.sh. Only run them from the main branch.")
    d.add_heading("Rate limiting", level=1)
    d.add_paragraph("Rate limiting on the registration API is half done. The limiter works but has no tests "
                    "yet, and it is blocked on the Redis add-on that the club has not paid for.")
    d.add_heading("Payments", level=1)
    d.add_paragraph("We decided to keep online payments switched off until the sponsor MoU is signed, because "
                    "the sponsor asked us to pause payments.")
    d.save(OUT / "riya-handover-notes.docx")


if __name__ == "__main__":
    runbook()
    handover_notes()
    print("Wrote", OUT / "deploy-runbook.pdf", "and", OUT / "riya-handover-notes.docx")
