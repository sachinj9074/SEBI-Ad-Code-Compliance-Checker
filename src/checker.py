"""Stage B — requirement checks, and assembly of the Layer-1 verdict (README §3).

Verdict rules:
  * conditional rule whose trigger feature is absent  -> not_applicable
  * rule carrying mandated_text                       -> deterministic fuzzy presence (pass/fail)
  * check_type == assisted                            -> needs_review (never pretends to decide)
  * check_type == automated without mandated_text     -> model judgment if a key is set, else needs_review
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import factcheck
from . import features as featuremod
from . import match, model
from .corpus import filter_rules, load_rules
from .extract import extract

TOOL_VERSION = "0.1.0"

_JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict"],
    "properties": {
        "verdict": {"enum": ["pass", "fail", "needs_review"]},
        "offending_text": {"type": "string"},
        "explanation": {"type": "string"},
    },
}


def _judge(rule: dict, text: str) -> dict:
    """Model judgment for an automated rule that has no verbatim mandated_text."""
    system = (
        "You check one SEBI mutual-fund advertisement rule against a creative. "
        "Return 'pass' if the creative complies, 'fail' if it clearly violates the "
        "rule, or 'needs_review' if you cannot tell. Quote the offending text on a fail."
    )
    prompt = (
        f"Rule: {rule['description']}\n"
        f"Source: {rule['source_clause']}\n\n"
        "Creative:\n\"\"\"\n" + text.strip() + "\n\"\"\"\n"
    )
    return model.structured(system, prompt, _JUDGE_SCHEMA, max_tokens=1024)


def check_rule(rule: dict, text: str, present: set[str], vision: dict | None = None) -> dict:
    res = _decide(rule, text, present)
    _apply_vision(res, rule, vision)
    return res


def _decide(rule: dict, text: str, present: set[str]) -> dict:
    trig = rule["trigger"]
    triggered_by = "unconditional" if trig["type"] == "unconditional" else trig.get("feature")

    res = {
        "rule_id": rule["rule_id"],
        "triggered_by": triggered_by,
        "severity": rule["severity"],
        "source_clause": rule["source_clause"],
        "provenance": rule["provenance"],
        "check_type": rule["check_type"],
    }

    # Conditional rule whose feature wasn't detected: out of play.
    if trig["type"] == "conditional" and trig.get("feature") not in present:
        res["verdict"] = "not_applicable"
        return res

    # Deterministic verbatim-disclaimer presence.
    if "mandated_text" in rule:
        mt = rule["mandated_text"]
        found, score = match.present(mt["text"], text, mt.get("match_threshold", 0.85))
        res["verdict"] = "pass" if found else "fail"
        res["confidence"] = score
        if not found:
            res["explanation"] = f"Required disclaimer not found (best match {score:.0%})."
            res["suggested_rewrite"] = f"Add the required disclaimer: “{mt['text']}”"
        return res

    # Human-judgment rules always raise a flag.
    if rule["check_type"] == "assisted":
        res["verdict"] = "needs_review"
        if rule.get("sub_criteria"):
            res["matched_criteria"] = [c["id"] for c in rule["sub_criteria"]]
        res["explanation"] = "Assisted rule — requires a human check."
        return res

    # Automated rule without mandated_text: model judgment, else defer.
    if model.available():
        try:
            j = _judge(rule, text)
            res["verdict"] = j["verdict"]
            if j.get("offending_text"):
                res["offending_text"] = j["offending_text"]
            if j.get("explanation"):
                res["explanation"] = j["explanation"]
        except Exception as exc:  # invalid key, rate limit, etc. — never crash the run
            res["verdict"] = "needs_review"
            res["explanation"] = f"Automated check unavailable ({type(exc).__name__}); flagged for review."
    else:
        res["verdict"] = "needs_review"
        res["explanation"] = "Automated check needs the model (no API key set)."
    return res


def _apply_vision(res: dict, rule: dict, vision: dict | None) -> None:
    """Let the visual pass drive the rules OCR can't (README §5): legibility of the
    mandatory warning, risk-o-meter presence/legibility, prominent-person context."""
    if not vision:
        return
    rid = rule["rule_id"]
    leg = vision.get("disclaimer_legibility")

    # Standard warnings present but not legibly sized -> a text 'pass' becomes needs_review.
    if rid in ("DISC-001", "DISC-002") and res.get("verdict") == "pass" and leg == "illegible":
        res["verdict"] = "needs_review"
        res["offending_element"] = "disclaimer (present but illegible)"
        res["explanation"] = "Warning text is present but flagged as not legibly sized (vision)."

    elif rid == "LEGIB-001":
        if leg == "legible":
            res["verdict"] = "pass"
            res["explanation"] = "Content and disclaimers read as legible (vision)."
        elif leg == "illegible":
            res["verdict"] = "fail"
            res["offending_element"] = "disclaimer (illegible)"
            res["explanation"] = vision.get("legibility_notes") or "Disclaimer not legibly sized (vision)."
        elif leg == "absent":
            res["verdict"] = "fail"
            res["explanation"] = "Mandatory warning appears absent (vision)."

    elif rid == "DISC-005":  # product labelling / risk-o-meter
        if not vision.get("riskometer_present"):
            res["verdict"] = "fail"
            res["explanation"] = "Risk-o-meter not found in the creative (vision)."
        elif not vision.get("riskometer_legible", True):
            res["verdict"] = "needs_review"
            res["explanation"] = "Risk-o-meter present but not legible (vision)."
        else:
            res["verdict"] = "pass"
            lvl = vision.get("riskometer_level")
            res["explanation"] = "Risk-o-meter present and legible (vision)" + (f" — {lvl}." if lvl else ".")

    elif rid == "CELEB-001" and vision.get("prominent_person_present") and res.get("verdict") == "needs_review":
        res["explanation"] = "Prominent person depicted: " + (
            vision.get("prominent_person_desc") or "review against the celebrity definition")


def run_rules(rules: list[dict], text: str, present: set[str], vision: dict | None = None) -> dict:
    results = [check_rule(r, text, present, vision) for r in rules]
    tally = {"pass": 0, "fail": 0, "needs_review": 0, "not_applicable": 0}
    for r in results:
        tally[r["verdict"]] += 1
    summary = {
        "rules_run": len(results),
        "passed": tally["pass"],
        "failed": tally["fail"],
        "needs_review": tally["needs_review"],
        "not_applicable": tally["not_applicable"],
    }
    return {"results": results, "summary": summary}


def build_verdict(file: str, areas: list[str], creative_type: str) -> dict:
    """Full Layer-1 verdict for one creative. Layers 2 & 3 are stubbed for now."""
    ex = extract(file)
    text = ex["extracted_text"]
    vision = ex.get("vision")

    feats = featuremod.detect(text) if text.strip() else []
    if vision:  # add prominent-person / language signals the text can't give
        seen = {f["feature"] for f in feats}
        feats += [f for f in featuremod.from_vision(vision) if f["feature"] not in seen]
    present = {f["feature"] for f in feats if f["present"]}

    scoped = filter_rules(load_rules(), areas, creative_type)
    rule_layer = run_rules(scoped, text, present, vision)

    # Layer 2 — kept entirely separate from the Layer-1 score.
    fact_check = factcheck.run(text)

    s = rule_layer["summary"]
    return {
        "schema_version": TOOL_VERSION,
        "meta": {
            "source_filename": file,
            "areas_selected": areas,
            "creative_type": creative_type,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "model_used": model.model_id() if model.available() else "none (deterministic only)",
            "tool_version": TOOL_VERSION,
        },
        "extraction": {
            "extracted_text": text,
            "confidence": ex["confidence"],
            "source_kind": ex["source_kind"],
            "warnings": ex["warnings"],
            **({"languages_detected": vision.get("languages", []),
                "layout_notes": vision.get("layout_notes", ""),
                "legibility_notes": vision.get("legibility_notes", "")} if vision else {}),
        },
        "feature_detection": {"features": feats},
        "rule_layer": rule_layer,
        "fact_check_layer": fact_check,
        "advisory_layer": {"notes": []},
        "summary_strip": {
            "rules_run": s["rules_run"],
            "passed": s["passed"],
            "failed": s["failed"],
            "needs_review": s["needs_review"],
            "fact_mismatches": fact_check["summary"]["mismatches"],
            "advisory_notes": 0,
        },
    }
