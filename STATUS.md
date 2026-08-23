# Build status & handoff

_Last updated: 2026-08-23._ Living note so a fresh context (or a post-compaction session) can
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
- ✅ **Taxonomy + report + output UI (2026-08-22, on user request)**
  - **New rule mapping.** Area is single-select: `scheme_related` / `iap` / `others_media`
    (+ `all` baseline, never user-facing). Creative type is a conditional multi-select:
    Scheme-related -> nfo/key_visual/yield; Others & Media -> social_post/article/blog/anniversary;
    IAP -> none. Schemas first (rule enums + verdict `meta.creative_type` now an array). All 62 rules
    retagged; `article_blog` split into `article` + `blog`; judgment cases: DISC-009 ct=nfo,
    ANNIV-001/DISC-024/DISC-025 -> others_media, AUM-001/SUBST-001 -> area `all`. `build_verdict(file,
    area, creative_types)`. Scope logic centralised in `src/corpus.py` (`AREAS`, `AREA_CTYPE_OPTIONS`);
    SEGMENTS/segments-matrix generators now import it (no drift).
  - **Warn-only scheme net** (user decision): scheme name / performance detected under a non-scheme
    area -> `meta.selection_warnings`, shown in app + CLI + report. Scheme rules still stay off.
  - **Output UI.** Verdict persisted in `st.session_state` (survives every interaction). Dashboard is
    now a one-section-at-a-time switcher in priority order: Fix these -> Fact check -> Human check ->
    Advisory -> Passed. Human/Advisory carry acknowledgement checkboxes backed by durable session keys
    (survive section navigation).
  - **Clearance report** (`src/report.py`, fpdf2). Gate: 0 failures + 0 fact mismatches (ambiguous /
    assumption-matches clear but are listed) + human & advisory acks (when present) + required reviewer
    name. PDF states it is a first-pass check, not a sign-off; includes creative identity (name +
    SHA-256), scope + warnings, acknowledgements, passed rules, fact-check (assumptions listed),
    human-review + advisory items. `meta.content_sha256` added to the verdict.
    Layout is **status-forward** (fpdf2 `table()`): a colour-coded at-a-glance tile strip, banded
    section headers, and tables per section (passed rules with severity chips; fact-check with a Note
    column; a dedicated "Assumptions & caveats" box) so the reviewer sees what passed / what was
    assumed / what is still open at a glance. Presentation-only: no corpus/prompt/pipeline change, so
    no eval re-run or demo-cache regen needed.
  - Deterministic eval still 100% (44/44); scope + report + UI covered by headless AppTests.

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
- ✅ **Portfolio-facing README** — done 2026-08-08. Spec moved to `docs/PRODUCT_SPEC.md` (CLAUDE.md
  import repointed); `README.md` is now a plain-English portfolio overview (problem → what it does →
  why → mermaid architecture → worked example → tech → limitations → responsible-data → setup).
- 🟡 **Access-controlled hosted demo + API-cost control** — _code-complete 2026-08-10; awaiting user's
  dashboard steps._ **Decided (user, 2026-08-10): cached public demo + password-gated live mode; repo
  public.** Built: `scripts/build_demo_cache.py` + committed `demo_cache/*.json` (pre-computed verdicts
  for the 4 bundled samples, incl. the vision banner); `app/app.py` DEMO_MODE (samples load from cache,
  zero API) + LIVE_PASSWORD gate + per-session run cap; `.streamlit/config.toml`,
  `.streamlit/secrets.toml.example`, `docs/DEPLOY.md`. Headless AppTest confirms cached render needs no
  key and the gate appears. **Remaining (user-only, in their dashboards):** (1) set an Anthropic monthly
  spend cap; (2) flip repo to Public; (3) deploy on Streamlit Community Cloud (`app/app.py`) and paste
  secrets (key, `DEMO_MODE="true"`, a `LIVE_PASSWORD`). Regenerate cache after any corpus/prompt/sample
  change: `.venv\Scripts\python.exe scripts\build_demo_cache.py`.
  Original framing (kept for context): a public Streamlit demo that calls the Anthropic API can rack up
  cost if anyone hammers it; a working demo lands better with recruiters than a README. Key constraint:
  a GitHub repo is
  all-or-nothing public/private — you can't make *parts* of one repo public; the levers are the demo
  deployment + gating, not partial-repo visibility (splitting into public-code + private-secrets repos
  is possible but overkill). Options to weigh when we pick this up:
  1. **Cached "demo mode" (recommended).** Public demo runs the bundled samples from pre-generated
     verdicts committed as JSON — **zero API calls, zero cost**, fully public, still shows the whole UX.
     Live upload either requires the visitor to paste their own key ("bring your own key") or is off in
     demo mode. Best cost/safety.
  2. **Access-gated live demo.** Deploy on Streamlit Community Cloud behind a password/access code
     (`st.secrets`); share the code with recruiters. Uses your key, but only for invited users.
  3. **Hard cost cap + cheap tier.** Spend limit on the key, force Haiku everywhere in the demo,
     per-session rate limit. Simple but still exposed.
  4. **Private repo + read access on request.** Keep the repo private, grant recruiters read access,
     do a live walkthrough. No public exposure at all.
  Likely direction: (1) cached demo-mode public site + optional gated "live" mode; repo public with the
  README as the shop window and the demo as the closer.
- ⬜ **Real-world evaluation set** — _user to source, 2026-08-09._ Current eval set is the corpus'
  built-in pass/fail examples only. User will seek labelled, reviewed marketing material from internal
  teams to build a genuine eval file; hold a slot for it. Now a README roadmap item too.
- ⬜ **RBAC / accounts / rule-management + maker-checker** — new roadmap items (README). Login, role-based
  access, a UI to add/edit rules without touching code, and maker-checker approval on any rule-set change.

## Roadmap (post-v1)
_The forward view, consolidated. Mirrored in `README.md` (Roadmap) and `docs/PRODUCT_SPEC.md` section 11._
- **Screen-recording walkthrough** of the demo.
- **Accounts + RBAC** for teams.
- **Rule-management UI** to add or edit rules without touching code, with **maker-checker** approval on any
  rule-set change (under RBAC).
- **Scheme-document knowledge base (SID / KIM / SAI)** _(added 2026-08-23)_. Extend the section-6 KB beyond
  factsheets with the scheme's own documents, so Layer-2 fact-checks can verify the scheme / benchmark
  risk-o-meter, product suitability, and investment objective against source instead of raising
  `needs_review`. Feeds: the public SID/KIM/SAI PDFs on the AMC website (same batch-extraction pattern as the
  factsheet KB), or a compact compliance-maintained sheet of just the essential data points. Same section-6
  discipline (one record per scheme, `as_of_date`, monthly regen). Directly closes the `riskometer_level`
  null gap under Known gaps.
- **Video creative support**. Activate the `video`-tagged rules; temporal checks (flash-frame disclaimers,
  voice-over requirements).
- **More business areas** (AIF, PMS, branding, social): more rules in the same corpus.
- **Real-world evaluation set**: labelled, reviewed marketing material from the compliance team (user to
  source), to measure accuracy on genuine examples beyond the built-in pass/fail set.

## Writing/README conventions (2026-08-09)
- **No em dashes** in any generated content, ever (README, docs, commits, code comments, chat). Use
  colons/commas/parens/periods. Standing rule across all sessions.
- **README does not disclose** internal-checklist provenance, `[AMC]`/`[Sponsor Bank]` genericization, or
  "tested only with synthetic copy" (user plans to demo real material). Corpus framed as public SEBI/AMFI
  sources. Actual repo data-handling per CLAUDE.md is unchanged.
- README now carries a **"What it improves"** business-impact section (TAT, rework, bandwidth) with
  numbers framed as levers to measure, not invented figures.

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
