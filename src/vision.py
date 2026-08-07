"""Vision ingestion for image creatives (README §5).

A large share of ad-code violations are visual, not textual: a disclaimer present
but unreadably small, the standard warning low-contrast, the risk-o-meter missing
or illegible. Plain OCR flattens a 4-point illegible disclaimer and a clear one
into the same string, and the violation vanishes. So we read the creative as a
creative — asking both "what does this say" (incl. Devanagari) and "is the
mandatory disclaimer present and legibly sized" — and return structured fields
with a confidence, feeding legibility, risk-o-meter and prominent-person judgments
into the rule layer.
"""
from __future__ import annotations

import base64
from pathlib import Path

from . import model

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_MEDIA = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
}

_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": [
        "extracted_text", "languages", "layout_notes",
        "disclaimer_legibility", "legibility_notes",
        "prominent_person_present", "prominent_person_desc",
        "riskometer_present", "riskometer_level", "riskometer_legible",
        "confidence",
    ],
    "properties": {
        "extracted_text": {"type": "string"},
        "languages": {"type": "array", "items": {"type": "string"}},   # e.g. ["en","hi"]
        "layout_notes": {"type": "string"},
        # Judgement on the mandatory 14-word market-risk warning specifically:
        "disclaimer_legibility": {"enum": ["legible", "illegible", "absent"]},
        "legibility_notes": {"type": "string"},
        "prominent_person_present": {"type": "boolean"},
        "prominent_person_desc": {"type": "string"},
        "riskometer_present": {"type": "boolean"},
        "riskometer_level": {"type": "string"},          # e.g. "Very High" or ""
        "riskometer_legible": {"type": "boolean"},
        "confidence": {"type": "number"},                # 0..1 extraction confidence
    },
}

_SYSTEM = (
    "You are reviewing a mutual-fund marketing creative (image/banner/frame) for a SEBI "
    "advertisement-code compliance check. Do two jobs a plain OCR cannot:\n"
    "1. Read ALL text, including Devanagari (Hindi) — put it in extracted_text and list the "
    "languages.\n"
    "2. Make VISUAL judgements: is the mandatory 14-word market-risk warning ('Mutual Fund "
    "investments are subject to market risks…') present and LEGIBLY sized (font commensurate with "
    "the body text), present-but-tiny/low-contrast (illegible), or absent? Is a prominent person "
    "or celebrity depicted? Is a risk-o-meter shown — at what level, and is it legible? Note the "
    "layout. Give an overall extraction confidence between 0 and 1. Never guess text you cannot "
    "actually read; lower the confidence instead."
)

_PROMPT = "Analyse this creative and return the structured fields."


def analyze_bytes(data: bytes, media_type: str) -> dict:
    b64 = base64.standard_b64encode(data).decode("ascii")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
        {"type": "text", "text": _PROMPT},
    ]
    return model.structured_content(_SYSTEM, content, _SCHEMA, max_tokens=4096)


def analyze_image(path: str | Path) -> dict:
    p = Path(path)
    media = _MEDIA.get(p.suffix.lower())
    if not media:
        raise ValueError(f"Unsupported image type {p.suffix!r}")
    return analyze_bytes(p.read_bytes(), media)


def merge_frames(frames: list[dict]) -> dict:
    """Combine per-frame vision results for a carousel: concatenate text, and take
    the worst-case for legibility / presence (any frame with an issue flags it)."""
    if len(frames) == 1:
        return frames[0]
    text = "\n\n".join(f"[frame {i + 1}]\n{f.get('extracted_text', '')}" for i, f in enumerate(frames))
    langs = sorted({l for f in frames for l in f.get("languages", [])})
    # legibility: 'absent' if no frame shows it, else worst of legible/illegible
    legs = [f.get("disclaimer_legibility") for f in frames]
    legibility = "absent" if all(l == "absent" for l in legs) else ("illegible" if "illegible" in legs else "legible")
    return {
        "extracted_text": text,
        "languages": langs,
        "layout_notes": " | ".join(f.get("layout_notes", "") for f in frames if f.get("layout_notes")),
        "disclaimer_legibility": legibility,
        "legibility_notes": " | ".join(f.get("legibility_notes", "") for f in frames if f.get("legibility_notes")),
        "prominent_person_present": any(f.get("prominent_person_present") for f in frames),
        "prominent_person_desc": " | ".join(f.get("prominent_person_desc", "") for f in frames if f.get("prominent_person_desc")),
        "riskometer_present": any(f.get("riskometer_present") for f in frames),
        "riskometer_level": next((f.get("riskometer_level") for f in frames if f.get("riskometer_level")), ""),
        "riskometer_legible": all(f.get("riskometer_legible", True) for f in frames if f.get("riskometer_present")),
        "confidence": min((f.get("confidence", 0.0) for f in frames), default=0.0),
        "frames": frames,
    }
