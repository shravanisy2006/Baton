"""Spot text in uploaded evidence that is written *to an AI* (possible prompt injection).

Evidence is untrusted. Baton never lets the AI's word stand alone (every quote is checked in code and a person
approves every line), but text like "ignore previous instructions" deserves a visible warning, a stricter
extraction prompt, and claims based only on such text can never count as verified automatically.
"""

import re

PATTERNS = [
    r"\bignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"\bdisregard (all |any |the )?(previous|prior|above|earlier|system) (instructions|prompts?|rules)",
    r"\b(forget|override) (all |your |the )?(previous |prior )?(instructions|rules|guidelines)",
    r"\byou are now\b",
    r"\b(new|updated) (system )?instructions?\s*:",
    r"\bsystem prompt\b",
    r"^\s*(system|assistant)\s*:",
    r"\bas an ai (language )?model\b",
    r"\b(mark|label|treat) (this|these|all) (claims?|statements?|facts?) as (verified|approved|true)\b",
    r"\bdo not (flag|mention|report) (this|these|any)\b",
    r"\bjailbreak\b",
]
_RE = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.IGNORECASE | re.MULTILINE)


def flags_for(text: str) -> list[str]:
    return ["instructions"] if _RE.search(text or "") else []
