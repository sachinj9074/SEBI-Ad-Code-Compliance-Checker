"""Load and validate the rule corpus against schemas/rule.schema.json.

Checks: every rule conforms to the schema, rule_ids are unique, conditional
triggers name a feature, and each rule ships a pass + fail example. Prints a
summary (counts by category, provenance, check_type, and v1-active vs inactive).

Run:  .venv\\Scripts\\python.exe scripts/validate_corpus.py
Exits non-zero on any failure so it can gate commits / CI.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "corpus" / "rules"
SCHEMA = ROOT / "schemas" / "rule.schema.json"

# Creative types the v1 checker actually offers (video is encoded but inactive).
ACTIVE_CREATIVE_TYPES = {"general_kv", "anniversary", "yield", "article_blog", "social_post"}


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    schema = load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    rule_files = sorted(RULES_DIR.glob("*.json"))
    if not rule_files:
        print(f"[FAIL] no rule files in {RULES_DIR}")
        return 1

    rules: list[tuple[str, dict]] = []
    failures = 0
    for f in rule_files:
        data = load(f)
        if not isinstance(data, list):
            print(f"[FAIL] {f.name}: top level must be a JSON array")
            failures += 1
            continue
        for rule in data:
            rules.append((f.name, rule))

    ids = Counter(r.get("rule_id", "<missing>") for _, r in rules)
    dupes = [rid for rid, n in ids.items() if n > 1]
    if dupes:
        print(f"[FAIL] duplicate rule_id(s): {', '.join(dupes)}")
        failures += 1

    by_provenance: Counter = Counter()
    by_check_type: Counter = Counter()
    active = inactive = 0

    for fname, rule in rules:
        rid = rule.get("rule_id", "<missing>")
        errs = sorted(validator.iter_errors(rule), key=lambda e: list(e.path))
        if errs:
            failures += 1
            print(f"[FAIL] {rid} ({fname}) does not conform:")
            for e in errs:
                loc = "/".join(str(p) for p in e.path) or "<root>"
                print(f"       - {loc}: {e.message}")
            continue
        for p in rule.get("provenance", []):
            by_provenance[p] += 1
        by_check_type[rule["check_type"]] += 1
        if set(rule["creative_type"]) & ACTIVE_CREATIVE_TYPES:
            active += 1
        else:
            inactive += 1

    print("-" * 56)
    print(f"rule files      : {len(rule_files)}")
    print(f"rules total     : {len(rules)}")
    print(f"  v1-active     : {active}")
    print(f"  inactive(video): {inactive}")
    print(f"check_type      : " + ", ".join(f"{k}={v}" for k, v in sorted(by_check_type.items())))
    print(f"provenance      : " + ", ".join(f"{k}={v}" for k, v in sorted(by_provenance.items())))
    print("-" * 56)
    if failures:
        print(f"FAILED: {failures} problem(s).")
        return 1
    print("All rules conform to rule.schema.json; rule_ids unique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
