> **Note:** This is the product spec / build bible, the single source of truth for *what* the project is and *why*. It was the repo's original README; the top-level `README.md` is now a plain-English portfolio overview, and `CLAUDE.md` imports this file.

# SEBI Ad Code Compliance Checker

A tool that screens mutual fund marketing material against the SEBI advertisement code, AMFI guidelines, and the internal compliance checklist, verifies factual claims against the published fund factsheets, and returns each flagged item with the governing rule cited, a severity level, and a compliant rewrite.

This README is the single source of truth for the build. It supersedes all earlier drafts. Read it top to bottom before writing code.

---

## 1. Problem statement

Marketing creatives, distributor material and social posts are manually screened against the SEBI advertisement code by a small compliance team. Reviews run sequentially over email, so turnaround is unpredictable and avoidable issues surface late, forcing rework close to launch dates.

## 2. What it does

The user uploads a creative, selects which business areas it relates to and what type of creative it is, and gets back a structured verdict. The verdict has three separately reported layers: scored rule checks, factsheet fact-checks, and unscored advisory observations. Each flag names the rule or data point involved, its severity, its source, and a suggested compliant rewrite. The intent is that creators self-correct before formal compliance review.

Efficiency levers: review turnaround time, rework cycles per creative, and compliance bandwidth shifted from routine screening to judgment calls.

---

## 3. Core architecture: three separated layers

The checker produces three kinds of output. Keeping them separate is a design decision, not an implementation detail. Never merge them into one prompt, one score, or one report section.

### Layer 1: rules-as-checklist (the scored spine)

Deterministic in intent, citable to a source, scoreable against test cases. This is the layer compliance trusts.

Pass one runs in two stages:

- **Stage A, feature detection.** Identify what the creative contains: performance figures, named stocks, named sectors, SIP references, AUM figures, yield/YTM figures, a prominent person, scheme names, language(s) used.
- **Stage B, requirement checks.** Each detected feature activates its conditional rules (performance shown activates the full performance requirement set; stocks named activates the stock disclaimer; AUM shown activates the AUM link requirement; and so on). Unconditional rules for the selected areas and creative type always run.

This two-stage structure exists because most rules in the compliance checklist are conditional: "if X appears, then Y is required." It also produces better output: the user sees which features triggered which rules.

Every rule check returns one of four verdicts: **pass**, **fail**, **needs_review**, or **not_applicable**. needs_review exists because some rules are not machine-decidable (celebrity identification, MCR consistency, approved-script matching). The tool detects the triggering condition and raises a flag for a human, instead of pretending it can decide. Rules carry a `check_type` of `automated` or `assisted` to make this explicit.

### Layer 2: factsheet fact-check (separate section, separate severity model)

Factual claims in the creative (returns, AUM, holdings, objectives, riskometer level) are verified against the structured knowledge base built from the published factsheets (section 6). A mismatch is a factual error, not an ad-code violation: it is reported in its own section, stamped with the factsheet as-of date, and never blended into the compliance score.

### Layer 3: open-ended judgment (advisory, unscored)

After the checks run, a second model pass sets the rules aside and surfaces anything else that reads as misleading, exaggerated, or off-tone. Output is labelled advisory, is never scored, and never affects the pass/fail summary. It is a "you may also want to look at this" section.

On any status slide, describe the tool honestly: one deterministic scored layer, one factual verification layer, one advisory layer, clearly separated.

---

## 4. The rule corpus (this is the real work)

The intelligence of this tool lives in the corpus, not the model.

### Three sources, three roles

- **Internal compliance checklist (xlsx, 5 sheets).** Ground truth for what gets flagged in practice. The sheets: Disclaimer Repository (~30 verbatim mandated disclaimer texts, including the Hindi standard disclaimer), Performance Checklist (~19 conditions plus merger cases), Celebrity Checklist (definition plus the caricature/meme prohibition), KV/Anniversary/Yield creative requirements, Video Checkpoints. Day 1 starts by converting these rows into the rule schema.
- **SEBI sources.** The Sixth Schedule (Advertisement Code) of the SEBI (Mutual Funds) Regulations, 1996, and the advertisement chapter of the current Master Circular for Mutual Funds dated March 20, 2026, which superseded the June 27, 2024 master circular. These provide the citable clause for each rule and the general prohibition rules the checklist omits because reviewers carry them in their heads: no assured or guaranteed returns language, no misleading or exaggerated claims, no superlatives without substantiation. Those prohibitions should be among the first rules in the corpus.
- **AMFI guidelines and circulars.** Current advertisement-related guidance, same role as the SEBI sources.

Any condition present in the public sources but absent from the internal checklist is a finding worth recording: it is evidence the tool adds value beyond encoding existing habit.

### Rule schema

Each rule carries:

- `rule_id`
- `description` (plain language)
- `trigger` (unconditional, or the content feature that activates it)
- `applies_to` (area tags: `all`, `mf_scheme`, `iap`, `non_iap`, `nfo`, `aif`, `pms`, `branding`, `social_media`; v1 populates only `all`, `mf_scheme`, `nfo`)
- `creative_type` (tags: `general_kv`, `anniversary`, `yield`, `article_blog`, `social_post`, `video`; video rules are encoded now but inactive in v1)
- `severity`
- `check_type` (`automated` or `assisted`)
- `source_clause` (the governing clause or circular reference)
- `provenance` (`sebi`, `amfi`, `internal_policy`, or a combination; several checklist items such as the sponsor disclaimer wording and the app-rating rule are internal policy, and tagging this matters when regulation changes versus when internal policy changes)
- `mandated_text` (for disclaimer-presence rules: the verbatim required text, matched fuzzily with a similarity threshold to tolerate line-break and punctuation drift)
- one pass example and one fail example

### Verbatim disclaimers

The Disclaimer Repository turns many checks into near-deterministic presence and fuzzy-match tests. The matcher must handle Devanagari: detect the creative's language(s) and check for the matching disclaimer version (Hindi creative requires the Hindi standard disclaimer; the video sheet's Hinglish rules apply when video comes into scope).

### Provenance and supersession

Record provenance on every rule from the start. SEBI circulars supersede each other; the March 2026 master circular replacing the June 2024 one during this project's design phase is the live proof. Note the source document date on every rule and confirm nothing newer overrides it. A SEBI consultation paper proposing a common advertisement code across regulated entities is in circulation; if adopted, the celebrity rules change. Watch, do not act.

### Corpus sizing

Around 25 well-specified rules is the honest v1 target given how specific the performance sheet is. Depth over breadth. Most rules are cheap deterministic checks, so the count is not a cost concern.

---

## 5. Input handling

Inputs: a file upload, an area multi-select, and a creative-type single-select. The two selectors filter the corpus so only relevant rules run.

### Formats, by difficulty tier

- **DOCX.** Easy. Build against this first.
- **PDF, text-based.** Easy once the text layer is read.
- **PDF, scanned or image-exported.** No text layer. Needs vision. The pipeline must detect which kind of PDF it has and branch; the extension does not tell you.
- **Static images and banners.** The important case. See below.
- **Carousels.** Handled as a multi-image upload; each frame runs through the image pipeline, results grouped per frame.

### Images: use vision, not plain OCR

A large share of ad-code violations in creatives are visual rather than textual: a disclaimer present but unreadably small, the standard warning buried or low-contrast, the risk-o-meter missing, wrong, or illegible. OCR flattens a 4-point illegible disclaimer and a clear one into the same string, and the violation vanishes. Use a vision model that reads the creative as a creative: ask both "what does this say" and "is the mandatory disclaimer present and legibly sized." Return structured fields with confidence, including layout, legibility, and prominent-person detection (which feeds the celebrity needs_review flag). The vision model must read Devanagari.

### Extraction errors propagate: two cheap defences

1. Surface extraction confidence. Low-confidence extraction is flagged, not silently trusted.
2. Show the extracted content back to the user alongside the verdict, so a garbled extraction is caught in one glance.

These are not optional polish. They prevent the worst class of error: authoritatively checking text the creative never contained.

---

## 6. Knowledge base: the factsheet JSON

Factual claims are verified against a structured knowledge base, not against the factsheet PDFs at query time, and not via embeddings/RAG. The claims that matter are numbers in tables, which is exactly where vector retrieval is weakest and hardest to debug.

### Sources

Two published factsheets, downloaded from the public website (never internal versions): the active funds factsheet (~170 pages) and the passive funds factsheet (~65 pages). Both are clean text-layer PDFs; small font size is irrelevant to text extraction.

### Build

A one-time batch job (regenerated monthly) walks each PDF in page chunks and emits one JSON record per scheme:

- Shared core: scheme name and aliases, category, plan/option, returns (1Y/3Y/5Y/since inception, scheme vs benchmark), riskometer level, benchmark, AUM, top holdings, fund manager(s), inception date, `as_of_date`, `source_file`
- Passive extras: underlying index, tracking error, tracking difference, expense ratio

Spot-check five schemes per file by hand against the PDF before trusting the extraction. If any table garbles under text extraction, rasterize just those pages and read them with vision.

### Fact-check pass

Extract claims from the creative, look them up deterministically in the JSON, compare. Every mismatch is citable ("creative says 15%, factsheet as of 30 Jun 2026 says 12.4% for direct-growth 1Y").

Handling built in:

- **As-of drift.** Every verdict is stamped with the factsheet date. The JSON is a monthly regeneration job.
- **Ambiguous claims.** "15% last year" does not specify plan, option, or calculation basis. The claim extractor outputs what the claim did not specify, and those comparisons are marked "matches under assumption X" rather than a hard pass or fail.

---

## 7. Output format

Streamlit, one page, built for non-technical users.

- **Summary strip:** N rules run for the selected areas and creative type, passed, failed, needs review, fact mismatches, advisory notes.
- **Failed and needs-review rules, expanded:** the offending line or element, the rule and its governing clause, severity, and a suggested compliant rewrite. Grouped by the feature that triggered them ("your creative shows performance, so these 9 rules applied").
- **Fact-check section:** each claim, the factsheet value, the as-of date, and any assumption the comparison rests on.
- **Advisory section:** clearly fenced, no verdicts.
- **Show-back panel:** the extracted content and extraction confidence, visible alongside the verdict throughout.

---

## 8. Evaluation approach

Evaluation is a first-class deliverable. Every rule carries a pass and a fail example: that is the starting eval set, handed over for free by the corpus work. Score the checker against it with a one-command script: how often it flags true violations, passes clean copy, and wrongly flags clean copy. Extend the set with image cases once vision ingestion lands. Track the number across every corpus and prompt change so improvements are measured decisions.

---

## 9. Tech and hosting

- **Personal machine, not the work laptop.** Standalone prototype outside the office stack.
- **Direct model API for all model calls.** Full control over prompts, input format and output schema. No platform in between. Streamlit is the display layer only and does not touch this rule.
- **Model choice on cost.** The intelligence is in the corpus; any capable model works for pass one. Images and garbled tables need a vision-capable model.
- **Minimal interface.** Upload, select, view. No routing, logins, or database.
- **Cost is near zero.** Marketing copy is short; the factsheet extraction is a monthly batch job.

---

## 10. Build sequence (3 days)

The order exists to get a working, measurable tool fast, and to avoid confusing a bad rule with a bad extraction.

**Setup (first hour of Day 1).** Repo. CLAUDE.md importing this README plus standing working rules. `/sources` folder with the internal checklist, the March 2026 SEBI Master Circular, the Sixth Schedule, current AMFI guidance, and both public factsheets, dates in filenames. Fix the three JSON schemas: rule, verdict, factsheet record. Schemas first lets each module be built and tested independently.

**Day 1: corpus and pass one.** Morning: convert the checklist rows into the rule schema, then enrich with clauses and the missing prohibition rules from the master circular. Human-review every rule; rule-writing is the judgment work. Afternoon: pass-one checker as a CLI (feature detection then requirement checks), DOCX and text-PDF only, plus the one-command eval script. End Day 1 with a real accuracy number.

**Day 2: knowledge base, then vision.** Morning: factsheet extraction into JSON for both files, spot-checks, then the fact-check pass. This is the step most likely to run long. Afternoon: vision ingestion for images, banners, carousels (per frame) and scanned PDFs, including the PDF type-detection branch, legibility and riskometer judgments, prominent-person detection, and the extraction-confidence field. Extend the eval set with image cases.

**Day 3: assembly.** Morning: pass-two advisory layer (fenced, unscored) and wire show-back through the pipeline. Afternoon: the Streamlit UI, then end-to-end testing with self-written generic sample creatives: one clean, one with planted violations, one with a wrong return figure. Keep two hours of buffer for extraction edge cases.

Working rules for every Claude Code session:

- Never merge the three layers into one prompt. That merge will look like a simplification; it destroys the design.
- Run the eval script after any corpus or prompt change.
- Commit after every working step.
- Schemas in `/schemas` are the source of truth.

---

## 11. Out of scope for the first build

- **Video.** Parked. The video checkpoint rules are encoded in the corpus with the `video` creative-type tag but stay inactive. Video adds a temporal dimension (a disclaimer flashing for a second, voice-over requirements) deserving its own phase.
- **Scheme-document knowledge base (SID / KIM / SAI).** The section 6 knowledge base covers the published factsheets only. A natural extension is to ingest the scheme's own documents (Scheme Information Document, Key Information Memorandum, Statement of Additional Information) into the same structured KB, so Layer-2 fact-checks can verify claims the factsheet does not carry cleanly: the scheme and benchmark risk-o-meter level, the product-suitability / product-labelling statement, and the investment objective, against source rather than raising a `needs_review`. Two possible feeds, both usable behind the same deterministic lookup: extract from the public SID/KIM/SAI PDFs on the AMC website (the same batch-extraction pattern as the factsheet KB), or load a compact compliance-maintained sheet of just the essential data points. Keep the section 6 discipline: one record per scheme, `as_of_date` stamped, monthly regeneration.
- **Workflow and routing.** Who receives the result, logging, dashboards.
- **Any login, database, or multi-user handling.**

---

## 12. Guardrails and risks

- **Public sources for regulation and data.** Corpus clauses come from the real, current public SEBI and AMFI documents, versioned by date, never from memory of the rules. Factsheets are the published public versions.
- **Internal material handling.** The compliance checklist is the one internal artifact in the repo; keep it there and nowhere else. No real campaign material: test with generic sample copy written for the purpose.
- **Extraction is the silent failure mode.** The confidence and show-back defences in section 5 are what prevent the worst class of error.
- **Scope creep toward "chat with the ad code."** The output is a structured verdict, not a conversation.
- **Over-trust.** The tool advises, it does not clear material for publication. Pass-one output is flags to resolve, needs_review flags are mandatory human checks, fact-check is verification against a dated snapshot, and pass-two is advisory. None of it is a compliance sign-off.
- **Supersession.** Sources get revised (the March 2026 master circular replaced the June 2024 one; a common ad code is in consultation). Every rule's provenance and date make revision a targeted update, not a rebuild.
