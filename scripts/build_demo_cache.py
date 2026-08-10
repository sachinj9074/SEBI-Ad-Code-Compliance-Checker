"""Pre-generate verdicts for the bundled demo samples.

The hosted public demo runs in DEMO_MODE (see app/app.py): when a visitor picks
a bundled sample, the app loads the verdict from demo_cache/ instead of calling
the model. That keeps the public surface at zero API cost while still showing
real, full-quality output.

Run this once locally (with a valid ANTHROPIC_API_KEY in .env) after any change
to the samples, the corpus, or the pipeline, then commit the demo_cache/ files:

    .venv\\Scripts\\python.exe scripts\\build_demo_cache.py

Uses the same default area/type a visitor gets when they pick a sample.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import model  # noqa: E402
from src.checker import build_verdict  # noqa: E402

AREAS = ["mf_scheme"]
CTYPE = "general_kv"

SAMPLES = [
    "sample_clean.txt",
    "sample_with_violations.txt",
    "sample_wrong_return.txt",
    "sample_banner.png",
]

OUT = ROOT / "demo_cache"


def main() -> int:
    if not model.available():
        print("ERROR: no ANTHROPIC_API_KEY found. The cache would be deterministic-only,")
        print("which is not what the demo should show. Add the key to .env and retry.")
        return 1

    OUT.mkdir(exist_ok=True)
    for name in SAMPLES:
        src = ROOT / "samples" / name
        if not src.exists():
            print(f"skip (missing sample): {name}")
            continue
        print(f"generating: {name} ...", flush=True)
        verdict = build_verdict(str(src), AREAS, CTYPE)
        # Stamp as pre-computed and strip any local temp path from the filename.
        verdict.setdefault("meta", {})["demo_cached"] = True
        verdict["meta"]["source_filename"] = name
        dest = OUT / f"{Path(name).stem}.json"
        dest.write_text(
            json.dumps(verdict, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"  wrote {dest.relative_to(ROOT)}")
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
