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
            assisted_ok += (pass_v == "needs_review") + (fail_v == "needs_review")
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
    if acc < FLOOR:
        print(f"FAIL: deterministic accuracy {acc:.1%} < floor {FLOOR:.0%}")
        return 1
    print(f"OK: deterministic accuracy {acc:.1%} (floor {FLOOR:.0%}); "
          f"assisted behaviour {'clean' if assisted_ok == assisted_total else 'CHECK'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
