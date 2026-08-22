"""Render helpers for the Streamlit UI.

Built for the primary user: a marketing / product / design person running a
creative through a FIRST-PASS self-check. The human-check items and advisory
points are for THAT team to review (looping in compliance only where they judge
it necessary), not things the tool punts to compliance.

Attention is channelled in priority order via a one-section-at-a-time switcher
(the dashboard doubles as the switcher), so a heavy verdict is never a long
scroll. Sections use responsive two-column cards, except the fact-check, whose
cards carry an internal three-column comparison and stay full-width.

Pure display: each takes the verdict dict (and the run id for widget-state
namespacing) and writes to the page. The three layers stay separate and are
never merged (README §3).
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
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEV_TINT = {"critical": "red", "high": "amber", "medium": "slate", "low": "neutral"}

# Sections in PRIORITY ORDER. 'report' is the end goal and sits last.
_SECTIONS = ["must_fix", "facts", "human", "advisory", "passed", "report"]
_SECTION_META = {
    "must_fix": ("🔴", "Fix these"),
    "facts": ("🧾", "Fact check"),
    "human": ("🟠", "Human check"),
    "advisory": ("💡", "Advisory"),
    "passed": ("✅", "Passed"),
    "report": ("📄", "Report"),
}
_FACT = {
    "mismatch": ("🔴", "Doesn't match the factsheet"),
    "ambiguous": ("🟠", "Can't fully confirm"),
    "not_found": ("⚪", "Not in the factsheet"),
    "match": ("🟢", "Matches the factsheet"),
}


# ---- small accessors ---------------------------------------------------------
def _fails(v):
    return [r for r in v["rule_layer"]["results"] if r["verdict"] == "fail"]


def _checks(v):
    return [r for r in v["rule_layer"]["results"] if r["verdict"] == "needs_review"]


def _passed(v):
    return [r for r in v["rule_layer"]["results"] if r["verdict"] == "pass"]


def _na(v):
    return sum(1 for r in v["rule_layer"]["results"] if r["verdict"] == "not_applicable")


def _counts(v: dict) -> dict:
    s = v["summary_strip"]
    return {"must_fix": s["failed"], "facts": s["fact_mismatches"], "human": s["needs_review"],
            "advisory": s["advisory_notes"], "passed": s["passed"], "report": 0}


def ack_keys(run_id: int) -> tuple[str, str]:
    """DURABLE (non-widget) session keys holding the two acknowledgement values,
    so they survive even when their checkbox isn't currently rendered (sections
    show one at a time). The report gate reads these."""
    return f"ack_human_val_{run_id}", f"ack_advisory_val_{run_id}"


def _persist_checkbox(label: str, val_key: str, widget_key: str, help: str | None = None) -> None:
    st.session_state.setdefault(val_key, False)
    if widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state[val_key]
    st.checkbox(label, key=widget_key, help=help,
                on_change=lambda: st.session_state.__setitem__(val_key, st.session_state[widget_key]))


# ---- headline + context ------------------------------------------------------
def headline(v: dict) -> None:
    s = v["summary_strip"]
    fails, review, facts = s["failed"], s["needs_review"], s["fact_mismatches"]
    if fails or facts:
        bits = []
        if fails:
            bits.append(f"**{fails}** rule issue{'' if fails == 1 else 's'} to fix")
        if facts:
            bits.append(f"**{facts}** factual mismatch{'' if facts == 1 else 'es'}")
        tail = f" Then **{review}** item(s) still need a manual review by your team." if review else ""
        st.error("🔴 **Not ready to send yet.** Fix " + " and ".join(bits) + " below." + tail)
    elif review:
        st.warning(f"🟠 **Nothing to fix on the automated checks.** **{review}** item(s) still need a "
                   "manual review by your team before you publish.")
    else:
        st.success("🟢 **Passed the automated first-pass checks.** This isn't a compliance sign-off "
                   "(your compliance team still gives the final OK), but you've caught the common issues.")


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
    for name in ("must_fix", "facts", "human", "advisory"):
        if counts[name]:
            return name
    return "passed"


def results(v: dict, run_id: int) -> None:
    counts = _counts(v)
    s = v["summary_strip"]
    na = _na(v)
    ok_auto, _ = report.automated_clear(v)

    state_key = f"section_{run_id}"
    active = st.session_state.get(state_key) or _default_section(counts)

    # #3: a line that actually reconciles with "rules ran".
    st.markdown(
        f"**{s['rules_run']}** rules ran for your selection:  "
        f"**{s['failed']}** to fix · **{s['needs_review']}** to review · "
        f"**{s['passed']}** passed · **{na}** not applicable to this creative.")
    st.caption("Fact-check and advisory below are **separate layers**, not part of the rule count. "
               "Work the buttons left to right: fixing failures first, then the fact-check.")

    cols = st.columns(len(_SECTIONS))
    clicked = None
    for col, name in zip(cols, _SECTIONS):
        icon, label = _SECTION_META[name]
        if name == "report":
            btn_label = f"{icon} {label}" + ("" if ok_auto else " 🔒")
            disabled = False
        else:
            n = counts[name]
            btn_label = f"{icon} {label} · {n}"
            disabled = (n == 0 and name != "passed")
        if col.button(btn_label, key=f"nav_{name}_{run_id}", use_container_width=True,
                      type="primary" if name == active else "secondary", disabled=disabled):
            clicked = name
    if clicked and clicked != active:
        st.session_state[state_key] = clicked
        st.rerun()

    {"must_fix": _sec_must_fix, "facts": _sec_facts, "human": _sec_human, "advisory": _sec_advisory,
     "passed": _sec_passed, "report": _sec_report}[active](v, run_id)


# ---- card primitives ---------------------------------------------------------
def _stack(cards: list[str]) -> None:
    """Single-column stack of full-width cards. Chosen over a grid because the
    cards vary a lot in height, and a grid leaves ragged, uneven rows."""
    st.markdown("".join(cards), unsafe_allow_html=True)


def _sev_chip(sev: str) -> str:
    bg, bd = _TONE.get(_SEV_TINT.get(sev, "neutral"), _TONE["neutral"])
    return (f'<span style="font-size:0.72rem;padding:1px 8px;border-radius:10px;'
            f'background:{bg};border:1px solid {bd};white-space:nowrap;">{_esc(sev or "—")}</span>')


def _details(r: dict) -> str:
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
            f'border-radius:8px;padding:10px 12px;margin:8px 0;">{body}</div>')


def _fix_card(r: dict) -> str:
    title = _esc(r.get("title") or r["rule_id"])
    why = _esc(r.get("explanation") or r.get("description") or "")
    fix = r.get("suggested_rewrite")
    sev = _esc(r.get("severity", ""))
    body = (f'<div style="font-weight:600;">🔴 {title}'
            f'<span style="font-size:0.72rem;opacity:0.55;font-weight:400;"> · {sev}</span></div>')
    if why:
        body += f'<div style="margin-top:2px;font-size:0.92rem;">{why}</div>'
    if fix:
        body += f'<div style="margin-top:6px;font-size:0.92rem;"><b>✏️ Change:</b> {_esc(fix)}</div>'
    body += _details(r)
    return _shell("rgba(220,38,38,0.75)", body)


def _check_card(r: dict) -> str:
    title = _esc(r.get("title") or r["rule_id"])
    what = _esc(r.get("description") or r.get("explanation") or "")
    body = f'<div style="font-weight:600;">🟠 {title}</div>'
    if what:
        body += f'<div style="margin-top:2px;font-size:0.92rem;">Confirm: {what}</div>'
    body += _details(r)
    return _shell("rgba(217,119,6,0.75)", body)


def _adv_card(n: dict) -> str:
    tag = (f'<span style="font-size:0.7rem;opacity:0.6;">[{_esc(n["area"])}]</span> ' if n.get("area") else "")
    return _shell("rgba(100,116,139,0.7)", f'<div style="font-size:0.92rem;">💡 {tag}{_esc(n.get("note", ""))}</div>')


# ---- sections ----------------------------------------------------------------
def _sec_must_fix(v: dict, run_id: int) -> None:
    fails = _fails(v)
    st.markdown(f"#### 🔴 Fix these to pass · {len(fails)}")
    st.caption("Layer 1 · rule checks. Your primary job: make each edit, then re-run the check.")
    if not fails:
        st.success("Nothing to fix — no rule failures for your selection. Move on to **Fact check**.")
        return
    _stack([_fix_card(r) for r in sorted(fails, key=lambda r: _SEV_ORDER.get(r.get("severity"), 9))])


def _sec_facts(v: dict, run_id: int) -> None:
    st.markdown("#### 🧾 Factsheet fact-check")
    st.caption("Layer 2 · the numbers in your creative, checked against the published factsheet. "
               "A separate layer — **never** part of the compliance score.")
    results_ = v["fact_check_layer"]["results"]
    if not results_:
        st.info("Fact-check needs the model (no API key set)." if not model.available()
                else "No checkable factual claims found in the creative.")
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


def _sec_human(v: dict, run_id: int) -> None:
    checks = _checks(v)
    ack_human, _ = ack_keys(run_id)
    st.markdown(f"#### 🟠 Human check · {len(checks)}")
    st.caption("Layer 1 · rules the tool can't decide alone. **Your team reviews these** as part of the "
               "first-pass check (loop in compliance only where you judge it necessary).")
    if not checks:
        st.success("Nothing needs a manual check for this creative.")
        return
    _stack([_check_card(r) for r in checks])
    st.write("")
    _persist_checkbox("I confirm each item above has been reviewed by our team.",
                      ack_human, f"ack_human_cb_{run_id}",
                      help="Required before a clearance report can be generated.")


def _sec_advisory(v: dict, run_id: int) -> None:
    notes = v["advisory_layer"]["notes"]
    _, ack_adv = ack_keys(run_id)
    st.markdown("#### 💡 Advisory")
    st.caption("Layer 3 · a second read that sets the rules aside. **Unscored — not a verdict.** "
               "Points that could materially mislead a reader, for your team to weigh.")
    if not notes:
        st.info("Advisory needs the model (no API key set)." if not model.available()
                else "Nothing flagged — the copy reads fair on a second pass.")
        return
    _stack([_adv_card(n) for n in notes])
    st.write("")
    _persist_checkbox("I confirm the advisory points above have been read and considered.",
                      ack_adv, f"ack_advisory_cb_{run_id}",
                      help="Required before a clearance report can be generated.")


def _sec_passed(v: dict, run_id: int) -> None:
    passed = _passed(v)
    na = _na(v)
    st.markdown(f"#### ✅ Passed · {len(passed)}")
    st.caption(f"Rules this creative already satisfies. ({na} more were not applicable to it.)")
    if not passed:
        st.info("No scored rules passed yet — work the **Fix these** list first.")
        return
    # A table reads better than cards for this terse content: Rule | Requirement | Severity.
    rows = "".join(
        '<tr style="border-bottom:1px solid rgba(128,128,128,0.15);">'
        f'<td style="padding:7px 12px;font-family:ui-monospace,Consolas,monospace;'
        f'white-space:nowrap;vertical-align:top;color:rgba(22,163,74,0.95);">{_esc(r["rule_id"])}</td>'
        f'<td style="padding:7px 12px;vertical-align:top;">{_esc(r.get("title") or "")}</td>'
        f'<td style="padding:7px 12px;vertical-align:top;white-space:nowrap;">{_sev_chip(r.get("severity",""))}</td>'
        '</tr>'
        for r in sorted(passed, key=lambda r: (_SEV_ORDER.get(r.get("severity"), 9), r["rule_id"])))
    st.markdown(
        '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.9rem;">'
        '<thead><tr style="text-align:left;border-bottom:1px solid rgba(128,128,128,0.35);">'
        '<th style="padding:7px 12px;width:118px;opacity:0.6;font-weight:600;">Rule</th>'
        '<th style="padding:7px 12px;opacity:0.6;font-weight:600;">Requirement it satisfies</th>'
        '<th style="padding:7px 12px;width:92px;opacity:0.6;font-weight:600;">Severity</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)


# ---- report section (gate + download) ---------------------------------------
def _prereq(done: bool, text: str) -> None:
    st.markdown(f"{'✅' if done else '⬜'} {text}")


def _sec_report(v: dict, run_id: int) -> None:
    st.markdown("#### 📄 Clearance report")
    st.caption("A record to attach when you hand this creative to compliance. It is a first-pass "
               "check, **not** a sign-off. It unlocks once everything below is done.")

    counts = _counts(v)
    ok_auto, _ = report.automated_clear(v)
    ack_human_key, ack_adv_key = ack_keys(run_id)
    need_human, need_adv = counts["human"] > 0, counts["advisory"] > 0
    ack_human = (not need_human) or bool(st.session_state.get(ack_human_key))
    ack_adv = (not need_adv) or bool(st.session_state.get(ack_adv_key))

    _prereq(counts["must_fix"] == 0, f"No rule failures  ·  {counts['must_fix']} to fix")
    _prereq(counts["facts"] == 0, f"No factual mismatches  ·  {counts['facts']} to resolve")
    if need_human:
        _prereq(ack_human, "Human-check items reviewed  ·  tick the box in the **🟠 Human check** tab")
    if need_adv:
        _prereq(ack_adv, "Advisory points considered  ·  tick the box in the **💡 Advisory** tab")

    if not ok_auto:
        st.info("Resolve the failures / mismatches above and re-run the check to unlock the report.")
        return
    if not (ack_human and ack_adv):
        st.info("Open the tabs noted above and tick their confirmations to unlock the report.")
        return

    c1, c2 = st.columns(2)
    name = c1.text_input("Your name (required)", key=f"rep_name_{run_id}")
    team = c2.text_input("Team / designation (optional)", key=f"rep_team_{run_id}")
    if not name.strip():
        st.info("Enter your name to generate the clearance report.")
        return
    try:
        pdf = report.build_clearance_pdf(v, name.strip(), team.strip(), ack_human, ack_adv)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not build the report: {type(exc).__name__}: {exc}")
        return
    stem = (v["meta"].get("source_filename") or "creative").rsplit(".", 1)[0]
    st.success("All prerequisites met. The report is ready.")
    st.download_button("⬇ Download clearance report (PDF)", data=pdf,
                       file_name=f"clearance_{stem}_{run_id}.pdf", mime="application/pdf", type="primary")
