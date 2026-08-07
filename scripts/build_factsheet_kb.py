"""Build the factsheet knowledge base (README §6).

Monthly batch job: walk each factsheet PDF, model-extract one record per scheme
(structured outputs against a strict schema), expand plan/option variants into
factsheet_record entries, validate against schemas/factsheet_record.schema.json,
and write data/factsheet_kb/<active|passive>.json.

Runs on a cheaper model by default (batch extraction; README §9 "cost near zero").

    .venv\\Scripts\\python.exe scripts/build_factsheet_kb.py --which both
    .venv\\Scripts\\python.exe scripts/build_factsheet_kb.py --which active --pages 8      # test one page
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import model  # noqa: E402

SRC = ROOT / "sources"
OUT = ROOT / "data" / "factsheet_kb"
SCHEMA = json.loads((ROOT / "schemas" / "factsheet_record.schema.json").read_text(encoding="utf-8"))

FILES = {
    "active": ("factsheet_active_2026-06-30.pdf", "active"),
    "passive": ("factsheet_passive_2026-06-30.pdf", "passive"),
}
AS_OF = "2026-06-30"
BATCH_MODEL = "claude-haiku-4-5"

# ---- model-facing extraction schema (strict: additionalProperties false, all required) ----
_PERIOD = {
    "type": "object", "additionalProperties": False,
    "required": ["scheme", "benchmark"],
    "properties": {"scheme": {"type": ["number", "null"]}, "benchmark": {"type": ["number", "null"]}},
}
_RETURNS = {
    "type": "object", "additionalProperties": False,
    "required": ["1Y", "3Y", "5Y", "since_inception"],
    "properties": {"1Y": _PERIOD, "3Y": _PERIOD, "5Y": _PERIOD, "since_inception": _PERIOD},
}
_VARIANT = {
    "type": "object", "additionalProperties": False,
    "required": ["plan", "option", "expense_ratio", "returns"],
    "properties": {
        "plan": {"type": "string"},    # "" if absent (structured-output union limit)
        "option": {"type": "string"},
        "expense_ratio": {"type": ["number", "null"]},
        "returns": _RETURNS,
    },
}
_HOLDING = {
    "type": "object", "additionalProperties": False,
    "required": ["name", "weight_pct"],
    "properties": {"name": {"type": "string"}, "weight_pct": {"type": ["number", "null"]}},
}
_EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["scheme_name", "aliases", "category", "benchmark", "riskometer_level",
                 "aum_crore", "inception_date", "fund_managers", "top_holdings",
                 "underlying_index", "tracking_error", "variants"],
    "properties": {
        "scheme_name": {"type": "string"},
        "aliases": {"type": "array", "items": {"type": "string"}},
        "category": {"type": "string"},          # "" if absent
        "benchmark": {"type": "string"},
        "riskometer_level": {"type": "string"},
        "aum_crore": {"type": ["number", "null"]},
        "inception_date": {"type": "string"},    # YYYY-MM-DD, or "" if absent
        "fund_managers": {"type": "array", "items": {"type": "string"}},
        "top_holdings": {"type": "array", "items": _HOLDING},
        "underlying_index": {"type": "string"},
        "tracking_error": {"type": ["number", "null"]},
        "variants": {"type": "array", "items": _VARIANT},
    },
}

_SYSTEM = (
    "You extract structured data from ONE mutual-fund scheme's monthly factsheet page. "
    "Use only what is present on the page; use an EMPTY STRING for absent text fields, null for "
    "absent numbers, and empty arrays where nothing applies — never invent figures. Return the "
    "scheme's own returns (not the benchmark) under 'scheme' and the stated benchmark's returns "
    "under 'benchmark', per period. Percentages as plain numbers (e.g. -4.24), AUM in INR crore, "
    "inception_date as YYYY-MM-DD, riskometer_level as written (e.g. 'Very High') or empty. One "
    "'variant' per plan+option returns row shown (e.g. Regular-Growth, Direct-Growth). "
    "Set underlying_index only for index funds / ETFs; leave it empty for actively-managed funds."
)

_RISK_MAP = {
    "low": "low", "low to moderate": "low_to_moderate", "moderate": "moderate",
    "moderately high": "moderately_high", "high": "high", "very high": "very_high",
}

# Passive returns live in a comprehensive returns annexure, not the per-scheme pages.
_RET_ROW = {
    "type": "object", "additionalProperties": False,
    "required": ["scheme_name", "plan", "option", "returns"],
    "properties": {
        "scheme_name": {"type": "string"},
        "plan": {"type": "string"},
        "option": {"type": "string"},
        "returns": _RETURNS,
    },
}
_RETURNS_ANNEX_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["rows"],
    "properties": {"rows": {"type": "array", "items": _RET_ROW}},
}
_RET_SYSTEM = (
    "This is a factsheet returns annexure listing many schemes. For every scheme + plan "
    "(Regular/Direct) + option (Growth/IDCW) row, extract the scheme's own CAGR under 'scheme' and "
    "the stated benchmark's CAGR under 'benchmark' for 1Y/3Y/5Y/since_inception. Use null for 'NA' "
    "or missing values. IGNORE the 'Additional Benchmark' rows. Percentages as plain numbers."
)


def scheme_pages(doc: fitz.Document, fund_type: str) -> list[int]:
    """1-indexed pages that describe a single scheme."""
    pages = []
    for i in range(doc.page_count):
        low = doc[i].get_text("text").lower()
        if fund_type == "active":
            if "investment objective" in low and "fund manager" in low and "nav" in low:
                pages.append(i + 1)
        else:  # passive: detail pages carry a "Scheme Details:" block
            if "scheme details" in low and "inception date" in low:
                pages.append(i + 1)
    return pages


def _norm_plan(s):
    s = (s or "").lower()
    return "direct" if "direct" in s else "regular" if "regular" in s else None


def _norm_option(s):
    s = (s or "").lower()
    if "growth" in s:
        return "growth"
    if "idcw" in s or "dividend" in s:
        return "idcw"
    return None


def _iso_date(s):
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    return s  # keep as-is if the model didn't normalise; spot-check will catch


def to_records(ext: dict, fund_type: str, source_file: str) -> list[dict]:
    """Expand one extracted scheme into factsheet_record entries (one per variant).
    Optional fields are included only when present ('' / null / [] are dropped)."""
    holdings = [h for h in (ext.get("top_holdings") or []) if h.get("name")]
    risk = _RISK_MAP.get((ext.get("riskometer_level") or "").strip().lower())
    inception = _iso_date(ext.get("inception_date"))

    base = {"scheme_name": ext["scheme_name"], "fund_type": fund_type,
            "as_of_date": AS_OF, "source_file": source_file}
    if ext.get("aliases"):
        base["aliases"] = ext["aliases"]
    if ext.get("category"):
        base["category"] = ext["category"]
    if ext.get("benchmark"):
        base["benchmark"] = ext["benchmark"]
    if risk:
        base["riskometer_level"] = risk
    if holdings:
        base["top_holdings"] = holdings
    if ext.get("fund_managers"):
        base["fund_managers"] = ext["fund_managers"]
    if inception:
        base["inception_date"] = inception
    if ext.get("underlying_index"):
        base["underlying_index"] = ext["underlying_index"]
    if ext.get("tracking_error") is not None:
        base["tracking_error"] = ext["tracking_error"]
    if ext.get("aum_crore") is not None:
        base["aum"] = {"value": ext["aum_crore"], "unit": "INR_crore", "as_of_date": AS_OF}

    variants = ext.get("variants") or [{}]
    out = []
    for v in variants:
        rec = dict(base)
        plan, option = _norm_plan(v.get("plan")), _norm_option(v.get("option"))
        rec["record_id"] = "|".join(filter(None, [ext["scheme_name"], plan, option]))
        if plan:
            rec["plan"] = plan
        if option:
            rec["option"] = option
        if v.get("expense_ratio") is not None:
            rec["expense_ratio"] = v["expense_ratio"]
        if v.get("returns"):
            rec["returns"] = v["returns"]
        out.append(rec)
    return out


def _nkey(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def fill_passive_returns(doc: fitz.Document, records: list[dict], model_name: str) -> None:
    """Join returns from the 'ANNEXURE FOR RETURNS OF ALL THE SCHEMES' pages into the
    passive detail records (which carry no returns on their own pages)."""
    # Returns live across the annexure (grouped by FM) AND the per-scheme "Scheme Returns"
    # pages; both are the only passive pages carrying CAGR tables.
    pages = [i + 1 for i in range(doc.page_count)
             if "cagr" in doc[i].get_text("text").lower()]
    if not pages:
        return
    index = {(_nkey(r["scheme_name"]), r.get("plan"), r.get("option")): r for r in records}
    filled = 0
    for p in pages:
        text = doc[p - 1].get_text("text")
        try:
            out = model.structured(_RET_SYSTEM, f"Annexure page {p}:\n\"\"\"\n{text}\n\"\"\"",
                                    _RETURNS_ANNEX_SCHEMA, max_tokens=8192, model=model_name)
        except Exception as exc:  # noqa: BLE001
            print(f"  returns p{p}: {type(exc).__name__}: {exc}")
            continue
        for row in out.get("rows", []):
            key = (_nkey(row["scheme_name"]), _norm_plan(row.get("plan")), _norm_option(row.get("option")))
            rec = index.get(key)
            if rec and row.get("returns") and any(pp.get("scheme") is not None for pp in row["returns"].values()):
                rec["returns"] = row["returns"]
                filled += 1
    print(f"  filled returns on {filled} records from {len(pages)} annexure page(s)")


def build(which: str, model_name: str, pages_filter, limit) -> None:
    validator = Draft202012Validator(SCHEMA)
    OUT.mkdir(parents=True, exist_ok=True)

    fname, fund_type = FILES[which]
    doc = fitz.open(SRC / fname)
    pages = scheme_pages(doc, fund_type)
    if pages_filter:
        pages = [p for p in pages if p in pages_filter]
    if limit:
        pages = pages[:limit]
    print(f"[{which}] {fname}: {len(pages)} scheme page(s) -> {pages[:8]}{'...' if len(pages) > 8 else ''}")

    records, errors = [], 0
    pageset = set(pages)
    for p in pages:
        text = doc[p - 1].get_text("text")
        # Two-page schemes (common for debt): the following page holds the returns table.
        if p < doc.page_count and (p + 1) not in pageset:
            nxt = doc[p].get_text("text")
            if re.search(r"cagr|since inception", nxt, re.I):
                text += "\n\n[continued — performance table]\n" + nxt
        prompt = f"Factsheet page {p}:\n\"\"\"\n{text}\n\"\"\""
        try:
            ext = model.structured(_SYSTEM, prompt, _EXTRACT_SCHEMA, max_tokens=4096, model=model_name)
        except Exception as exc:  # noqa: BLE001
            print(f"  p{p}: extract failed — {type(exc).__name__}: {exc}")
            errors += 1
            continue
        for rec in to_records(ext, fund_type, fname):
            errs = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
            if errs:
                errors += 1
                print(f"  p{p} [{rec.get('scheme_name','?')}]: schema error — {errs[0].message[:80]}")
            else:
                records.append(rec)
        print(f"  p{p}: {ext['scheme_name']} ({len(ext.get('variants') or [])} variant(s))")

    if fund_type == "passive" and not pages_filter and not limit:
        fill_passive_returns(doc, records, model_name)

    out_path = OUT / f"{which}.json"
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{which}] wrote {len(records)} records to {out_path}  ({errors} error(s))")
    doc.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["active", "passive", "both"], default="both")
    ap.add_argument("--model", default=BATCH_MODEL, help="model for extraction (cheaper is fine)")
    ap.add_argument("--pages", help="comma-separated 1-indexed pages to restrict to (testing)")
    ap.add_argument("--limit", type=int, help="cap number of scheme pages (testing)")
    args = ap.parse_args()

    if not model.available():
        print("No ANTHROPIC_API_KEY — add one to .env first.")
        return 1
    pages_filter = {int(x) for x in args.pages.split(",")} if args.pages else None
    targets = ["active", "passive"] if args.which == "both" else [args.which]
    print(f"model: {args.model}")
    for which in targets:
        build(which, args.model, pages_filter, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
