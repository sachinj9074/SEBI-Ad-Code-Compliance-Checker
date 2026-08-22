"""Load the rule corpus and filter it to a run (business area x creative types).

Mirrors the segmentation in corpus/SEGMENTS.md. No model needed.

Taxonomy (2026-08): the user picks ONE business area, then a conditional
multi-select of creative types. Rules tagged 'all' (area or creative type) are
the mandatory baseline and always run; 'all' is never a user-facing option.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "corpus" / "rules"

# User-facing vocabulary (single source of truth for the app and CLI).
AREAS = ["scheme_related", "iap", "others_media"]
# Creative-type options offered per area (IAP takes no creative-type input).
AREA_CTYPE_OPTIONS = {
    "scheme_related": ["nfo", "key_visual", "yield"],
    "iap": [],
    "others_media": ["social_post", "article", "blog", "anniversary"],
}

# Creative types the v1 checker offers (video is encoded but inactive).
ACTIVE_CREATIVE_TYPES = {"nfo", "key_visual", "yield", "social_post", "article", "blog", "anniversary"}


def load_rules(include_inactive: bool = False) -> list[dict]:
    """All rules across corpus/rules/*.json (active-only unless asked otherwise)."""
    rules: list[dict] = []
    for f in sorted(RULES_DIR.glob("*.json")):
        rules.extend(json.loads(f.read_text(encoding="utf-8")))
    if not include_inactive:
        rules = [r for r in rules
                 if "all" in r["creative_type"] or set(r["creative_type"]) & ACTIVE_CREATIVE_TYPES]
    return rules


def in_scope(rule: dict, area: str, creative_types: set[str]) -> bool:
    """A rule is in scope when its area matches the selected area ('all' matches
    any) and its creative types intersect the selection ('all' matches any;
    an empty selection, e.g. IAP, matches only 'all'-tagged rules)."""
    ap = set(rule["applies_to"])
    if "all" not in ap and area not in ap:
        return False
    ct = set(rule["creative_type"])
    return "all" in ct or bool(ct & creative_types)


def filter_rules(rules: list[dict], area: str, creative_types: list[str]) -> list[dict]:
    cset = set(creative_types)
    return [r for r in rules if in_scope(r, area, cset)]
