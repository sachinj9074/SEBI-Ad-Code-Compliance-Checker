"""Clearance report: a downloadable PDF the marketing / product user can attach
when sending a creative to the compliance team.

It is produced ONLY when the first-pass check is clean (no rule failures, no
factsheet mismatches) and the user has acknowledged the human-review items and
advisory points. The report is explicit that it is a first-pass self-check, NOT
a compliance sign-off.

Layout is "status-forward" (README §7): a colour-coded at-a-glance strip, then
tables so the compliance reader sees, at a glance, what passed, what was assumed,
and what is still open for a human. `automated_clear` is the pure eligibility
check (failures + fact mismatches); the acknowledgement/name gate lives in the
UI. `build_clearance_pdf` renders the bytes. No model calls.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fpdf import FPDF
from fpdf.fonts import FontFace

# Core PDF fonts are latin-1; map the few non-latin-1 characters our data can
# carry, then drop anything else, so a stray glyph never breaks the report.
_SUBST = {
    "₹": "Rs ",  # rupee
    "–": "-", "—": "-",  # en / em dash
    "‘": "'", "’": "'",  # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
    "•": "-", "…": "...",  # bullet, ellipsis
    "≥": ">=", "™": "",
}


def _san(text) -> str:
    s = str(text)
    for k, v in _SUBST.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def automated_clear(verdict: dict) -> tuple[bool, list[str]]:
    """Whether the automated + fact-check side is clean. Returns (ok, blockers)."""
    s = verdict["summary_strip"]
    blockers = []
    if s["failed"]:
        blockers.append(f"{s['failed']} rule failure(s) still to fix")
    if s["fact_mismatches"]:
        blockers.append(f"{s['fact_mismatches']} factual mismatch(es) still to resolve")
    return (not blockers), blockers


# ---- palette ----------------------------------------------------------------
_INK = (24, 32, 44)
_MUTED = (96, 105, 120)
_HAIR = (214, 220, 228)
_HEAD_BG = (238, 241, 246)

# status swatches: (text colour, light fill)
_GREEN = ((22, 101, 52), (220, 252, 231))
_RED = ((153, 27, 27), (254, 226, 226))
_AMBER = ((146, 64, 14), (254, 243, 199))
_BLUE = ((55, 48, 120), (226, 231, 252))

# severity -> (text colour, light fill) for the chips
_SEV = {
    "critical": ((150, 20, 20), (253, 232, 232)),
    "high": ((150, 80, 6), (254, 243, 214)),
    "medium": ((51, 65, 85), (226, 232, 240)),
    "low": ((80, 88, 100), (241, 243, 246)),
}

# human labels over the internal tags (kept in sync with app/app.py)
_AREA_LABELS = {
    "scheme_related": "Scheme-related",
    "iap": "Investor Awareness Programme (IAP)",
    "others_media": "Others & Media",
}
_CTYPE_LABELS = {
    "nfo": "NFO", "key_visual": "Key visual", "yield": "Yield / debt",
    "social_post": "Social media post", "article": "Article", "blog": "Blog",
    "anniversary": "Anniversary",
}


# ---- data shaping -----------------------------------------------------------
def _dig(verdict: dict):
    meta = verdict["meta"]
    s = verdict["summary_strip"]
    results = verdict["rule_layer"]["results"]
    passed = [r for r in results if r["verdict"] == "pass"]
    human = [r for r in results if r["verdict"] == "needs_review"]
    na = sum(1 for r in results if r["verdict"] == "not_applicable")
    facts = verdict["fact_check_layer"]["results"]
    advisory = verdict["advisory_layer"]["notes"]
    return meta, s, passed, human, na, facts, advisory


def _fact_note(r: dict) -> str:
    v = r["verdict"]
    if v == "match":
        return "Matches the factsheet."
    if v == "ambiguous":
        a = r.get("assumption")
        return "Matches under assumption: " + a if a else "Matches under a stated assumption."
    if v == "not_found":
        a = r.get("assumption") or "no matching record in the factsheet KB"
        return "Not verified against factsheet data (" + a + ")."
    if v == "mismatch":
        return "MISMATCH vs factsheet."
    return v


def _assumption_lines(facts: list[dict]) -> list[str]:
    """Every caveat the clearance quietly rests on, spelled out."""
    lines = []
    for r in facts:
        if r["verdict"] in ("ambiguous", "not_found") or r.get("assumption"):
            claim = r.get("claim_text", "claim")
            lines.append(f'"{claim}" - {_fact_note(r)}')
    return lines


def _creative_scope_rows(meta: dict, verdict: dict) -> list[tuple[str, str]]:
    ext = verdict["extraction"]
    return [
        ("File name", meta.get("source_filename", "-")),
        ("Content SHA-256", meta.get("content_sha256", "not recorded")),
        ("Checked on", meta.get("run_at", "-")),
        ("Extraction", f"{ext.get('source_kind', '-')} ({ext.get('confidence', 0):.0%} confidence)"),
        ("Tool / model", f"v{meta.get('tool_version', '-')} / {meta.get('model_used', '-')}"),
        ("Business area", ", ".join(_AREA_LABELS.get(a, a) for a in meta.get("areas_selected", [])) or "-"),
        ("Creative type(s)", ", ".join(_CTYPE_LABELS.get(c, c) for c in meta.get("creative_type", [])) or "(none / IAP)"),
    ]


# ---- PDF primitives ---------------------------------------------------------
class _Report(FPDF):
    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, _san("First-pass self-check by the SEBI Ad-Code Compliance Checker. "
                             "Not a compliance sign-off."), align="L")
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")


def _reset(pdf):
    """Clear the doc fill/font so the next table draws a white body in a regular
    weight (fpdf2 tables fill body cells with the current fill colour and inherit
    the current font emphasis for cells whose FontFace leaves emphasis unset)."""
    pdf.set_fill_color(255, 255, 255)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_INK)


def _band(pdf, text, rgb):
    """A colour-coded left-bar section header."""
    pdf.ln(1)
    y = pdf.get_y()
    pdf.set_fill_color(*rgb)
    pdf.rect(pdf.l_margin, y, 2.2, 5.6, style="F")
    pdf.set_xy(pdf.l_margin + 4, y)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*rgb)
    pdf.cell(0, 5.6, _san(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    _reset(pdf)
    pdf.ln(1.5)


def _muted(pdf, text):
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 5, _san(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)


def _kv_table(pdf, rows):
    _reset(pdf)
    with pdf.table(col_widths=(40, 146), first_row_as_headings=False, line_height=5.4,
                   borders_layout="NONE", text_align=("LEFT", "LEFT"), width=186) as t:
        for k, v in rows:
            row = t.row()
            row.cell(_san(k), style=FontFace(color=_MUTED, emphasis="BOLD", size_pt=8.5))
            row.cell(_san(v), style=FontFace(color=_INK, size_pt=8.5))


def _title_and_disclaimer(pdf):
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 9, _san("First-Pass Compliance Check: Clearance Summary"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_fill_color(253, 242, 242)
    pdf.set_draw_color(220, 38, 38)
    pdf.set_text_color(150, 20, 20)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.multi_cell(0, 4.6, _san(
        "This is a first-pass self-check produced by an automated tool. It is NOT a compliance "
        "sign-off or regulatory clearance. Final approval rests with the compliance team. The "
        "human-review and advisory items below were acknowledged by the named reviewer, not "
        "decided by the tool."),
        border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    _reset(pdf)
    pdf.ln(2)


def _table_head(t, labels):
    row = t.row()
    for lab in labels:
        row.cell(_san(lab))


# ---- report -----------------------------------------------------------------
def build_clearance_pdf(verdict: dict, reviewer: str, team: str,
                        ack_human: bool, ack_advisory: bool) -> bytes:
    meta, s, passed, human, na, facts, advisory = _dig(verdict)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    amb = sum(1 for r in facts if r["verdict"] == "ambiguous")

    pdf = _Report(format="A4")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    pdf.add_page()

    _title_and_disclaimer(pdf)

    # ---- at a glance: colour tiles -----------------------------------------
    tiles = [
        ("Passed", s["passed"], _GREEN),
        ("To fix", s["failed"], _GREEN if s["failed"] == 0 else _RED),
        ("Human review", s["needs_review"], _AMBER if s["needs_review"] else _GREEN),
        ("Fact mismatches", s["fact_mismatches"], _GREEN if s["fact_mismatches"] == 0 else _RED),
        ("Advisory", s["advisory_notes"], _BLUE if s["advisory_notes"] else _GREEN),
    ]
    with pdf.table(col_widths=(1, 1, 1, 1, 1), line_height=6, text_align="CENTER",
                   borders_layout="ALL", width=186, first_row_as_headings=False,
                   gutter_width=1.5) as t:
        r = t.row()
        for lab, _v, (fg, bg) in tiles:
            r.cell(_san(lab), style=FontFace(color=fg, emphasis="BOLD", size_pt=8, fill_color=bg))
        r = t.row()
        for lab, v, (fg, bg) in tiles:
            r.cell(str(v), style=FontFace(color=fg, emphasis="BOLD", size_pt=17, fill_color=bg))
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 4.4, _san(
        f"{s['rules_run']} rules ran for this scope; {na} were not applicable to this creative. "
        "Green = clear. Passed / to-fix / human-review are the scored rule layer; fact mismatches "
        "and advisory are separate layers."), new_x="LMARGIN", new_y="NEXT")
    _reset(pdf)
    pdf.ln(2)

    # ---- creative & scope ---------------------------------------------------
    _band(pdf, "Creative & scope checked", (71, 85, 105))
    _kv_table(pdf, _creative_scope_rows(meta, verdict))
    for w in meta.get("selection_warnings", []):
        pdf.set_text_color(150, 90, 10)
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4.4, _san("Scope note: " + w), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_INK)
    pdf.ln(1.5)

    # ---- reviewer & acknowledgements ---------------------------------------
    _band(pdf, "Reviewer & acknowledgements", (71, 85, 105))
    _kv_table(pdf, [("Cleared by", reviewer + (f"  ({team})" if team else "")), ("Generated", now)])
    pdf.ln(0.5)
    acks = [
        f"[x]  Mandatory automated rule checks passed: {len(passed)} passed, 0 failed, {na} not applicable.",
        f"[x]  Factsheet fact-check cleared: 0 mismatches"
        + (f"; {amb} match(es) under a stated assumption." if amb else "."),
    ]
    if human:
        acks.append(f"[x]  The {len(human)} human-review item(s) below were manually reviewed by the reviewer.")
    if advisory:
        acks.append(f"[x]  The {len(advisory)} advisory point(s) below were read and considered.")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_INK)
    for a in acks:
        pdf.multi_cell(0, 5, _san(a), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)

    # ---- assumptions & caveats ---------------------------------------------
    _band(pdf, "Assumptions & caveats this clearance rests on", (180, 130, 20))
    pdf.set_fill_color(255, 251, 235)
    pdf.set_draw_color(230, 200, 120)
    pdf.set_text_color(90, 70, 20)
    pdf.set_font("Helvetica", "", 8.5)
    body = _assumption_lines(facts) + [
        "Human-review and advisory items were acknowledged by the reviewer, not decided by the tool.",
        "Fact-check is against a dated factsheet snapshot; figures may move at the next monthly refresh.",
    ]
    pdf.multi_cell(0, 5, "\n".join("-  " + _san(b) for b in body),
                   border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    _reset(pdf)
    pdf.ln(2)

    # ---- passed checks (severity chips) ------------------------------------
    _band(pdf, f"Passed automated checks ({len(passed)})", (22, 120, 60))
    if not passed:
        _muted(pdf, "No scored automated rules applied to this creative.")
    else:
        with pdf.table(col_widths=(26, 132, 28), line_height=5.4, width=186,
                       borders_layout="HORIZONTAL_LINES", v_align="MIDDLE",
                       headings_style=FontFace(color=_INK, emphasis="BOLD", size_pt=8, fill_color=_HEAD_BG),
                       text_align=("LEFT", "LEFT", "CENTER")) as t:
            _table_head(t, ("Rule", "Requirement it satisfies", "Severity"))
            for rule in sorted(passed, key=lambda r: r["rule_id"]):
                sev = (rule.get("severity") or "").lower()
                fg, bg = _SEV.get(sev, (_MUTED, (240, 240, 240)))
                r = t.row()
                r.cell(_san(rule["rule_id"]), style=FontFace(color=(22, 120, 60), emphasis="BOLD", size_pt=8))
                r.cell(_san(rule.get("title", "")), style=FontFace(color=_INK, size_pt=8))
                r.cell(_san(sev.upper()), style=FontFace(color=fg, emphasis="BOLD", size_pt=7, fill_color=bg))
    pdf.ln(2)

    # ---- fact-check --------------------------------------------------------
    _band(pdf, f"Factsheet fact-check ({len(facts)} claim{'s' if len(facts) != 1 else ''})", (30, 90, 160))
    if not facts:
        _muted(pdf, "No checkable factual claims were found in the creative.")
    else:
        with pdf.table(col_widths=(54, 28, 30, 24, 50), line_height=4.8, width=186,
                       borders_layout="HORIZONTAL_LINES",
                       headings_style=FontFace(color=_INK, emphasis="BOLD", size_pt=8, fill_color=_HEAD_BG),
                       text_align="LEFT") as t:
            _table_head(t, ("Claim", "Creative says", "Factsheet says", "As of", "Note"))
            for f in facts:
                r = t.row()
                r.cell(_san(f.get("claim_text", "")), style=FontFace(size_pt=7.5))
                r.cell(_san(f.get("claimed_value", "-")), style=FontFace(size_pt=7.5))
                r.cell(_san(f.get("factsheet_value", "-")), style=FontFace(size_pt=7.5))
                r.cell(_san(f.get("as_of_date", "-")), style=FontFace(size_pt=7.5))
                r.cell(_san(_fact_note(f)), style=FontFace(color=(120, 90, 20), size_pt=7.5))
    pdf.ln(2)

    # ---- human review ------------------------------------------------------
    if human:
        _band(pdf, f"Open for human review ({len(human)})", (150, 90, 10))
        with pdf.table(col_widths=(26, 160), line_height=5, width=186,
                       borders_layout="HORIZONTAL_LINES",
                       headings_style=FontFace(color=_INK, emphasis="BOLD", size_pt=8, fill_color=_HEAD_BG),
                       text_align="LEFT") as t:
            _table_head(t, ("Rule", "What a person must confirm"))
            for rule in human:
                r = t.row()
                r.cell(_san(rule["rule_id"]), style=FontFace(color=(150, 90, 10), emphasis="BOLD", size_pt=8))
                r.cell(_san(rule.get("description") or rule.get("title", "")), style=FontFace(size_pt=7.8))
        pdf.ln(2)

    # ---- advisory ----------------------------------------------------------
    _band(pdf, f"Advisory notes ({len(advisory)})", (55, 48, 120))
    if not advisory:
        _muted(pdf, "No advisory observations were raised for this creative.")
    else:
        with pdf.table(col_widths=(30, 156), line_height=5, width=186,
                       borders_layout="HORIZONTAL_LINES",
                       headings_style=FontFace(color=_INK, emphasis="BOLD", size_pt=8, fill_color=_HEAD_BG),
                       text_align="LEFT") as t:
            _table_head(t, ("Area", "Observation"))
            for n in advisory:
                r = t.row()
                r.cell(_san(n.get("area", "-")), style=FontFace(color=_MUTED, size_pt=7.8))
                r.cell(_san(n.get("note", "")), style=FontFace(size_pt=7.8))

    return bytes(pdf.output())
