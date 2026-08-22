"""Layer 2 — factsheet fact-check (README §6). Kept entirely separate from the
Layer-1 compliance score.

Extract factual claims from the creative, look them up deterministically in the
factsheet KB (no embeddings/RAG — the claims are numbers in tables), and compare.
Every result is stamped with the factsheet as-of date. Unspecified plan/option/
period are surfaced as an assumption ("matches under assumption X") rather than a
hard pass/fail.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from rapidfuzz import fuzz

from . import model

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "factsheet_kb"

_CLAIM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["claim_text", "field", "scheme_name", "period", "plan", "option", "value"],
                "properties": {
                    "claim_text": {"type": "string"},
                    "field": {"enum": ["returns", "aum", "riskometer", "benchmark", "holding", "other"]},
                    "scheme_name": {"type": "string"},   # "" if not named
                    "period": {"type": "string"},        # 1Y | 3Y | 5Y | since_inception | ""
                    "plan": {"type": "string"},          # direct | regular | ""
                    "option": {"type": "string"},        # growth | idcw | ""
                    "value": {"type": "string"},         # claimed value as written, e.g. "18%", "8,421 cr"
                },
            },
        }
    },
}

_CLAIM_SYSTEM = (
    "Extract every verifiable factual claim in this mutual-fund creative that could be checked "
    "against a fund factsheet — returns/CAGR, AUM, riskometer level, benchmark, or a named "
    "holding. For each: the exact claim_text, the field, the scheme named (or empty), the period "
    "(1Y/3Y/5Y/since_inception or empty), plan (direct/regular or empty), option (growth/idcw or "
    "empty), and the claimed value as written. Ignore generic marketing language with no checkable fact."
)


def load_kb() -> list[dict]:
    records: list[dict] = []
    if KB_DIR.exists():
        for f in sorted(KB_DIR.glob("*.json")):
            records.extend(json.loads(f.read_text(encoding="utf-8")))
    return records


def _names(rec: dict) -> list[str]:
    return [rec["scheme_name"], *rec.get("aliases", [])]


# Strip the AMC token so a generic "[AMC] Flexi Cap Fund" matches "Axis Flexi Cap Fund"
# on the scheme-specific part rather than loosely on shared words like "Cap Fund".
_AMC_NOISE = re.compile(r"\[amc\]|\baxis\b", re.I)


def _norm_name(n: str) -> str:
    n = _AMC_NOISE.sub(" ", n.lower())
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def find_records(scheme_name: str, kb: list[dict], threshold: int = 85) -> list[dict]:
    """All KB records (plan/option variants) for the best-matching scheme.
    token_sort_ratio on AMC-stripped names avoids the partial-overlap false match."""
    q = _norm_name(scheme_name)
    if not q:
        return []
    scored = [(max(fuzz.token_sort_ratio(q, _norm_name(n)) for n in _names(r)), r) for r in kb]
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < threshold:
        return []
    best_name = scored[0][1]["scheme_name"]
    return [r for s, r in scored if r["scheme_name"] == best_name]


def _num(s: str):
    m = re.search(r"-?\d+(?:\.\d+)?", (s or "").replace(",", ""))
    return float(m.group()) if m else None


def check_claim(claim: dict, kb: list[dict]) -> dict:
    res = {"claim_text": claim["claim_text"], "verdict": "not_found"}
    if claim.get("field"):
        res["claim_field"] = claim["field"]
    if claim.get("value"):
        res["claimed_value"] = claim["value"]

    recs = find_records(claim.get("scheme_name", ""), kb)
    if not recs:
        res["verdict"] = "not_found"
        res["assumption"] = "no matching scheme in the factsheet KB" if claim.get("scheme_name") \
            else "no scheme named in the claim"
        return res

    plan = claim.get("plan") or None
    option = claim.get("option") or None
    field = claim.get("field")
    # Plan/option only change plan-specific figures (returns, IDCW). AUM,
    # riskometer and benchmark are shared across a scheme's plan/option variants,
    # so picking a variant for them is arbitrary and must NOT raise an assumption.
    plan_relevant = field in ("returns",)

    assumptions = []
    cand = recs
    if plan_relevant:
        filtered = [r for r in recs
                    if (not plan or r.get("plan") == plan) and (not option or r.get("option") == option)]
        if filtered:
            cand = filtered
        else:
            # a plan/option was named but the KB has no such variant: fall back and say so
            if plan and any(r.get("plan") for r in recs):
                assumptions.append(f"{plan} plan not in the factsheet; compared to {recs[0].get('plan')}")
            cand = recs
    rec = cand[0]
    res["scheme_matched"] = rec["scheme_name"]
    res["as_of_date"] = rec.get("as_of_date")
    res["source_file"] = rec.get("source_file")
    if rec.get("plan"):
        res["plan"] = rec["plan"]
    if rec.get("option"):
        res["option"] = rec["option"]
    if plan_relevant:
        if not plan and rec.get("plan"):
            assumptions.append(f"plan={rec['plan']}")
        if not option and rec.get("option"):
            assumptions.append(f"option={rec['option']}")

    fv = None  # factsheet value (for comparison)
    if field == "returns":
        period = claim.get("period") or None
        if not period:
            assumptions.append("period unspecified")
        else:
            fv = (rec.get("returns") or {}).get(period, {}).get("scheme")
        cv = _num(claim.get("value", ""))
        _apply(res, fv, cv, "%", assumptions, need=period)
    elif field == "aum":
        fv = (rec.get("aum") or {}).get("value")
        cv = _num(claim.get("value", ""))
        _apply(res, fv, cv, " cr", assumptions, tol=max(1.0, (fv or 0) * 0.01))
    elif field == "riskometer":
        fv = rec.get("riskometer_level")
        res["factsheet_value"] = fv or "(not in KB)"
        res["verdict"] = "not_found" if not fv else "needs_review"  # dial-graphic; human confirms wording
    else:
        res["verdict"] = "ambiguous"
        res["factsheet_value"] = "(field not auto-verified in v1)"

    if assumptions:
        res["assumption"] = "; ".join(assumptions)
    return res


def _apply(res, fv, cv, unit, assumptions, tol: float = 0.15, need=None):
    if need is None and res.get("claim_field") == "returns":
        res["verdict"] = "ambiguous"
        res["factsheet_value"] = "(period unspecified)"
        return
    if fv is None:
        res["verdict"] = "not_found"
        res["factsheet_value"] = "(not in KB)"
        return
    res["factsheet_value"] = f"{fv}{unit}"
    if cv is None:
        res["verdict"] = "ambiguous"
        return
    close = abs(cv - fv) <= tol
    # If the comparison rests on an assumption, report 'ambiguous' rather than a hard verdict.
    res["verdict"] = ("ambiguous" if assumptions else ("match" if close else "mismatch"))
    if assumptions and not close:
        res["verdict"] = "mismatch"  # differs even from the assumed variant


def run(creative_text: str, kb: list[dict] | None = None) -> dict:
    """Fact-check layer for one creative. Needs the model for claim extraction;
    degrades to an empty layer if unavailable."""
    kb = load_kb() if kb is None else kb
    results: list[dict] = []
    if creative_text.strip() and model.available():
        try:
            out = model.structured(_CLAIM_SYSTEM, creative_text, _CLAIM_SCHEMA,
                                   model=model.fast_model_id())
            for claim in out.get("claims", []):
                results.append(check_claim(claim, kb))
        except Exception:  # noqa: BLE001 — never break the run on a model error
            results = []

    tally = {"match": 0, "mismatch": 0, "ambiguous": 0, "not_found": 0}
    for r in results:
        tally[r["verdict"]] += 1
    return {
        "results": results,
        "summary": {
            "claims_checked": len(results),
            "matches": tally["match"],
            "mismatches": tally["mismatch"],
            "ambiguous": tally["ambiguous"],
            "not_found": tally["not_found"],
        },
    }
