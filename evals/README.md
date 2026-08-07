# Evals

Every rule ships a **pass** and a **fail** example (README §8) — that is the seed eval set,
handed over for free by the corpus work. The eval runs the real check engine against those
examples and scores the deterministic layer.

## Run
```
.venv\Scripts\python.exe evals/run_eval.py            # deterministic layer (no API key needed)
.venv\Scripts\python.exe evals/run_eval.py --model    # also score automated non-disclaimer rules (needs a valid key)
.venv\Scripts\python.exe evals/run_eval.py --image    # also run the vision case (sample banner; needs a valid key)
```

The script exits non-zero if deterministic accuracy drops below the 95% floor, so it can gate commits.

## What is scored
- **mandated_text rules** — pass example must PASS, fail example must FAIL (verbatim disclaimer presence, fuzzy-matched). Fully deterministic.
- **assisted rules** — both examples must raise `needs_review` (the tool never pretends to decide). Behaviour check.
- **automated non-disclaimer rules** — need the model; scored only with `--model` + a valid key.

## Recorded numbers
Run the eval after any corpus or prompt change and add a line here.

| Date | Deterministic accuracy | Notes |
|---|---|---|
| 2026-08-07 | **100.0%** (44/44) | assisted rules raise `needs_review` on 50/50 examples; 11 automated non-disclaimer rules await the model |
| 2026-08-07 | image case ✅ | `--image`: banner read as image; LEGIB-001 FAIL + DISC-001 needs_review on the illegible warning |
| 2026-08-07 | **100.0%** (44/44) + image ✅ | Day 3 complete (advisory layer + UI added — both outside the scored layer, no change expected or seen). E2E: clean sample 0 FAIL / 0 mismatch; violations 11 FAIL / 3 mismatch; wrong-return 6 FAIL / 1 mismatch |
