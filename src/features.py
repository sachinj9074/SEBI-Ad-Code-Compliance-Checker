"""Stage A — feature detection (README §3).

Identify what the creative contains so Stage B can activate conditional rules.
Uses the model when a key is available; otherwise falls back to a transparent
keyword heuristic so the pipeline runs end-to-end (clearly lower recall — the
model path is the real one, and vision handles images on Day 2).
"""
from __future__ import annotations

import re

from . import model

# The feature vocabulary the corpus triggers on (schemas/rule.schema.json $defs/feature).
FEATURES = [
    "performance", "named_stocks", "named_sectors", "sip_reference", "aum_figure",
    "yield_ytm", "prominent_person", "scheme_name", "non_english_language",
    "idcw_payout", "tax_reference", "fund_of_funds", "elss", "graph_chart",
    "market_cap_terms", "index_etf", "exchange_listed", "offshore_promotion",
    "app_rating", "planning_tool", "asset_allocation", "sip_low_ticket",
    "small_cap_scheme", "merged_scheme",
]

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["features"],
    "properties": {
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["feature", "present"],
                "properties": {
                    "feature": {"type": "string", "enum": FEATURES},
                    "present": {"type": "boolean"},
                    "evidence": {"type": "string"},
                },
            },
        }
    },
}

_SYSTEM = (
    "You detect content features in a mutual-fund marketing creative for a SEBI "
    "advertisement-code compliance check. For each feature, decide if it is present "
    "and quote the shortest supporting evidence. Be precise; do not over-flag. "
    "'market_cap_terms' means the creative actually classifies holdings or strategy by "
    "market capitalisation (large-cap / mid-cap / small-cap) — NOT merely a fund's proper "
    "name that contains the word 'cap' (e.g. 'Flexi Cap Fund' or 'Large & Mid Cap Fund' as "
    "a scheme name is not, by itself, use of market-cap terms)."
)

# Keyword heuristics for the keyless fallback (deliberately conservative).
_HEURISTICS = {
    "performance": r"\b(cagr|returns?|%|annuali[sz]ed|1[- ]?year|3[- ]?year|5[- ]?year)\b",
    "sip_reference": r"\bsip\b",
    "aum_figure": r"\baum\b|assets under management",
    "yield_ytm": r"\bytm\b|yield to maturity|portfolio yield",
    "idcw_payout": r"\bidcw\b|dividend|pay-?out",
    "tax_reference": r"\btax\b|section\s?80c|80c",
    "elss": r"\belss\b|tax saver",
    "graph_chart": r"\bgraph\b|\bchart\b",
    "market_cap_terms": r"\b(large|mid|small)\s?cap\b",
    "index_etf": r"\betf\b|index fund|nifty|sensex",
    "sip_low_ticket": r"\b(rs\.?\s?100|₹\s?100|rs\.?\s?10|₹\s?10)\b",
    "non_english_language": r"[ऀ-ॿ]",  # Devanagari
}


def detect(text: str) -> list[dict]:
    """Return [{feature, present, evidence?}, ...]. Model path if a key is set,
    else the keyword heuristic."""
    if model.available():
        try:
            return _detect_model(text)
        except Exception:  # invalid key / API error — fall back rather than crash
            return _detect_heuristic(text)
    return _detect_heuristic(text)


def detect_map(text: str) -> dict[str, bool]:
    return {f["feature"]: bool(f["present"]) for f in detect(text)}


def from_vision(v: dict) -> list[dict]:
    """Features that come from the visual pass rather than the text."""
    feats = []
    if v.get("prominent_person_present"):
        feats.append({"feature": "prominent_person", "present": True,
                      "evidence": v.get("prominent_person_desc", "")})
    langs = [l.lower() for l in v.get("languages", [])]
    if langs and any(l not in ("en", "english") for l in langs):
        feats.append({"feature": "non_english_language", "present": True,
                      "evidence": ", ".join(v.get("languages", []))})
    return feats


def _detect_model(text: str) -> list[dict]:
    prompt = (
        "Creative text:\n\"\"\"\n" + text.strip() + "\n\"\"\"\n\n"
        "Return, for each feature you assess, whether it is present.\n"
        "Features: " + ", ".join(FEATURES)
    )
    out = model.structured(_SYSTEM, prompt, _SCHEMA, model=model.fast_model_id())
    return out.get("features", [])


def _detect_heuristic(text: str) -> list[dict]:
    found = []
    for feat, pat in _HEURISTICS.items():
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            found.append({"feature": feat, "present": True, "evidence": m.group(0)})
    return found
