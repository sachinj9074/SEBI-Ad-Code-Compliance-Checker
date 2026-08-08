# CLAUDE.md — SEBI Ad Code Compliance Checker

@README.md

The README above is the single source of truth for **what** we are building and **why**.
This file adds the standing **working rules** for every session, plus environment notes and
open decisions. If the two conflict, the README wins on product/design; this file wins on process.

## Standing working rules (README §10)
- **Never merge the three layers** (rules-as-checklist / factsheet fact-check / advisory) into
  one prompt, one score, or one report section. The merge looks like a simplification; it
  destroys the design.
- **Schemas in `/schemas` are the source of truth.** Rule, verdict, and factsheet-record shapes
  are defined there. Change the schema first, then the code.
- **Run the eval script after any corpus or prompt change** and record the accuracy number.
- **Commit after every working step** with a clear message.
- Regulation/data come from the real, current **public** SEBI / AMFI / factsheet documents,
  versioned by date — never from memory of the rules. Record `provenance` and `source_date`
  on every rule.
- **This repo is a public portfolio project.** The internal compliance checklist is **local-only
  and never committed** (gitignored). AMC-identifying content is **genericized** in every
  committed file — see `corpus/GENERICIZATION.md`. Public SEBI/AMFI verbatim texts are kept as-is.
  Test only with **generic sample copy** written for the purpose — never real campaign material.

## Repository layout
- `sources/`  — inputs (internal checklist, SEBI/AMFI sources, factsheets). See `sources/SOURCES.md`.
- `schemas/`  — the three JSON schemas + `examples/` templates. Source of truth.
- `corpus/`   — the rule corpus (built Day 1 from the checklist + SEBI/AMFI clauses).
- `src/`      — pipeline: extraction, feature detection, rule checks, fact-check, advisory.
- `data/`     — generated factsheet knowledge base JSON (monthly batch output).
- `evals/`    — the one-command eval script + case set.
- `app/`      — Streamlit UI (Day 3).

**Current build status, resolved decisions, gotchas, and next steps: see `STATUS.md`** (kept current).

## Environment
- Windows 11, **PowerShell is the primary shell** (Bash tool also available). Python 3.12, venv at `.venv`.
- Direct model API for all model calls (README §9). API key in `.env` (gitignored), never committed.

## Resolved decisions
- **Model provider = Anthropic Claude** (native vision, Devanagari, structured output). All model
  calls go through one client in `src/` so the provider stays swappable. API key in `.env`.
  **Tiered on cost** (see STATUS.md): Haiku 4.5 for feature detection + claim extraction, Sonnet 5
  for rule judgment / advisory / vision (`ANTHROPIC_FAST_MODEL` / `ANTHROPIC_MODEL`).
- **Sources = fetch from official public sites.** The missing SEBI/AMFI documents are being
  downloaded from sebi.gov.in / amfiindia.com into `sources/`. See `sources/SOURCES.md`.
- **Repo = public + genericized** (for portfolio). Internal checklist local-only/gitignored;
  committed corpus uses generic placeholders. See `corpus/GENERICIZATION.md`.
- **Factsheets = public → committed as-is.** The factsheet PDFs are public downloads, so both the
  raw PDFs and the generated knowledge base (`data/`) are committed with **real** data — public
  factsheet figures are not AMC-internal material and are not genericized.

## Open decisions (confirm before writing the code that depends on them)
- **Severity enum.** Set to `critical | high | medium | low` at setup; reconcile with the
  checklist's own severity language on Day 1.
