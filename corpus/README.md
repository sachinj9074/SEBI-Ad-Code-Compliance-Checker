# Rule corpus

The intelligence of this tool lives here, not in the model. Each rule is the encoded, citable
form of one requirement or prohibition. The shape of a rule is defined by
[`schemas/rule.schema.json`](../schemas/rule.schema.json) — **that schema is the source of truth**;
change it before changing rule structure.

## Files (`rules/*.json`, one JSON array each)

| File | Category | IDs | Count |
|---|---|---|---|
| `01_prohibitions.json` | General prohibitions (unconditional, Sixth Schedule) | PROH-001…008 | 8 |
| `02_celebrity.json` | Celebrity / prominent person | CELEB-001…002 | 2 |
| `03_disclaimers.json` | Mandatory disclaimers (verbatim `mandated_text` + fuzzy match) | DISC-001…027 | 27 |
| `04_performance.json` | Performance (Master Circular Ch. 14) | PERF-001…014 | 14 |
| `05_yield_aum_anniversary.json` | Yield / AUM / anniversary | AUM-001, YLD-001…002, ANNIV-001 | 4 |
| `06_video.json` | Video — **encoded but inactive in v1** | VID-001…003 | 3 |
| `07_amfi.json` | AMFI guidelines | AMFI-001 | 1 |
| `08_general.json` | General ad standards (from Dos & Don'ts) | XSELL-001, SUBST-001, LEGIB-001 | 3 |

**Total: 62 rules — 58 v1-active + 4 inactive (3 video + 1 video-only disclaimer). 34 automated / 28 assisted.**

With PROH-001…008 the corpus now covers **all of Sixth Schedule (a)–(j)** (clause (f) — exploiting
inexperience / excessive jargon — was the last to be added, from the internal Dos & Don'ts list).

The disclaimer set mirrors the internal checklist's Disclaimer Repository nearly one-to-one
(conditional on the content feature that requires each disclaimer). Two checklist rows — "Internal
Disclaimer" and "Distributor Specific Disclaimer" — are intentionally excluded: they govern who may
*see* material, not ad-code compliance of a creative.

## How the checker uses these (two-stage, README §3)

1. **Filter** the corpus to the run: keep rules whose `applies_to` intersects the selected areas
   (`all` matches any) **and** whose `creative_type` includes the selected creative type.
2. **Stage A — feature detection:** identify what the creative contains (performance, named
   stocks/sectors, SIP, AUM, yield/YTM, prominent person, language…).
3. **Stage B — requirement checks:** unconditional rules always run; conditional rules run only
   when their `trigger.feature` was detected.
4. Each rule returns **pass / fail / needs_review / not_applicable**. `check_type: assisted` rules
   raise **needs_review** rather than pretend to decide (celebrity ID, "misleading", risk-o-meter
   legibility, month-end dating, completeness of disclosures).

### v1-active vs inactive
Video is encoded now but inactive in v1. `ACTIVE_CREATIVE_TYPES` in
[`scripts/validate_corpus.py`](../scripts/validate_corpus.py) is the single switch — the checker
does not offer `video` as a creative type yet, so the 3 VID rules never run. Activating video is a
targeted change, not a rebuild.

## Provenance and genericization
- `provenance` is recorded honestly on every rule: `sebi`, `amfi`, `internal_policy`, or a
  combination — so a regulation change vs. an internal-policy change stays distinguishable.
- All AMC-identifying text is genericized per [`GENERICIZATION.md`](GENERICIZATION.md); public
  SEBI/AMFI verbatim texts (the 14-word warning, the Hindi warning) are kept exactly.

## Evaluation seed
Every rule carries one **pass** and one **fail** example. That is the starting eval set, handed
over for free by the corpus work (README §8); the Day-1 checker + `evals/` script score against it.

## Validate
```
.venv\Scripts\python.exe scripts/validate_corpus.py
```
Checks schema conformance, unique `rule_id`s, and prints the summary above. Run after any change.

## Review status
Citations (`source_clause`, `source_date`) are grounded in the actual Sixth Schedule and Master
Circular Chapter 14 text in `sources/`, but **clause-letter precision and severity/`check_type`
calls should be reviewed rule by rule** — that human review is the judgment work (README §10).
