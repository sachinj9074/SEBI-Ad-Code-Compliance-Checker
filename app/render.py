"""Render helpers for the Streamlit UI — one function per layer.

Pure display: each takes the verdict dict and writes to the page. The three
layers are rendered as separate, differently-styled sections and never merged
(README §3). Kept apart from `app.py` (page flow) so they can be smoke-tested
headlessly with streamlit's AppTest.
"""
from __future__ import annotations

import streamlit as st

from src import model

VERDICT_ICON = {"pass": "🟢", "fail": "🔴", "needs_review": "🟠", "not_applicable": "⚪"}
FACT_ICON = {"match": "🟢", "mismatch": "🔴", "ambiguous": "🟠", "not_found": "⚪"}
SEV_ICON = {"critical": "🟥", "high": "🟧", "medium": "🟨", "low": "🟦"}


def summary_strip(v: dict) -> None:
    s = v["summary_strip"]
    c = st.columns(6)
    c[0].metric("Rules run", s["rules_run"])
    c[1].metric("Passed", s["passed"])
    c[2].metric("Failed", s["failed"])
    c[3].metric("Needs review", s["needs_review"])
    c[4].metric("Fact mismatches", s["fact_mismatches"])
    c[5].metric("Advisory notes", s["advisory_notes"])


def features(v: dict) -> None:
    present = [f["feature"] for f in v["feature_detection"]["features"] if f["present"]]
    if present:
        chips = " ".join(f"`{p}`" for p in present)
        st.caption("Detected in your creative (these drive which conditional rules apply): " + chips)


def showback(v: dict) -> None:
    ex = v["extraction"]
    conf = ex["confidence"]
    with st.container(border=True):
        st.markdown("#### 🔎 Show-back — what the tool read")
        cols = st.columns([1, 1, 1, 1])
        cols[0].metric("Extraction confidence", f"{conf:.0%}")
        cols[1].markdown(f"**Source**\n\n{ex['source_kind']}")
        if ex.get("languages_detected"):
            cols[2].markdown("**Languages**\n\n" + ", ".join(ex["languages_detected"]))
        if conf < 0.75:
            st.warning("Low extraction confidence — check the text below against your creative before trusting the verdict.")
        for w in ex.get("warnings", []):
            st.warning("⚠ " + w)
        if ex.get("layout_notes"):
            st.caption("Layout: " + ex["layout_notes"])
        if ex.get("legibility_notes"):
            st.caption("Legibility: " + ex["legibility_notes"])
        st.text_area("Extracted content", ex["extracted_text"] or "(no text extracted)",
                     height=160, disabled=True, label_visibility="collapsed")


def rule_layer(v: dict) -> None:
    st.markdown("### 1 · Compliance rule checks")
    st.caption("The scored spine — deterministic checks and human-review flags, each cited to its governing clause.")
    results = v["rule_layer"]["results"]
    flagged = [r for r in results if r["verdict"] in ("fail", "needs_review")]

    if not flagged:
        st.success("No failed or needs-review rules for the selected areas and creative type.")
    else:
        # Group by the feature that triggered them ("your creative shows performance, so …").
        groups: dict[str, list[dict]] = {}
        for r in flagged:
            groups.setdefault(r.get("triggered_by", "unconditional"), []).append(r)
        for trig, items in sorted(groups.items()):
            fails = sum(1 for r in items if r["verdict"] == "fail")
            revs = len(items) - fails
            head = f"Triggered by **{trig}** — {fails} failed, {revs} needs-review"
            with st.expander(head, expanded=True):
                for r in items:
                    icon = VERDICT_ICON.get(r["verdict"], "•")
                    sev = r.get("severity", "")
                    sev_ic = SEV_ICON.get(sev, "")
                    st.markdown(f"{icon} **{r['rule_id']}** — {r['verdict'].replace('_', ' ')}  ·  {sev_ic} {sev}")
                    if r.get("source_clause"):
                        st.caption("Clause: " + r["source_clause"])
                    if r.get("explanation"):
                        st.write(r["explanation"])
                    if r.get("offending_text"):
                        st.markdown("› offending text: " + f"_{r['offending_text']}_")
                    if r.get("offending_element"):
                        st.markdown("› offending element: " + f"_{r['offending_element']}_")
                    if r.get("suggested_rewrite"):
                        st.success("Suggested fix: " + r["suggested_rewrite"])
                    st.divider()

    passed = sum(1 for r in results if r["verdict"] == "pass")
    na = sum(1 for r in results if r["verdict"] == "not_applicable")
    st.caption(f"Also: {passed} passed, {na} not applicable to this creative.")


def fact_layer(v: dict) -> None:
    st.markdown("### 2 · Factsheet fact-check")
    st.caption("A separate layer with its own severity model — factual errors, **never** blended into the compliance score above.")
    results = v["fact_check_layer"]["results"]
    if not results:
        if not model.available():
            st.info("Fact-check needs the model (no API key set).")
        else:
            st.success("No checkable factual claims found in the creative.")
        return
    for r in results:
        icon = FACT_ICON.get(r["verdict"], "•")
        with st.container(border=True):
            st.markdown(f"{icon} **{r['verdict']}** — “{r['claim_text']}”")
            cols = st.columns(3)
            cols[0].markdown(f"**Creative says**\n\n{r.get('claimed_value', '—')}")
            cols[1].markdown(f"**Factsheet says**\n\n{r.get('factsheet_value', '—')}")
            asof = r.get("as_of_date", "—")
            cols[2].markdown(f"**As of**\n\n{asof}")
            if r.get("scheme_matched"):
                st.caption("Scheme matched: " + r["scheme_matched"]
                           + (f" ({r.get('source_file')})" if r.get("source_file") else ""))
            if r.get("assumption"):
                st.caption("Comparison rests on assumption: " + r["assumption"])


def advisory_layer(v: dict) -> None:
    st.markdown("### 3 · Advisory")
    notes = v["advisory_layer"]["notes"]
    with st.container(border=True):
        st.caption("A second read that sets the rules aside. **Unscored — not a verdict, and it does not affect the pass/fail summary.** A 'you may also want to look at this' list.")
        if not notes:
            if not model.available():
                st.info("Advisory needs the model (no API key set).")
            else:
                st.write("Nothing flagged — the copy reads clean on a second pass.")
            return
        for n in notes:
            tag = f"**[{n['area']}]** " if n.get("area") else ""
            st.markdown(f"- {tag}{n['note']}")
