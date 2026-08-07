# Factsheet knowledge base (Layer 2)

Structured JSON extracted from the public monthly factsheets (README §6) — one record per
scheme + plan/option variant, conforming to `schemas/factsheet_record.schema.json`. Regenerated
monthly by `scripts/build_factsheet_kb.py`. Committed with real data (the factsheets are public).

## Files (as of 2026-06-30)
| File | Records | Schemes | Source |
|---|---|---|---|
| `factsheet_kb/active.json` | 163 | 84 | `factsheet_active_2026-06-30.pdf` |
| `factsheet_kb/passive.json` | 105 | 37 | `factsheet_passive_2026-06-30.pdf` |

## Coverage / known gaps (v1)
- **Active** — returns (scheme + benchmark, 1Y/3Y/5Y/since-inception), AUM, top holdings, fund
  managers, benchmark, inception: all present. Two-page debt schemes have their returns captured
  from the continuation page.
- **Passive** — details + AUM + tracking error + expense ratio + underlying index present, but
  **returns are null**: passive returns live in a separate returns annexure (pp.42–55) this v1
  does not yet join. Follow-up: an annexure pass merged by scheme name.
- `riskometer_level` is null (it is a graphic dial on a consolidated page, not text) — a vision
  pass can fill it later.

## Regenerate
```
.venv\Scripts\python.exe scripts/build_factsheet_kb.py --which both
```
Runs on `claude-haiku-4-5` by default (a batch extraction job — README §9 "cost near zero").
**Spot-check five schemes per file against the PDF before trusting a fresh run** (README §6).
