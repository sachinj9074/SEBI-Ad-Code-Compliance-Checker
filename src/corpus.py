"""Load the rule corpus and filter it to a run (business area x creative type).

Mirrors the segmentation in corpus/SEGMENTS.md. No model needed.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "corpus" / "rules"

# Creative types the v1 checker offers (video is encoded but inactive).
ACTIVE_CREATIVE_TYPES = {"general_kv", "anniversary", "yield", "article_blog", "social_post"}


def load_rules(include_inactive: bool = False) -> list[dict]:
    """All rules across corpus/rules/*.json (active-only unless asked otherwise)."""
    rules: list[dict] = []
    for f in sorted(RULES_DIR.glob("*.json")):
        rules.extend(json.loads(f.read_text(encoding="utf-8")))
    if not include_inactive:
        rules = [r for r in rules if set(r["creative_type"]) & ACTIVE_CREATIVE_TYPES]
    return rules


def in_scope(rule: dict, areas: set[str], creative_type: str) -> bool:
    """A rule is in scope when the creative type matches and the area intersects
    ('all' matches any selected area)."""
    if creative_type not in rule["creative_type"]:
        return False
    ap = set(rule["applies_to"])
    return "all" in ap or bool(ap & areas)


def filter_rules(rules: list[dict], areas: list[str], creative_type: str) -> list[dict]:
    aset = set(areas)
    return [r for r in rules if in_scope(r, aset, creative_type)]
