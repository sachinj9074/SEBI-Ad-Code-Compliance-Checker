"""Pass-one checker CLI.

    python -m src.cli <creative-file> --areas mf_scheme --type general_kv [--json out.json]

Prints the summary strip, failed / needs-review rules grouped by trigger, and
the show-back (extracted text + confidence). DOCX / text-PDF in v1.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import model
from .checker import build_verdict
from .corpus import ACTIVE_CREATIVE_TYPES

AREAS = ["all", "mf_scheme", "nfo", "iap"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SEBI ad-code pass-one checker")
    ap.add_argument("file", help="creative file (.docx, .pdf, .txt)")
    ap.add_argument("--areas", nargs="+", default=["mf_scheme"], choices=AREAS,
                    help="business area(s) the creative relates to")
    ap.add_argument("--type", dest="creative_type", default="general_kv",
                    choices=sorted(ACTIVE_CREATIVE_TYPES), help="creative type")
    ap.add_argument("--json", dest="json_out", help="also write the full verdict JSON here")
    args = ap.parse_args(argv)

    verdict = build_verdict(args.file, args.areas, args.creative_type)
    _print_report(verdict)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(verdict, fh, ensure_ascii=False, indent=2)
        print(f"\nFull verdict written to {args.json_out}")
    return 0


def _print_report(v: dict) -> None:
    s = v["summary_strip"]
    ex = v["extraction"]
    print("=" * 68)
    print(f"  {v['meta']['source_filename']}  [{', '.join(v['meta']['areas_selected'])}"
          f" / {v['meta']['creative_type']}]")
    print(f"  model: {v['meta']['model_used']}")
    print("=" * 68)
    print(f"  rules run {s['rules_run']} | pass {s['passed']} | FAIL {s['failed']}"
          f" | needs-review {s['needs_review']} | fact-mismatch {s['fact_mismatches']}"
          f" | advisory {s['advisory_notes']}")
    if not model.available():
        print("  (no API key: feature detection is heuristic; automated non-disclaimer "
              "rules deferred to needs-review)")

    triggered = {}
    for r in v["rule_layer"]["results"]:
        if r["verdict"] in ("fail", "needs_review"):
            triggered.setdefault(r.get("triggered_by", "unconditional"), []).append(r)

    for feat, items in sorted(triggered.items()):
        print(f"\n— triggered by: {feat} —")
        for r in items:
            tag = "FAIL" if r["verdict"] == "fail" else "review"
            print(f"  [{tag}] {r['rule_id']} ({r['severity']}) — {r['source_clause'][:70]}")
            if r.get("explanation"):
                print(f"         {r['explanation']}")
            if r.get("suggested_rewrite"):
                print(f"         fix: {r['suggested_rewrite'][:90]}")

    fc = v["fact_check_layer"]["results"]
    if fc:
        print("\n— fact-check (Layer 2 — factsheet verification, separate from the compliance score) —")
        for r in fc:
            print(f"  [{r['verdict']}] {r['claim_text'][:66]}")
            print(f"         claimed: {r.get('claimed_value','?')}  |  factsheet: "
                  f"{r.get('factsheet_value','?')}  (as of {r.get('as_of_date','?')})")
            if r.get("scheme_matched"):
                print(f"         scheme: {r['scheme_matched']}")
            if r.get("assumption"):
                print(f"         assumption: {r['assumption']}")

    adv = v["advisory_layer"]["notes"]
    if adv:
        print("\n— advisory (Layer 3 — unscored; does not affect the pass/fail summary) —")
        for n in adv:
            tag = f"[{n['area']}] " if n.get("area") else ""
            print(f"  • {tag}{n['note']}")

    print("\n— show-back (extracted content, confidence "
          f"{ex['confidence']:.0%}, {ex['source_kind']}) —")
    if ex.get("languages_detected"):
        print("  languages: " + ", ".join(ex["languages_detected"]))
    if ex.get("layout_notes"):
        print("  layout: " + ex["layout_notes"][:130])
    if ex.get("legibility_notes"):
        print("  legibility: " + ex["legibility_notes"][:130])
    body = ex["extracted_text"].strip()
    print("  " + (body[:300] + "…" if len(body) > 300 else body or "(no text extracted)"))
    for w in ex["warnings"]:
        print(f"  ! {w}")


if __name__ == "__main__":
    sys.exit(main())
