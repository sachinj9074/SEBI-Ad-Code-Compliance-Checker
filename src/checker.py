"""Stage B — requirement checks, and assembly of the Layer-1 verdict (README §3).

Verdict rules:
  * conditional rule whose trigger feature is absent  -> not_applicable
  * rule carrying mandated_text                       -> deterministic fuzzy presence (pass/fail)
  * check_type == assisted                            -> needs_review (never pretends to decide)
  * check_type == automated without mandated_text     -> model judgment if a key is set, else needs_review
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from . import advisory
from . import factcheck
from . import features as featuremod
from . import match, model
from .corpus import filter_rules, load_rules
from .extract import extract

TOOL_VERSION = "0.1.0"


def _content_hash(file: str) -> str:
    """SHA-256 of the creative, for the clearance report's identity block. A
    directory (carousel) is hashed over its files in name order. Never raises."""
    try:
        p = Path(file)
        h = hashlib.sha256()
        paths = sorted(p.rglob("*")) if p.is_dir() else [p]
        for fp in paths:
            if fp.is_file():
                h.update(fp.name.encode("utf-8"))
                h.update(fp.read_bytes())
        return h.hexdigest()
    except Exception:  # noqa: BLE001 — identity is best-effort, never fatal
        return "not recorded"

_JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict"],
    "properties": {
        "verdict": {"enum": ["pass", "fail", "needs_review"]},
        "offending_text": {"type": "string"},
        "explanation": {"type": "string"},
        "suggested_fix": {"type": "string"},
    },
}


def _judge(rule: dict, text: str) -> dict:
    """Model judgment for an automated rule that has no verbatim mandated_text.
    Explanations/fixes are written for a marketing or product person doing a
    first-pass self-check — plain English, no clause numbers or jargon."""
    system = (
        "You check ONE SEBI mutual-fund advertisement rule against a creative, on behalf of a "
        "marketing / product person running a first-pass self-check before compliance review — "
        "they are not a compliance expert. "
        "Return 'pass' if the creative complies, 'fail' if it clearly breaks the rule, or "
        "'needs_review' only if you genuinely cannot tell from the text. "
        "On a fail: 'explanation' is ONE plain-English sentence saying what is wrong and why it "
        "matters (no clause numbers, no jargon); 'offending_text' quotes the exact words from the "
        "creative; 'suggested_fix' is the specific edit to make — add, remove, or reword what."
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
        "title": rule["title"],              # short headline for the UI card
        "description": rule["description"],  # plain-language: what this rule checks
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
            res["explanation"] = ("A disclaimer this creative must carry is missing (or its wording "
                                  f"differs too much from the mandated text — closest match {score:.0%}).")
            res["suggested_rewrite"] = f"Add this exact text: “{mt['text']}”"
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
            if j["verdict"] == "fail" and j.get("suggested_fix"):
                res["suggested_rewrite"] = j["suggested_fix"]
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
    rid = rule["rule_id"]
    if not vision:
        # Legibility is a purely visual property; on a text / DOCX / text-PDF creative
        # there is nothing to judge, so mark it not_applicable rather than raising a
        # noisy needs_review the user can't action.
        if rid == "LEGIB-001" and res.get("verdict") == "needs_review":
            res["verdict"] = "not_applicable"
            res.pop("explanation", None)
        return
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


def build_verdict(file: str, area: str, creative_types: list[str]) -> dict:
    """Full Layer-1 verdict for one creative.

    `area` is the single selected business area; `creative_types` the selected
    creative types (empty for IAP, which takes no creative-type input).
    """
    ex = extract(file)
    text = ex["extracted_text"]
    vision = ex.get("vision")

    feats = featuremod.detect(text) if text.strip() else []
    if vision:  # add prominent-person / language signals the text can't give
        seen = {f["feature"] for f in feats}
        feats += [f for f in featuremod.from_vision(vision) if f["feature"] not in seen]
    present = {f["feature"] for f in feats if f["present"]}

    # Warn-only scheme-content check (user decision 2026-08-22): under a
    # non-scheme area the scheme-related rules stay off, but if the creative
    # names a scheme or shows performance we say so loudly rather than let a
    # false-clean result pass silently. The warning also goes on any report.
    selection_warnings: list[str] = []
    if area != "scheme_related" and present & {"scheme_name", "performance"}:
        what = " and ".join(sorted(
            {"scheme_name": "a scheme name", "performance": "performance figures"}[f]
            for f in present & {"scheme_name", "performance"}))
        selection_warnings.append(
            f"This creative contains {what}, but the selected business area is not "
            f"'Scheme-related', so the scheme-specific rules (sponsor/suitability "
            f"disclaimers, risk-o-meter, performance requirements) were NOT checked. "
            f"If it promotes a specific scheme, re-run it under Scheme-related."
        )

    scoped = filter_rules(load_rules(), area, creative_types)
    rule_layer = run_rules(scoped, text, present, vision)

    # Layer 2 — kept entirely separate from the Layer-1 score.
    fact_check = factcheck.run(text)

    # Layer 3 — advisory, unscored. Sets the rules aside (never sees the Layer-1
    # results) and never affects the pass/fail summary.
    advisory_layer = advisory.run(text, vision)

    s = rule_layer["summary"]
    return {
        "schema_version": TOOL_VERSION,
        "meta": {
            "source_filename": Path(file).name,
            "content_sha256": _content_hash(file),
            "areas_selected": [area],
            "creative_type": creative_types,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "model_used": model.model_id() if model.available() else "none (deterministic only)",
            "tool_version": TOOL_VERSION,
            **({"selection_warnings": selection_warnings} if selection_warnings else {}),
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
        "advisory_layer": advisory_layer,
        "summary_strip": {
            "rules_run": s["rules_run"],
            "passed": s["passed"],
            "failed": s["failed"],
            "needs_review": s["needs_review"],
            "fact_mismatches": fact_check["summary"]["mismatches"],
            "advisory_notes": len(advisory_layer["notes"]),
        },
    }
