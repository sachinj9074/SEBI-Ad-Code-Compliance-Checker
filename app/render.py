"""Render helpers for the Streamlit UI — one function per layer.

Pure display: each takes the verdict dict and writes to the page. The three
layers are rendered as separate, differently-styled sections and never merged
(README §3). Kept apart from `app.py` (page flow) so they can be smoke-tested
headlessly with streamlit's AppTest.
"""
from __future__ import annotations

import streamlit as st

from src import model

# Plain-language verdict labels (non-technical users read these, not the enum).
VERDICT = {
    "fail": ("🔴", "Must fix"),
    "needs_review": ("🟠", "Human check"),
    "pass": ("🟢", "OK"),
    "not_applicable": ("⚪", "N/A"),
}
FACT = {
    "mismatch": ("🔴", "Mismatch"),
    "ambiguous": ("🟠", "Can't confirm"),
    "not_found": ("⚪", "Not in factsheet"),
    "match": ("🟢", "Matches"),
}
SEV = {"critical": "🟥 critical", "high": "🟧 high", "medium": "🟨 medium", "low": "🟦 low"}


def headline(v: dict) -> None:
    """One plain-language line at the top: overall state + what to do next."""
    s = v["summary_strip"]
    fails, review, facts = s["failed"], s["needs_review"], s["fact_mismatches"]
    if fails or facts:
        bits = []
        if fails:
            bits.append(f"**{fails}** rule {'issue' if fails == 1 else 'issues'} to fix")
        if facts:
            bits.append(f"**{facts}** factual {'mismatch' if facts == 1 else 'mismatches'}")
        extra = f" · {review} item(s) also need a human check." if review else ""
        st.error("🔴 Not ready to publish — " + " and ".join(bits) + " before compliance review." + extra)
    elif review:
        st.warning(f"🟠 No hard stops — but **{review}** item(s) need a human check before sign-off.")
    else:
        st.success("🟢 No rule failures, factual mismatches, or open checks. Still not a compliance sign-off — see the advisory read below.")


def summary_strip(v: dict) -> None:
    s = v["summary_strip"]
    c = st.columns(6)
    c[0].metric("Rules run", s["rules_run"])
    c[1].metric("Passed", s["passed"])
    c[2].metric("Must fix", s["failed"])
    c[3].metric("Human check", s["needs_review"])
    c[4].metric("Fact issues", s["fact_mismatches"])
    c[5].metric("Advisory", s["advisory_notes"])


def features(v: dict) -> None:
    present = [f["feature"] for f in v["feature_detection"]["features"] if f["present"]]
    if present:
        chips = " ".join(f"`{p}`" for p in present)
        st.caption("Your creative contains: " + chips
                   + " — these decide which conditional rules apply.")


def showback(v: dict) -> None:
    ex = v["extraction"]
    conf = ex["confidence"]
    with st.container(border=True):
        st.markdown("#### 🔎 What the tool read")
        cols = st.columns(3)
        cols[0].metric("Extraction confidence", f"{conf:.0%}")
        cols[1].markdown(f"**Source**\n\n{ex['source_kind']}")
        if ex.get("languages_detected"):
            cols[2].markdown("**Languages**\n\n" + ", ".join(ex["languages_detected"]))
        if conf < 0.75:
            st.warning("Low extraction confidence — check the text below against your creative before trusting the verdict.")
        for w in ex.get("warnings", []):
            st.warning("⚠ " + w)
        st.text_area("Extracted content", ex["extracted_text"] or "(no text extracted)",
                     height=160, disabled=True, label_visibility="collapsed")


def _rule_block(r: dict) -> None:
    """One flagged rule, in plain language."""
    icon, label = VERDICT.get(r["verdict"], ("•", r["verdict"]))
    sev = SEV.get(r.get("severity", ""), r.get("severity", ""))
    st.markdown(f"{icon} **{label}** · {r['rule_id']} · {sev}")
    if r.get("description"):
        st.markdown("What this checks: " + r["description"])
    if r.get("offending_text"):
        st.markdown("› In your creative: " + f"_{r['offending_text']}_")
    if r.get("offending_element"):
        st.markdown("› Element: " + f"_{r['offending_element']}_")
    # For human-check items, the explanation/description IS the "what to verify".
    if r["verdict"] == "needs_review":
        st.info("A person must confirm this — the tool can detect the condition but not decide it.")
    if r.get("suggested_rewrite"):
        st.success("Suggested fix: " + r["suggested_rewrite"])
    if r.get("source_clause"):
        st.caption("Governing clause: " + r["source_clause"])


def rule_layer(v: dict) -> None:
    st.markdown("### 1 · Compliance rule checks")
    st.caption("The scored spine. **Must fix** = a rule failure to resolve. "
               "**Human check** = the tool flags it for a person rather than guessing. Grouped by what triggered them.")
    results = v["rule_layer"]["results"]
    flagged = [r for r in results if r["verdict"] in ("fail", "needs_review")]

    if not flagged:
        st.success("No rule failures or open checks for the selected areas and creative type.")
    else:
        groups: dict[str, list[dict]] = {}
        for r in flagged:
            groups.setdefault(r.get("triggered_by", "unconditional"), []).append(r)
        for trig, items in sorted(groups.items()):
            fails = sum(1 for r in items if r["verdict"] == "fail")
            revs = len(items) - fails
            why = "Always-on rules" if trig == "unconditional" else f"Because your creative shows **{trig}**"
            parts = []
            if fails:
                parts.append(f"{fails} to fix")
            if revs:
                parts.append(f"{revs} to check")
            with st.expander(f"{why} — {', '.join(parts)}", expanded=True):
                for i, r in enumerate(items):
                    _rule_block(r)
                    if i < len(items) - 1:
                        st.divider()

    passed = sum(1 for r in results if r["verdict"] == "pass")
    na = sum(1 for r in results if r["verdict"] == "not_applicable")
    st.caption(f"Also: {passed} passed · {na} not applicable to this creative.")


def fact_layer(v: dict) -> None:
    st.markdown("### 2 · Factsheet fact-check")
    st.caption("The numbers in your creative, checked against the published factsheet. "
               "A separate layer with its own severity — **never** part of the compliance score above.")
    results = v["fact_check_layer"]["results"]
    if not results:
        if not model.available():
            st.info("Fact-check needs the model (no API key set).")
        else:
            st.success("No checkable factual claims found in the creative.")
        return
    for r in results:
        icon, label = FACT.get(r["verdict"], ("•", r["verdict"]))
        with st.container(border=True):
            st.markdown(f"{icon} **{label}** — “{r['claim_text']}”")
            cols = st.columns(3)
            cols[0].markdown(f"**Creative says**\n\n{r.get('claimed_value', '—')}")
            cols[1].markdown(f"**Factsheet says**\n\n{r.get('factsheet_value', '—')}")
            cols[2].markdown(f"**As of**\n\n{r.get('as_of_date', '—')}")
            if r.get("scheme_matched"):
                st.caption("Scheme matched: " + r["scheme_matched"]
                           + (f" ({r.get('source_file')})" if r.get("source_file") else ""))
            if r.get("assumption"):
                st.caption("Comparison assumes: " + r["assumption"])


def advisory_layer(v: dict) -> None:
    st.markdown("### 3 · Advisory")
    notes = v["advisory_layer"]["notes"]
    with st.container(border=True):
        st.caption("A second read that sets the rules aside. **Unscored — not a verdict, and it does not affect the summary above.** "
                   "A 'you may also want to look at this' list, kept to things that could materially mislead a reader.")
        if not notes:
            if not model.available():
                st.info("Advisory needs the model (no API key set).")
            else:
                st.write("Nothing flagged — the copy reads fair on a second pass.")
            return
        for n in notes:
            tag = f"**[{n['area']}]** " if n.get("area") else ""
            st.markdown(f"- {tag}{n['note']}")
