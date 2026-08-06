# Sources manifest

All regulation and data come from **real, current, public** documents, versioned by date
(README §12). The internal checklist is the one internal artifact and stays in this folder only.

## Present

| File | Role | As-of / date | Notes |
|---|---|---|---|
| `compliance_checklist_2026.xlsx` | Internal compliance checklist (5 sheets) — ground truth for what gets flagged | 2026 | Internal. Do not copy elsewhere. Day 1 converts its rows into the rule schema. |
| `factsheet_active_2026-06-30.pdf` | Active funds factsheet (~170 pp) | 2026-06-30 | Public. Knowledge-base source (README §6). |
| `factsheet_passive_2026-06-30.pdf` | Passive funds factsheet (~65 pp) | 2026-06-30 | Public. Knowledge-base source (README §6). |

## Missing — needed to fill `source_clause` / `provenance` on rules (README §10 Setup)

These are public SEBI/AMFI documents. They supply the citable clause for each rule and the
general prohibition rules the checklist omits (no assured/guaranteed returns, no misleading or
exaggerated claims, no unsubstantiated superlatives).

| Needed | Suggested filename | Where |
|---|---|---|
| SEBI (Mutual Funds) Regulations 1996 — **Sixth Schedule** (Advertisement Code) | `sebi_sixth_schedule.pdf` | SEBI website (regulations) |
| **MF Master Circular dated 2026-03-20** — advertisement chapter (supersedes 2024-06-27) | `sebi_mf_master_circular_2026-03-20.pdf` | SEBI website (circulars) |
| **AMFI** current advertisement guidelines / circulars | `amfi_ad_guidelines_<date>.pdf` | AMFI website |

**Supersession watch (README §4):** the March 2026 master circular replaced the June 2024 one.
A SEBI consultation paper proposing a common advertisement code across regulated entities is in
circulation; if adopted, the celebrity rules change. Watch, do not act.

## How to add

Download the public PDF, name it with the document's date as above, drop it in this folder, and
add a row to the **Present** table. Then rules can cite it in `source_clause` with `source_date`.
