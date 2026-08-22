"""Render helpers for the Streamlit UI.

Built for the primary user: a marketing / product person running a creative
through a FIRST-PASS self-check before handing it to the compliance team.

Attention is channelled in priority order — fix failures first, then factual
mismatches, then the human checks, then advisory. One section is shown at a
time; the summary dashboard doubles as the section switcher, so a heavy verdict
never becomes a long scroll. The three layers stay separate and are never
merged (README §3).

Pure display: each function takes the verdict dict (and the run id for
widget-state namespacing) and writes to the page. Kept apart from `app.py`
(page flow) so they can be smoke-tested headlessly with streamlit's AppTest.
"""
from __future__ import annotations

import html

import streamlit as st

from src import model, report

_esc = html.escape

# rgba tints work in both light and dark themes; text colour is inherited.
_TONE = {
    "red": ("rgba(220,38,38,0.12)", "rgba(220,38,38,0.45)"),
    "amber": ("rgba(217,119,6,0.14)", "rgba(217,119,6,0.50)"),
    "green": ("rgba(22,163,74,0.12)", "rgba(22,163,74,0.40)"),
    "slate": ("rgba(100,116,139,0.14)", "rgba(100,116,139,0.40)"),
    "neutral": ("rgba(128,128,128,0.10)", "rgba(128,128,128,0.30)"),
}

# Section registry in PRIORITY ORDER: fixing failures is the user's primary
# responsibility, the fact-check second, human checks + advisory after that.
_SECTIONS = ["must_fix", "facts", "human", "advisory", "passed"]
_SECTION_META = {
    "must_fix": ("🔴", "Fix these"),
    "facts": ("🧾", "Fact check"),
    "human": ("🟠", "Human check"),
    "advisory": ("💡", "Advisory"),
    "passed": ("✅", "Passed"),
}


# ---- small accessors ---------------------------------------------------------
def _fails(v):
    return [r for r in v["rule_layer"]["results"] if r["verdict"] == "fail"]


def _checks(v):
    return [r for r in v["rule_layer"]["results"] if r["verdict"] == "needs_review"]


def _counts(v: dict) -> dict:
    s = v["summary_strip"]
    return {
        "must_fix": s["failed"],
        "facts": s["fact_mismatches"],
        "human": s["needs_review"],
        "advisory": s["advisory_notes"],
        "passed": s["passed"],
    }


def ack_keys(run_id: int) -> tuple[str, str]:
    """DURABLE session-state keys holding the two acknowledgement values (per run).

    These are plain keys we manage ourselves, NOT widget keys, so they survive
    even when their checkbox is not currently rendered (the results show one
    section at a time). The clearance gate reads these.
    """
    return f"ack_human_val_{run_id}", f"ack_advisory_val_{run_id}"


def _persist_checkbox(label: str, val_key: str, widget_key: str, help: str | None = None) -> None:
    """A checkbox whose value survives navigating away from its section. The
    widget writes to a durable `val_key` via on_change; on re-render the widget
    is re-seeded from that durable value."""
    st.session_state.setdefault(val_key, False)
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state[val_key]
    st.checkbox(
        label, key=widget_key, help=help,
        on_change=lambda: st.session_state.__setitem__(val_key, st.session_state[widget_key]),
    )


# ---- headline + selection warnings ------------------------------------------
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


def selection_warnings(v: dict) -> None:
    for w in v["meta"].get("selection_warnings", []):
        st.warning(f"⚠️ {w}")


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


# ---- the navigator (dashboard = section switcher) ----------------------------
def _default_section(counts: dict) -> str:
    for name in _SECTIONS[:-1]:  # first non-empty in priority order
        if counts[name]:
            return name
    return "passed"


def results(v: dict, run_id: int) -> None:
    """Dashboard-switcher + the active section. One section at a time."""
    counts = _counts(v)
    state_key = f"section_{run_id}"
    active = st.session_state.get(state_key) or _default_section(counts)

    s = v["summary_strip"]
    st.caption(f"**{s['rules_run']}** rules ran for your selection. Work top priority first — "
               "the buttons below are in order of importance.")
    cols = st.columns(len(_SECTIONS))
    clicked = None
    for col, name in zip(cols, _SECTIONS):
        icon, label = _SECTION_META[name]
        n = counts[name]
        if col.button(f"{icon} {label} · {n}", key=f"nav_{name}_{run_id}",
                      use_container_width=True,
                      type="primary" if name == active else "secondary",
                      disabled=(n == 0 and name != "passed")):
            clicked = name
    if clicked and clicked != active:
        st.session_state[state_key] = clicked
        st.rerun()  # repaint so the active button styling matches

    {"must_fix": _sec_must_fix, "facts": _sec_facts, "human": _sec_human,
     "advisory": _sec_advisory, "passed": _sec_passed}[active](v, run_id)


# ---- Layer-1 cards -----------------------------------------------------------
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


# ---- sections (one visible at a time) ---------------------------------------
def _sec_must_fix(v: dict, run_id: int) -> None:
    fails = _fails(v)
    st.markdown(f"#### 🔴 Fix these to pass · {len(fails)}")
    st.caption("Layer 1 · rule checks. Your primary job: make each edit below, then re-run the check.")
    if not fails:
        st.success("Nothing to fix — no rule failures for your selection. 🎉  Move on to **Fact check**.")
        return
    st.markdown("".join(_fix_card(r) for r in fails), unsafe_allow_html=True)


def _sec_facts(v: dict, run_id: int) -> None:
    st.markdown("#### 🧾 Factsheet fact-check")
    st.caption("Layer 2 · the numbers in your creative, checked against the published factsheet. "
               "A separate layer — **never** part of the compliance score.")
    results_ = v["fact_check_layer"]["results"]
    if not results_:
        if not model.available():
            st.info("Fact-check needs the model (no API key set).")
        else:
            st.success("No checkable factual claims found in the creative.")
        return
    order = {"mismatch": 0, "ambiguous": 1, "not_found": 2, "match": 3}
    for r in sorted(results_, key=lambda r: order.get(r["verdict"], 9)):
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


_FACT = {
    "mismatch": ("🔴", "Doesn't match the factsheet"),
    "ambiguous": ("🟠", "Can't confirm"),
    "not_found": ("⚪", "Not in the factsheet"),
    "match": ("🟢", "Matches the factsheet"),
}


def _sec_human(v: dict, run_id: int) -> None:
    checks = _checks(v)
    st.markdown(f"#### 🟠 Human check · {len(checks)}")
    st.caption("Layer 1 · rule checks the tool can't decide alone: it can tell the rule applies but "
               "a person makes the call. Review each one (with your compliance team where needed).")
    ack_human, _ = ack_keys(run_id)
    if not checks:
        st.success("Nothing needs a manual check for this creative.")
        return
    st.markdown("".join(_check_card(r) for r in checks), unsafe_allow_html=True)
    _persist_checkbox(
        "I confirm that each item above has been manually reviewed.",
        ack_human, f"ack_human_cb_{run_id}",
        help="Required before a clearance report can be generated.",
    )


def _sec_advisory(v: dict, run_id: int) -> None:
    st.markdown("#### 💡 Advisory")
    notes = v["advisory_layer"]["notes"]
    _, ack_adv = ack_keys(run_id)
    with st.container(border=True):
        st.caption("Layer 3 · a second read that sets the rules aside. **Unscored — not a verdict, and it "
                   "does not affect the summary.** Kept to things that could materially mislead a reader.")
        if not notes:
            if not model.available():
                st.info("Advisory needs the model (no API key set).")
            else:
                st.write("Nothing flagged — the copy reads fair on a second pass.")
            return
        for n in notes:
            tag = f"**[{n['area']}]** " if n.get("area") else ""
            st.markdown(f"- {tag}{n['note']}")
    _persist_checkbox(
        "I confirm the advisory points above have been read and considered.",
        ack_adv, f"ack_advisory_cb_{run_id}",
        help="Required before a clearance report can be generated.",
    )


def _sec_passed(v: dict, run_id: int) -> None:
    results_ = v["rule_layer"]["results"]
    passed = [r for r in results_ if r["verdict"] == "pass"]
    na = sum(1 for r in results_ if r["verdict"] == "not_applicable")
    st.markdown(f"#### ✅ Passed · {len(passed)}")
    st.caption(f"Rules this creative already satisfies (plus {na} not applicable to it).")
    if passed:
        items = "".join(
            f'<div style="padding:3px 0;font-size:0.9rem;">✅ {_esc(r.get("title") or r["rule_id"])}'
            f'<span style="font-size:0.72rem;opacity:0.5;"> · {_esc(r["rule_id"])}</span></div>'
            for r in passed)
        st.markdown(f'<div style="column-width:320px;column-gap:28px;">{items}</div>',
                    unsafe_allow_html=True)


# ---- clearance report (gate + download) -------------------------------------
def _prereq(done: bool, text: str) -> None:
    st.markdown(f"{'✅' if done else '⬜'} {text}")


def clearance(v: dict, run_id: int) -> None:
    st.divider()
    st.markdown("### 4 · Clearance report")
    st.caption("Once the automated checks and fact-checks are clean and you've reviewed the human-check "
               "and advisory items, download a report to attach when you hand this creative to compliance. "
               "It records a first-pass check; it is **not** a compliance sign-off.")

    counts = _counts(v)
    ok_auto, _ = report.automated_clear(v)
    ack_human_key, ack_adv_key = ack_keys(run_id)
    need_human, need_adv = counts["human"] > 0, counts["advisory"] > 0
    ack_human = (not need_human) or bool(st.session_state.get(ack_human_key))
    ack_adv = (not need_adv) or bool(st.session_state.get(ack_adv_key))

    _prereq(counts["must_fix"] == 0, f"No rule failures  ·  {counts['must_fix']} to fix")
    _prereq(counts["facts"] == 0, f"No factual mismatches  ·  {counts['facts']} to resolve")
    if need_human:
        _prereq(ack_human, "Human-check items reviewed  ·  tick the box in the **🟠 Human check** section")
    if need_adv:
        _prereq(ack_adv, "Advisory points considered  ·  tick the box in the **💡 Advisory** section")

    if not ok_auto:
        st.info("Resolve the failures / mismatches above and re-run the check to unlock the report.")
        return
    if not (ack_human and ack_adv):
        st.info("Open the sections noted above and tick their confirmations to unlock the report.")
        return

    c1, c2 = st.columns(2)
    name = c1.text_input("Your name (required)", key=f"rep_name_{run_id}")
    team = c2.text_input("Team / designation (optional)", key=f"rep_team_{run_id}")
    if not name.strip():
        st.info("Enter your name to generate the clearance report.")
        return

    try:
        pdf = report.build_clearance_pdf(v, name.strip(), team.strip(), ack_human, ack_adv)
    except Exception as exc:  # noqa: BLE001 — never crash the page on a report error
        st.error(f"Could not build the report: {type(exc).__name__}: {exc}")
        return

    stem = (v["meta"].get("source_filename") or "creative").rsplit(".", 1)[0]
    fname = f"clearance_{stem}_{run_id}.pdf"
    st.success("All prerequisites met. The report is ready to download.")
    st.download_button("⬇ Download clearance report (PDF)", data=pdf, file_name=fname,
                       mime="application/pdf", type="primary")
