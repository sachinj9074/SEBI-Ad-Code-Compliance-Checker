"""One-command eval (README §8).

Each rule ships a pass + fail example — that is the seed eval set. This runs the
real check engine against every active rule's examples (with the rule's trigger
feature forced present) and scores the deterministic layer:

  * mandated_text rules  -> pass example must PASS, fail example must FAIL  (scored)
  * assisted rules       -> both examples must raise needs_review           (behaviour check)
  * automated non-disclaimer rules -> need the model; scored only with --model + a key

Run:  .venv\\Scripts\\python.exe evals/run_eval.py
Exits non-zero if the deterministic accuracy drops below the recorded floor.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import model  # noqa: E402
from src.checker import check_rule  # noqa: E402
from src.corpus import load_rules  # noqa: E402


def _present_for(rule: dict) -> set[str]:
    trig = rule["trigger"]
    return {trig["feature"]} if trig["type"] == "conditional" else set()


def image_eval() -> bool:
    """Vision case (README §10): the sample banner has a present-but-illegible warning.
    Needs the vision model + a valid key. Asserts the legibility judgments fire."""
    from src.checker import build_verdict  # local import: only needed with --image

    banner = ROOT / "samples" / "sample_banner.png"
    if not banner.exists():
        print("\nimage eval: samples/sample_banner.png missing (run scripts/make_sample_banner.py)")
        return True
    if not model.available():
        print("\nimage eval: needs a valid ANTHROPIC_API_KEY (skipped)")
        return True

    v = build_verdict(str(banner), "scheme_related", ["key_visual"])
    rl = {r["rule_id"]: r["verdict"] for r in v["rule_layer"]["results"]}
    checks = [
        ("source read as image", v["extraction"]["source_kind"] == "image"),
        ("LEGIB-001 FAIL (disclaimer illegible)", rl.get("LEGIB-001") == "fail"),
        ("DISC-001 needs_review (present but illegible)", rl.get("DISC-001") == "needs_review"),
    ]
    print("\n=== image eval (sample_banner.png — the case OCR would miss) ===")
    ok = True
    for label, passed in checks:
        print(f"  [{'ok' if passed else 'FAIL'}] {label}")
        ok = ok and passed
    return ok


def main() -> int:
    use_model = "--model" in sys.argv and model.available()
    rules = load_rules()

    det_correct = det_total = 0
    assisted_ok = assisted_total = 0
    model_required = 0
    mismatches: list[str] = []

    def verdicts(rule):
        present = _present_for(rule)
        return (
            check_rule(rule, rule["examples"]["pass"]["content"], present)["verdict"],
            check_rule(rule, rule["examples"]["fail"]["content"], present)["verdict"],
        )

    for rule in rules:
        # Deterministic rows (mandated_text, assisted) never call the model.
        # Automated non-disclaimer rows are only exercised with --model + a valid key.
        if "mandated_text" in rule:
            pass_v, fail_v = verdicts(rule)
            det_total += 2
            if pass_v == "pass":
                det_correct += 1
            else:
                mismatches.append(f"{rule['rule_id']}: pass-example -> {pass_v} (want pass)")
            if fail_v == "fail":
                det_correct += 1
            else:
                mismatches.append(f"{rule['rule_id']}: fail-example -> {fail_v} (want fail)")
        elif rule["check_type"] == "assisted":
            pass_v, fail_v = verdicts(rule)
            assisted_total += 2
            # The tool must never pretend to decide an assisted rule: needs_review,
            # or not_applicable for the vision-only ones (e.g. LEGIB-001) when run on
            # text with no image to judge.
            ok = {"needs_review", "not_applicable"}
            assisted_ok += (pass_v in ok) + (fail_v in ok)
        else:
            model_required += 1  # automated, no mandated_text
            if use_model:
                pass_v, fail_v = verdicts(rule)
                det_total += 2
                det_correct += pass_v in ("pass", "needs_review")
                det_correct += fail_v in ("fail", "needs_review")

    acc = det_correct / det_total if det_total else 0.0
    print("-" * 60)
    print(f"rules evaluated        : {len(rules)}")
    print(f"deterministic cases    : {det_total}  ({det_correct} correct)")
    print(f"deterministic accuracy : {acc:.1%}")
    print(f"assisted rules         : {assisted_total // 2}  "
          f"(needs_review raised on {assisted_ok}/{assisted_total} examples)")
    print(f"model-required rules   : {model_required}"
          f"{'  (scored above, --model)' if use_model else '  (run with --model + API key to score)'}")
    if mismatches:
        print("\nmismatches:")
        for m in mismatches:
            print("  -", m)
    print("-" * 60)

    FLOOR = 0.95
    det_ok = acc >= FLOOR
    if not det_ok:
        print(f"FAIL: deterministic accuracy {acc:.1%} < floor {FLOOR:.0%}")
    else:
        print(f"OK: deterministic accuracy {acc:.1%} (floor {FLOOR:.0%}); "
              f"assisted behaviour {'clean' if assisted_ok == assisted_total else 'CHECK'}.")

    img_ok = image_eval() if "--image" in sys.argv else True
    return 0 if (det_ok and img_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
