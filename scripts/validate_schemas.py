"""Validate the three source-of-truth schemas and their example fixtures.

Run:  .venv\\Scripts\\python.exe scripts/validate_schemas.py
Exits non-zero on any failure so it can gate commits / CI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_DIR = SCHEMA_DIR / "examples"

# schema file -> example fixture that must conform to it
PAIRS = {
    "rule.schema.json": "rule.example.json",
    "verdict.schema.json": "verdict.example.json",
    "factsheet_record.schema.json": "factsheet_record.example.json",
}


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    failures = 0
    for schema_name, example_name in PAIRS.items():
        schema = load(SCHEMA_DIR / schema_name)

        # 1. the schema itself must be a valid Draft 2020-12 schema
        try:
            Draft202012Validator.check_schema(schema)
            print(f"[ok]   schema valid       : {schema_name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] schema invalid     : {schema_name}\n       {exc}")
            continue

        # 2. the example fixture must conform to it
        example = load(EXAMPLE_DIR / example_name)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(example),
            key=lambda e: e.path,
        )
        if errors:
            failures += 1
            print(f"[FAIL] example non-conform: {example_name}")
            for err in errors:
                loc = "/".join(str(p) for p in err.path) or "<root>"
                print(f"       - {loc}: {err.message}")
        else:
            print(f"[ok]   example conforms    : {example_name}")

    print("-" * 48)
    if failures:
        print(f"FAILED: {failures} problem(s).")
        return 1
    print("All schemas valid and all examples conform.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
