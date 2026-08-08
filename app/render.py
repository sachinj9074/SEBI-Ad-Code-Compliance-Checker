"""Render helpers for the Streamlit UI — one function per layer.

Built for the primary user: a marketing / product person running a creative
through a FIRST-PASS self-check before handing it to the compliance team. So the
rule section leads with "what to change to pass", not with rules or clauses.

Pure display: each takes the verdict dict and writes to the page. The three
layers stay separate and are never merged (README §3). Kept apart from `app.py`
(page flow) so they can be smoke-tested headlessly with streamlit's AppTest.
"""
from __future__ import annotations

import html

import streamlit as st

from src import model

_esc = html.escape

# rgba tints work in both light and dark themes; text colour is inherited.
_TONE = {
    "red": ("rgba(220,38,38,0.12)", "rgba(220,38,38,0.45)"),
    "amber": ("rgba(217,119,6,0.14)", "rgba(217,119,6,0.50)"),
    "green": ("rgba(22,163,74,0.12)", "rgba(22,163,74,0.40)"),
    "slate": ("rgba(100,116,139,0.14)", "rgba(100,116,139,0.40)"),
    "neutral": ("rgba(128,128,128,0.10)", "rgba(128,128,128,0.30)"),
}


# ---- headline + clickable dashboard -----------------------------------------
def headline(v: dict) -> None:
    s = v["summary_strip"]
    fails, review, facts = s["failed"], s["needs_review"], s["fact_mismatches"]
    if fails or facts:
        bits = []
        if fails:
            bits.append(f"**{fails}** rule issue{'' if fails == 1 else 's'} to fix")
        if facts:
            bits.append(f"**{facts}** factual mismatch{'' if facts == 1 else 'es'}")
        tail = f" Then **{review}** item(s) go to your compliance team to confirm." if review else ""
        st.error("🔴 **Not ready to send yet.** Fix " + " and ".join(bits) + " below." + tail)
    elif review:
        st.warning(f"🟠 **Nothing to fix on the automated checks** — but **{review}** item(s) need "
                   "your compliance team's eyes before you publish.")
    else:
        st.success("🟢 **Passed the automated first-pass checks.** This isn't a compliance sign-off — "
                   "your compliance team still gives the final OK — but you've caught the common issues.")


def _stat_card(label: str, n: int, anchor: str | None, tone: str) -> str:
    bg, bd = _TONE[tone]
    inner = (f'<div style="font-size:1.7rem;font-weight:700;line-height:1.1;">{n}</div>'
             f'<div style="font-size:0.78rem;opacity:0.85;">{label}</div>')
    style = (f'display:block;min-width:92px;padding:10px 14px;border-radius:10px;'
             f'background:{bg};border:1px solid {bd};text-align:center;color:inherit;text-decoration:none;')
    if anchor and n:  # only a live jump-link when there is something to jump to
        return f'<a href="#{anchor}" style="{style}">{inner}</a>'
    return f'<div style="{style}opacity:0.9;">{inner}</div>'


def summary_strip(v: dict) -> None:
    s = v["summary_strip"]
    items = [
        ("Rules run", s["rules_run"], None, "neutral"),
        ("Passed", s["passed"], None, "green"),
        ("Must fix", s["failed"], "must-fix", "red"),
        ("Human check", s["needs_review"], "human-check", "amber"),
        ("Fact issues", s["fact_mismatches"], "fact-issues", "red"),
        ("Advisory", s["advisory_notes"], "advisory", "slate"),
    ]
    cards = "".join(_stat_card(*i) for i in items)
    st.markdown(f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin:0.25rem 0;">{cards}</div>',
                unsafe_allow_html=True)
    st.caption("Click **Must fix**, **Human check**, **Fact issues** or **Advisory** to jump straight to that section.")


def features(v: dict) -> None:
    present = [f["feature"] for f in v["feature_detection"]["features"] if f["present"]]
    if present:
        chips = " ".join(f"`{p}`" for p in present)
        st.caption("The tool saw these in your creative: " + chips + " — they decide which rules apply.")


def showback(v: dict) -> None:
    ex = v["extraction"]
    conf = ex["confidence"]
    low = conf < 0.75
    label = f"🔎 What the tool read  ·  {conf:.0%} confidence  ·  {ex['source_kind']}"
    with st.expander(label, expanded=low):
        if low:
            st.warning("Low extraction confidence — check the text below against your creative before trusting the verdict.")
        for w in ex.get("warnings", []):
            st.warning("⚠ " + w)
        if ex.get("languages_detected"):
            st.caption("Languages: " + ", ".join(ex["languages_detected"]))
        st.text_area("Extracted content", ex["extracted_text"] or "(no text extracted)",
                     height=140, disabled=True, label_visibility="collapsed")


# ---- Layer 1: rule checks (creator-first action cards) -----------------------
def _details(r: dict) -> str:
    """Rule id + clause + flagged text, hidden behind a native ℹ️ disclosure."""
    parts = [f"Rule {_esc(r['rule_id'])}"]
    if r.get("source_clause"):
        parts.append("Governing clause: " + _esc(r["source_clause"]))
    if r.get("offending_text"):
        parts.append("Flagged wording: “" + _esc(r["offending_text"]) + "”")
    if r.get("offending_element"):
        parts.append("Element: " + _esc(r["offending_element"]))
    inner = "<br>".join(parts)
    return ('<details style="margin-top:6px;"><summary style="cursor:pointer;font-size:0.8rem;opacity:0.65;">'
            'ℹ️ rule &amp; clause</summary>'
            f'<div style="font-size:0.8rem;opacity:0.8;margin-top:4px;">{inner}</div></details>')


def _shell(accent: str, body: str) -> str:
    return (f'<div style="border:1px solid rgba(128,128,128,0.22);border-left:4px solid {accent};'
            f'border-radius:8px;padding:9px 12px;margin:8px 0;">{body}</div>')


def _fix_card(r: dict) -> str:
    title = _esc(r.get("title") or r["rule_id"])
    why = _esc(r.get("explanation") or r.get("description") or "")
    fix = r.get("suggested_rewrite")
    sev = _esc(r.get("severity", ""))
    body = (f'<div style="font-weight:600;">🔴 {title}'
            f'<span style="font-size:0.72rem;opacity:0.55;font-weight:400;"> · {sev}</span></div>')
    if why:
        body += f'<div style="margin-top:2px;">{why}</div>'
    if fix:
        body += f'<div style="margin-top:6px;"><b>✏️ Change:</b> {_esc(fix)}</div>'
    body += _details(r)
    return _shell("rgba(220,38,38,0.75)", body)


def _check_card(r: dict) -> str:
    title = _esc(r.get("title") or r["rule_id"])
    what = _esc(r.get("description") or r.get("explanation") or "")
    body = f'<div style="font-weight:600;">🟠 {title}</div>'
    if what:
        body += f'<div style="margin-top:2px;">A person should confirm: {what}</div>'
    body += _details(r)
    return _shell("rgba(217,119,6,0.75)", body)


def rule_layer(v: dict) -> None:
    results = v["rule_layer"]["results"]
    fails = [r for r in results if r["verdict"] == "fail"]
    checks = [r for r in results if r["verdict"] == "needs_review"]
    passed = sum(1 for r in results if r["verdict"] == "pass")
    na = sum(1 for r in results if r["verdict"] == "not_applicable")

    st.markdown("### 1 · Compliance checks")
    st.caption("Your first-pass self-check before compliance review. **Fix** the red items so the creative "
               "passes; the amber items are calls only a person can make — send those to your compliance team.")

    st.subheader(f"🔴 Fix these to pass · {len(fails)}", anchor="must-fix")
    if not fails:
        st.success("Nothing to fix — no rule failures for the selected areas and creative type.")
    else:
        st.markdown("".join(_fix_card(r) for r in fails), unsafe_allow_html=True)

    st.subheader(f"🟠 Send these to compliance to check · {len(checks)}", anchor="human-check")
    st.caption("Not failures — the tool can tell the rule applies but can't make the call, so a person confirms.")
    if not checks:
        st.success("Nothing needs a manual check.")
    else:
        st.markdown("".join(_check_card(r) for r in checks), unsafe_allow_html=True)

    st.caption(f"✅ {passed} checks passed  ·  ⚪ {na} not applicable to this creative.")


# ---- Layer 2: fact-check -----------------------------------------------------
_FACT = {
    "mismatch": ("🔴", "Doesn't match the factsheet"),
    "ambiguous": ("🟠", "Can't confirm"),
    "not_found": ("⚪", "Not in the factsheet"),
    "match": ("🟢", "Matches the factsheet"),
}


def fact_layer(v: dict) -> None:
    st.subheader("2 · Factsheet fact-check", anchor="fact-issues")
    st.caption("The numbers in your creative, checked against the published factsheet. "
               "A separate layer — **never** part of the compliance score above.")
    results = v["fact_check_layer"]["results"]
    if not results:
        if not model.available():
            st.info("Fact-check needs the model (no API key set).")
        else:
            st.success("No checkable factual claims found in the creative.")
        return
    for r in results:
        icon, label = _FACT.get(r["verdict"], ("•", r["verdict"]))
        with st.container(border=True):
            st.markdown(f"{icon} **{label}** — “{r['claim_text']}”")
            cols = st.columns(3)
            cols[0].markdown(f"**Your creative says**\n\n{r.get('claimed_value', '—')}")
            cols[1].markdown(f"**Factsheet says**\n\n{r.get('factsheet_value', '—')}")
            cols[2].markdown(f"**As of**\n\n{r.get('as_of_date', '—')}")
            if r.get("scheme_matched"):
                st.caption("Scheme matched: " + r["scheme_matched"]
                           + (f" ({r.get('source_file')})" if r.get("source_file") else ""))
            if r.get("assumption"):
                st.caption("Comparison assumes: " + r["assumption"])


# ---- Layer 3: advisory -------------------------------------------------------
def advisory_layer(v: dict) -> None:
    st.subheader("3 · Advisory", anchor="advisory")
    notes = v["advisory_layer"]["notes"]
    with st.container(border=True):
        st.caption("A second read that sets the rules aside. **Unscored — not a verdict, and it does not affect "
                   "the summary above.** A 'you may also want to look at this' list, kept to things that could "
                   "materially mislead a reader.")
        if not notes:
            if not model.available():
                st.info("Advisory needs the model (no API key set).")
            else:
                st.write("Nothing flagged — the copy reads fair on a second pass.")
            return
        for n in notes:
            tag = f"**[{n['area']}]** " if n.get("area") else ""
            st.markdown(f"- {tag}{n['note']}")
