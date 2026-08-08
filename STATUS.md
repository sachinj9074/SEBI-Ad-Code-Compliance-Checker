# Build status & handoff

_Last updated: 2026-08-07._ Living note so a fresh context (or a post-compaction session) can
resume instantly. The README is the product spec; CLAUDE.md is the working rules; this file is
"where we are and what's next." Read those three, then `git log --oneline`.

## Progress
- ✅ **Setup** — repo, 3 JSON schemas (`schemas/`), sources fetched (`sources/`, see SOURCES.md).
- ✅ **Day 1** — 62-rule corpus (`corpus/rules/`), full Sixth Schedule (a)–(j) + checklist +
  Dos-and-Don'ts; segmentation map (`corpus/SEGMENTS.md`); pass-one checker (`src/`) + eval.
  Layer-1 deterministic eval = **100%** (44/44). Review sheet artifact generated from the corpus.
- ✅ **Day 2 AM** — factsheet KB (`data/factsheet_kb/active.json` 163 rec / 84 schemes,
  `passive.json` 105 rec / 37 schemes) + fact-check layer (`src/factcheck.py`, Layer 2).
- ✅ **Day 2 PM** — vision ingestion (`src/vision.py`): image/banner, scanned-PDF (rasterise),
  carousel; legibility + risk-o-meter + prominent-person judgments feed the rules.
- ✅ **Gaps closed** — scheme-match (AMC-stripped token_sort_ratio); passive returns joined
  (57/105 Growth variants); image eval case (`evals/run_eval.py --image`).
- ✅ **Day 3 — COMPLETE**
  - ✅ **Layer 3 advisory** (`src/advisory.py`) — second model pass, sets the rules aside (never
    sees Layer-1), flags misleading/exaggerated/off-tone; unscored, fenced; wired into
    `build_verdict` + CLI. Bounded to ≤8 concise notes at `max_tokens=4096` (a tight ceiling
    truncated the JSON and silently returned 0 notes — fixed).
  - ✅ **Streamlit UI** (`app/app.py` controller + `app/render.py` renderers) — upload → area
    multiselect + creative-type select → one-page verdict with the three layers rendered as
    separate sections + show-back. Display-only (calls `build_verdict`). Verified live + via
    streamlit AppTest. (`app.py` uses a sibling `import render`, not `from app import …` — under
    `streamlit run` the script itself is module `app`, so that form is a circular import.)
  - ✅ **End-to-end test** — three generic samples through the full pipeline;
    self-serve sample picker added to the UI. Eval: 100% + image case ✅.
- ✅ **Refinements (2026-08-08, on user feedback from the live UI)**
  - Tiered models (Haiku + Sonnet) — see Resolved decisions.
  - Reclassified 13 model-judgeable rules `assisted`→`automated` so the model screens them:
    clean-sample needs-review **12 → 2**, advisory **6 → 0**; violations FAIL 11 → 16,
    needs-review 19 → 10, advisory 8 → 3. Kept 12 truly un-decidable rules human-only.
  - Plain-language rule `description` on every result (verdict schema + checker + UI).
  - Advisory: high-bar rewrite (material investor harm only; excludes NFO urgency, low-ticket
    SIP, puffery, upbeat tone).
  - UI overhaul: headline verdict, Must-fix / Human-check labels, leaner show-back.
  - Precision: `market_cap_terms` no longer fires on "Cap" in a scheme name; DISC-010 start-
    placement scoped to audio-visual; LEGIB-001 → not_applicable on text.
  - Eval re-run: 100% deterministic (44/44); 98.9% with `--model` (Sonnet judging 24 rules).

## Architecture (where things live)
- `schemas/` — rule / verdict / factsheet_record JSON schemas (source of truth). `scripts/validate_*.py`.
- `corpus/rules/*.json` — the 62 rules. `scripts/build_review_sheet.py`, `scripts/build_segments.py`.
- `src/` — pipeline: `extract` (docx/pdf/image/carousel) → `features` (Stage A) + `vision` →
  `checker` (Stage B, 3-layer verdict) → `factcheck` (Layer 2). `model.py` = one Anthropic client.
  `cli.py` = `python -m src.cli <file> --areas mf_scheme --type general_kv`.
- `data/factsheet_kb/` — the KB (`scripts/build_factsheet_kb.py`). `evals/` — the eval + cases.
- `samples/` — generic test creatives (violations, wrong-return, banner). `app/` — Streamlit (Day 3, TBD).

## Resolved decisions
- **Model = Anthropic Claude, tiered on cost** (changed 2026-08-08 on user feedback — Opus 5 was
  too costly). `src/model.py`: **FAST = `claude-haiku-4-5`** for feature detection + claim extraction;
  **JUDGMENT = `claude-sonnet-5`** for rule judgment, advisory, and vision. Factsheet **batch**
  extraction also Haiku. Overridable via `ANTHROPIC_FAST_MODEL` / `ANTHROPIC_MODEL`. All calls go
  through `src/model.py`.
- **Public + genericize repo.** Internal checklist is local-only/gitignored; committed corpus uses
  `[AMC]`/`[Sponsor Bank]` placeholders (`corpus/GENERICIZATION.md`). **Factsheets are public → KB
  committed with real data.**
- **Severity enum** = critical/high/medium/low.

## Environment gotchas
- Windows 11, **PowerShell primary**; Python 3.12 venv at `.venv`. Run python as `.venv\Scripts\python.exe`.
- The **shell has a stale/invalid `ANTHROPIC_API_KEY`**; the real key is in `.env`, and
  `src/model.py` loads `.env` with `override=True` so it wins. `scripts/check_key.py` validates (free).
- Model errors degrade gracefully (feature detection → heuristic; automated rules → needs_review;
  fact-check → empty) — the run never crashes.

## Known gaps / follow-ups (documented, non-blocking)
- `riskometer_level` null in the KB (graphic dial, not text) — a vision pass could fill it.
- Passive **IDCW** return variants stay null (factsheet publishes only Growth returns).
- 2 active KB records dropped on schema-validation edge cases (163 written).

## Parked to-dos (do before flipping the GitHub repo to public)
- **Portfolio-facing README.** _Parked by user 2026-08-07._ The current `README.md` reads as a
  technical build spec — too dense for recruiters. Rewrite it in the style of the invoice-extractor
  repo: problem-first, plain-language, "what it does", design highlights, screenshots/demo. **Do NOT
  just overwrite `README.md`** — it is the product spec that `CLAUDE.md` imports via `@README.md`.
  Plan: move the spec to `docs/PRODUCT_SPEC.md` (or `SPEC.md`), repoint the `CLAUDE.md` import at it,
  then make `README.md` the portfolio landing page. Keep the three-layer story front and centre.

## Next steps — Day 3 ✅ COMPLETE
1. ✅ **Layer 3 advisory** — done (`src/advisory.py`, wired into `build_verdict` + CLI).
2. ✅ **Streamlit UI** — done (`app/app.py` + `app/render.py`).
3. ✅ **End-to-end test** — done (clean / violations / wrong-return; eval 100% + image ✅).

**The 3-day build is done.** Remaining before flipping the repo public: the parked
portfolio-README rewrite (see "Parked to-dos" above), plus optionally a UI screenshot for it.

## Commands
```
.venv\Scripts\python.exe evals\run_eval.py                 # Layer-1 deterministic eval (no key)
.venv\Scripts\python.exe evals\run_eval.py --image         # + vision case (needs key)
.venv\Scripts\python.exe -m src.cli samples\sample_with_violations.txt --areas mf_scheme --type general_kv
.venv\Scripts\python.exe scripts\build_factsheet_kb.py --which both   # rebuild KB (monthly)
.venv\Scripts\python.exe -m streamlit run app\app.py                  # launch the UI (Day 3)
```
