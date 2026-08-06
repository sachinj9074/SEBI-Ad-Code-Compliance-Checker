# Genericization policy

This is a **public portfolio repo**. The internal compliance checklist (an AMC's internal
artifact) is **local-only and never committed** (gitignored). Everything committed here is either
public regulation or **genericized** so the project is employer-neutral and leaks no internal
material.

## What stays verbatim (public / universal)
These are identical for every AMC and are quoted exactly, with citations:
- SEBI standard 14-word warning (EN): *"Mutual Fund investments are subject to market risks, read
  all scheme related documents carefully."* — Sixth Schedule (i)
- The Hindi standard warning — Sixth Schedule (ia)
- SEBI / AMFI clause text and references (Sixth Schedule, MC Chapter 14, AMFI Circular 109)
- Standard exchange disclaimers (NSE/BSE templates), SEBI market-cap definitions, riskometer levels

## What gets genericized (AMC-identifying → placeholder)
Applied to all `mandated_text`, examples, and sample creatives in committed files:

| Internal / real value | Placeholder used in the repo |
|---|---|
| Axis Mutual Fund / Axis MF / Axis AMC / "Axis MF/AMC" | `[AMC]` |
| Axis Bank Ltd (sponsor) | `[Sponsor Bank]` |
| www.axismf.com | `[AMC website]` |
| customerservice@axismf.com | `[AMC email]` |
| 8108622211 (helpline) | `[AMC helpline]` |
| MF/061/09/02 (SEBI reg. no.) | `[SEBI registration no.]` |
| Axis ELSS Tax Saver Fund (and other scheme names) | `[scheme name]` / generic sample names |
| "Axis Group Employees" | `[AMC] employees` |

Rule of thumb: if a string names or identifies a specific AMC, sponsor, scheme, or contact, it is
replaced with a bracketed placeholder. The **structure and intent** of every disclaimer is
preserved so the checker logic is unchanged.

## Provenance still recorded honestly
Genericizing the text does not change a rule's `provenance`. Items that originate from the internal
checklist are still tagged `provenance: [internal_policy]` (e.g. sponsor wording, app-rating rule,
SEBI reg-no. presence) so a regulation change vs. a policy change stays distinguishable.

## Sample data
End-to-end tests use **self-written generic sample creatives** (one clean, one with planted
violations, one with a wrong return figure), never real campaign material (README §12).
