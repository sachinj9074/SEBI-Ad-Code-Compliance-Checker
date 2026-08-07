"""Fuzzy presence check for verbatim mandated disclaimers (README §4).

Tolerates line-break, punctuation, and casing drift; handles Devanagari (no
casefold applied to non-Latin text). No model needed.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    s = (
        s.replace("’", "'").replace("‘", "'")
        .replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-")
    )
    return _WS.sub(" ", s).strip()


def present(mandated: str, text: str, threshold: float = 0.85) -> tuple[bool, float]:
    """Return (found, score in 0..1). `found` iff the mandated phrase appears in
    `text` above `threshold`, matched fuzzily as a substring."""
    m, t = _norm(mandated), _norm(text)
    if not m:
        return (False, 0.0)
    # partial_ratio aligns the shorter string (the disclaimer) within the longer
    # (the creative); casefold only helps Latin scripts, harmless for Devanagari.
    score = fuzz.partial_ratio(m.casefold(), t.casefold()) / 100.0
    return (score >= threshold, round(score, 3))
