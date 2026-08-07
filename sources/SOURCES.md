# Sources manifest

All regulation and data come from **real, current, public** documents, versioned by date
(README §12). The internal checklist is the one internal artifact and stays in this folder only.

## Present

| File | Role | As-of / date | Notes |
|---|---|---|---|
| `compliance_checklist_2026.xlsx` | Internal compliance checklist (5 sheets) — ground truth for what gets flagged | 2026 | **Internal — local-only, gitignored, NEVER committed** (public+genericize policy, see `corpus/GENERICIZATION.md`). Day 1 converts its rows into the (genericized) rule schema. |
| `Checklist - Advertisement_Dos and Don'ts List with Examples.xlsx` | Internal Dos & Don'ts list — Sixth Schedule in plain language + worked examples | 2026 | **Internal — local-only, gitignored, NEVER committed.** Genericized into PROH-007/008, XSELL-001, SUBST-001, LEGIB-001 and the CELEB-001 / DISC-010 enhancements. Its examples are earmarked for the advisory layer + eval set. |
| `factsheet_active_2026-06-30.pdf` | Active funds factsheet (~170 pp) | 2026-06-30 | Public. Knowledge-base source (README §6). |
| `factsheet_passive_2026-06-30.pdf` | Passive funds factsheet (~65 pp) | 2026-06-30 | Public. Knowledge-base source (README §6). |
| `sebi_mf_regulations_1996_2026-01.pdf` | SEBI (Mutual Funds) Regulations 1996, consolidated to Jan 2026 (162 pp) | 2026-01 | Public. **Sixth Schedule = Advertisement Code** is on **pp. 126–127** [Regulation 30]. Reg. 30 (p. 43) mandates conformity with it + filing within 7 days. |
| `sebi_mf_master_circular_2026-03-20_ad_chapter.pdf` | MF Master Circular — **Chapter 14: Advertisements** only (5 pp) | 2026-03-20 | Public. Extract of **pp. 232–236 of 748** from the full circular. Supersedes the 2024-06-27 circular. |
| `amfi_bp_circular_109_2023-11-01.pdf` | AMFI Best Practices Circular No. 109/2023-24 — ad-code compliance for returns illustrations | 2023-11-01 | Public. Caps depicted future returns at 13% in tools/calculators; relevant to `yield` creatives. |

### Citation quick-reference (for rule `source_clause` / `source_date`)
- **SEBI ad code (foundational):** Sixth Schedule [Reg. 30], `sebi_mf_regulations_1996_2026-01.pdf` pp. 126–127. `source_date` = 2026-01. `provenance: [sebi]`.
- **SEBI ad chapter (supplementary):** Master Circular 2026-03-20, Chapter 14 §14.x, `..._ad_chapter.pdf`. `source_date` = 2026-03-20. `provenance: [sebi]`.
- **AMFI:** BP Circular 109/2023-24 (returns illustrations), `source_date` = 2023-11-01. `provenance: [amfi]`.
- **Internal-only items** (e.g. Sponsor/Axis wording, app-rating rule): `provenance: [internal_policy]`, cite the checklist sheet.

## Not stored in the repo (re-downloadable)
- **Full MF Master Circular (748 pp, 6.86 MB)** — only Chapter 14 is kept above to stay lean.
  Re-download if another chapter is ever needed:
  `https://www.sebi.gov.in/sebi_data/attachdocs/mar-2026/1774024028162.pdf`
- **Optional broader AMFI coverage:** AMFI Master Circular for MF Distributors (consolidated to
  Dec 2025) — distributor-focused; add only if distributor material comes into scope.

## Supersession watch (README §4)
The March 2026 master circular replaced the June 2024 one. A SEBI consultation paper proposing a
common advertisement code across regulated entities is in circulation; if adopted, the celebrity
rules change. **Watch, do not act.**

## How to add a source
Download the public PDF, name it with the document's date, drop it in this folder, add a row to
the **Present** table, then rules can cite it in `source_clause` with `source_date`.
