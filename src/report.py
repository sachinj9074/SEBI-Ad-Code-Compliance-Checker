"""Clearance report: a downloadable PDF the marketing / product user can attach
when sending a creative to the compliance team.

It is produced ONLY when the first-pass check is clean (no rule failures, no
factsheet mismatches) and the user has acknowledged the human-review items and
advisory points. The report is explicit that it is a first-pass self-check, NOT
a compliance sign-off.

`automated_clear` is the pure eligibility check (failures + fact mismatches);
the acknowledgement/name gate lives in the UI. `build_clearance_pdf` renders the
bytes. No model calls.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fpdf import FPDF

# Core PDF fonts are latin-1; map the few non-latin-1 characters our data can
# carry, then drop anything else, so a stray glyph never breaks the report.
_SUBST = {
    "₹": "Rs ",  # rupee
    "–": "-", "—": "-",  # en / em dash
    "‘": "'", "’": "'",  # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
    "•": "-", "…": "...",  # bullet, ellipsis
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


# ---- PDF helpers -------------------------------------------------------------
_INK = (27, 35, 48)
_MUTED = (88, 97, 113)
_RULE = (210, 216, 224)


class _Report(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, _san("First-pass self-check produced by the SEBI Ad-Code Compliance Checker. "
                             "Not a compliance sign-off. "), align="L")
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")


def _h(pdf, text):
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 7, _san(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_RULE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)


def _kv(pdf, key, value):
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(42, 5, _san(key), new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 5, _san(value), new_x="LMARGIN", new_y="NEXT")


def _line(pdf, text, bold=False, size=9, gap=5):
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, gap, _san(text), new_x="LMARGIN", new_y="NEXT")


def build_clearance_pdf(verdict: dict, reviewer: str, team: str,
                        ack_human: bool, ack_advisory: bool) -> bytes:
    meta = verdict["meta"]
    s = verdict["summary_strip"]
    results = verdict["rule_layer"]["results"]
    passed = [r for r in results if r["verdict"] == "pass"]
    na = sum(1 for r in results if r["verdict"] == "not_applicable")
    human = [r for r in results if r["verdict"] == "needs_review"]
    facts = verdict["fact_check_layer"]["results"]
    advisory = verdict["advisory_layer"]["notes"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf = _Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 9, _san("First-Pass Compliance Check: Clearance Summary"),
             new_x="LMARGIN", new_y="NEXT")

    # Prominent disclaimer band
    pdf.ln(1)
    pdf.set_fill_color(253, 242, 242)
    pdf.set_draw_color(220, 38, 38)
    pdf.set_text_color(150, 20, 20)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.multi_cell(0, 4.6, _san(
        "This is a first-pass self-check produced by an automated tool. It is NOT a compliance "
        "sign-off or regulatory clearance. Final approval rests with the compliance team. Human-review "
        "items and advisory points listed here were acknowledged by the reviewer, not decided by the tool."),
        border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)

    # Creative identity
    _h(pdf, "Creative")
    _kv(pdf, "File name", meta.get("source_filename", "-"))
    _kv(pdf, "Content SHA-256", meta.get("content_sha256", "not recorded"))
    _kv(pdf, "Checked on", meta.get("run_at", "-"))
    _kv(pdf, "Extraction", f"{verdict['extraction'].get('source_kind', '-')} "
                           f"({verdict['extraction'].get('confidence', 0):.0%} confidence)")
    _kv(pdf, "Tool / model", f"v{meta.get('tool_version', '-')} / {meta.get('model_used', '-')}")

    # Scope
    _h(pdf, "Scope checked")
    _kv(pdf, "Business area", ", ".join(meta.get("areas_selected", [])) or "-")
    _kv(pdf, "Creative type(s)", ", ".join(meta.get("creative_type", [])) or "(none / IAP)")
    for w in meta.get("selection_warnings", []):
        pdf.set_text_color(150, 90, 10)
        _line(pdf, "Scope note: " + w, size=8.5)
        pdf.set_text_color(*_INK)

    # Reviewer + acknowledgements
    _h(pdf, "Reviewer and acknowledgements")
    _kv(pdf, "Cleared by", reviewer + (f"  ({team})" if team else ""))
    _kv(pdf, "Generated", now)
    pdf.ln(1)
    amb = sum(1 for r in facts if r["verdict"] == "ambiguous")
    acks = [
        f"[x] All mandatory automated rule checks passed: {len(passed)} passed, 0 failed, "
        f"{na} not applicable to this creative.",
        f"[x] Factsheet fact-check cleared: 0 mismatches"
        + (f"; {amb} match(es) under a stated assumption, listed below." if amb else "."),
    ]
    if human:
        acks.append(f"[x] The {len(human)} human-review item(s) below were manually reviewed by the reviewer.")
    if advisory:
        acks.append(f"[x] The {len(advisory)} advisory point(s) below were read and considered.")
    for a in acks:
        _line(pdf, a, size=9, gap=5.2)

    # Automated rule checks passed
    _h(pdf, f"Automated rule checks passed ({len(passed)})")
    if passed:
        for r in passed:
            _line(pdf, f"- {r['rule_id']}: {r.get('title', '')} ({r.get('severity', '')})", size=8.5, gap=4.6)
    else:
        _line(pdf, "No scored automated rules applied to this creative.", size=8.5)

    # Fact-check
    _h(pdf, "Factsheet fact-check")
    if not facts:
        _line(pdf, "No checkable factual claims were found in the creative.", size=8.5)
    else:
        for r in facts:
            v = r["verdict"]
            tag = {"match": "MATCH", "ambiguous": "MATCH (assumption)",
                   "not_found": "not in factsheet", "mismatch": "MISMATCH"}.get(v, v)
            _line(pdf, f"- [{tag}] \"{r.get('claim_text', '')}\"", bold=True, size=8.5, gap=4.6)
            detail = (f"    creative: {r.get('claimed_value', '-')}   |   "
                      f"factsheet: {r.get('factsheet_value', '-')}   |   as of {r.get('as_of_date', '-')}")
            _line(pdf, detail, size=8, gap=4.4)
            if r.get("assumption"):
                _line(pdf, f"    assumption: {r['assumption']}", size=8, gap=4.4)

    # Human-review items
    if human:
        _h(pdf, f"Human-review items (acknowledged as reviewed) ({len(human)})")
        for r in human:
            _line(pdf, f"- {r['rule_id']}: {r.get('title', '')}", size=8.5, gap=4.6)
            if r.get("description"):
                _line(pdf, f"    {r['description']}", size=8, gap=4.4)

    # Advisory
    if advisory:
        _h(pdf, f"Advisory points (acknowledged as considered) ({len(advisory)})")
        for n in advisory:
            area = f"[{n['area']}] " if n.get("area") else ""
            _line(pdf, f"- {area}{n.get('note', '')}", size=8.5, gap=4.6)

    out = pdf.output()
    return bytes(out)
