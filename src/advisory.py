"""Layer 3 — open-ended advisory (README §3). Unscored, fenced, never affects the
pass/fail summary.

A second model pass that *sets the rules aside* (it never sees the Layer-1 results)
and surfaces anything that reads as misleading, exaggerated, or off-tone — the kind
of judgment a rule checklist can't encode. Output is a "you may also want to look at
this" list, not a verdict. Degrades to an empty layer when the model is unavailable,
exactly like the fact-check layer.
"""
from __future__ import annotations

from . import model

_ADVISORY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["notes"],
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["note"],
                "properties": {
                    # One concrete observation, tied to the actual wording.
                    "note": {"type": "string"},
                    # Optional short tag: tone | exaggeration | clarity | omission | imagery | other
                    "area": {"type": "string"},
                },
            },
        }
    },
}

_ADVISORY_SYSTEM = (
    "You are a senior mutual-fund advertising compliance reviewer giving an informal second read. "
    "The formal rule checks have already run — set them aside completely; do not restate rule or "
    "disclaimer violations. Read the creative the way a discerning retail investor would and surface "
    "only things a checklist would MISS: selective or cherry-picked framing, implied guarantees, "
    "emotional pressure or FOMO, unsubstantiated superlatives, a celebratory or triumphant tone that "
    "undercuts the risk disclosures, and claims that are technically accurate but likely to mislead. "
    "Each note is one specific, concrete observation in plain language, tied to the actual wording — "
    "not a general lecture. Keep each note to one or two sentences, and return at most the eight most "
    "significant, ordered most important first. Do NOT assign pass/fail, scores, or severities. Do NOT "
    "invent problems: if the copy reads clean and fair, return an empty list. This is advisory only."
)

# Verbose notes at a tight ceiling truncate the JSON mid-generation; give ample headroom
# (the prompt already caps the note count/length so output stays well under this).
_MAX_TOKENS = 4096


def run(creative_text: str, vision: dict | None = None) -> dict:
    """Advisory layer for one creative. Needs the model; degrades to an empty
    layer (no notes) when no key is set or the call fails — the run never breaks."""
    context = creative_text.strip()
    if vision:  # let the advisory comment on visual tone too, not just the words
        extra = []
        if vision.get("layout_notes"):
            extra.append("Layout: " + vision["layout_notes"])
        if vision.get("legibility_notes"):
            extra.append("Legibility: " + vision["legibility_notes"])
        if extra:
            context = (context + "\n\n[Visual context]\n" + "\n".join(extra)).strip()

    notes: list[dict] = []
    if context and model.available():
        try:
            out = model.structured(_ADVISORY_SYSTEM, context, _ADVISORY_SCHEMA, max_tokens=_MAX_TOKENS)
            for n in out.get("notes", []):
                note = (n.get("note") or "").strip()
                if not note:
                    continue
                item = {"note": note}
                if n.get("area"):
                    item["area"] = n["area"].strip()
                notes.append(item)
        except Exception:  # noqa: BLE001 — advisory is best-effort; never break the run
            notes = []

    return {"notes": notes}
