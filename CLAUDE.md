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
- The internal compliance checklist is the one internal artifact; it stays in `sources/` and
  nowhere else. Test only with **generic sample copy** written for the purpose — never real
  campaign material.

## Repository layout
- `sources/`  — inputs (internal checklist, SEBI/AMFI sources, factsheets). See `sources/SOURCES.md`.
- `schemas/`  — the three JSON schemas + `examples/` templates. Source of truth.
- `corpus/`   — the rule corpus (built Day 1 from the checklist + SEBI/AMFI clauses).
- `src/`      — pipeline: extraction, feature detection, rule checks, fact-check, advisory.
- `data/`     — generated factsheet knowledge base JSON (monthly batch output).
- `evals/`    — the one-command eval script + case set.
- `app/`      — Streamlit UI (Day 3).

## Environment
- Windows 11, **PowerShell is the primary shell** (Bash tool also available). Python 3.12, venv at `.venv`.
- Direct model API for all model calls (README §9). API key in `.env` (gitignored), never committed.

## Open decisions (confirm before writing the code that depends on them)
- **Model provider.** README says "direct model API, chosen on cost, vision-capable." Default
  assumption: **Anthropic Claude** (native vision, Devanagari, structured output). Isolated behind
  a model client in `src/` so it can be swapped.
- **Severity enum.** Set to `critical | high | medium | low` at setup; reconcile with the
  checklist's own severity language on Day 1.
- **Missing public sources.** Sixth Schedule, Mar-2026 MF Master Circular (advertisement chapter),
  and current AMFI guidance are not yet in `sources/`. Needed to fill `source_clause` on rules.
  See `sources/SOURCES.md`.
