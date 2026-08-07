"""Generate the marketing-material segmentation map from the corpus.

Emits:
  - corpus/SEGMENTS.md      taxonomy (3 axes) + coverage matrix (markdown, versioned)
  - review/segments_matrix.html  a visual heatmap of the same matrix (for an artifact)

The corpus filters to a run by two axes: business area (applies_to) and creative
type (creative_type). A rule is in scope for a run when
    creative_type contains the selected type  AND
    applies_to contains 'all' or one of the selected areas.
Conditional rules then only fire if their trigger feature is detected; this map
counts a rule as in-scope after the area+type filter (feature is content-dependent).

Run:  .venv\\Scripts\\python.exe scripts/build_segments.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "corpus" / "rules"
OUT_MD = ROOT / "corpus" / "SEGMENTS.md"
OUT_HTML = ROOT / "review" / "segments_matrix.html"

# --- axis definitions -------------------------------------------------------
AREAS = [
    ("all", "Applies to every business area (the unconditional baseline).", "implicit"),
    ("mf_scheme", "Mutual-fund scheme advertisements.", "v1"),
    ("nfo", "New Fund Offer creatives — additive to mf_scheme (an NFO is an MF scheme).", "v1"),
    ("iap", "Investor awareness / education initiatives.", "v1"),
    ("non_iap", "Non-IAP material.", "future"),
    ("aif", "Alternative Investment Fund material.", "future"),
    ("pms", "Portfolio Management Service material.", "future"),
    ("branding", "Brand / corporate creatives.", "future"),
    ("social_media", "Social-handle / branding material.", "future"),
]
CTYPES = [
    ("general_kv", "A general 'key visual' creative.", "v1"),
    ("anniversary", "A scheme / fund anniversary post.", "v1"),
    ("yield", "A creative showing yield / YTM.", "v1"),
    ("article_blog", "A long-form article or blog.", "v1"),
    ("social_post", "A social-media post.", "v1"),
    ("video", "A video creative.", "encoded, inactive in v1"),
]
FILE_FORMATS = [
    ("DOCX", "Text extracted directly. Build-first format."),
    ("PDF (text layer)", "Text extracted directly."),
    ("PDF (scanned / image)", "No text layer — vision pipeline."),
    ("Image / banner", "Vision pipeline (layout, legibility, prominent-person)."),
    ("Carousel", "Multi-image — each frame through the image pipeline, grouped per frame."),
]

# selection scenarios shown as matrix columns: label -> set of selected areas
SCENARIOS = [
    ("MF scheme", {"mf_scheme"}),
    ("NFO (+scheme)", {"mf_scheme", "nfo"}),
    ("IAP", {"iap"}),
]
ROW_CTYPES = ["general_kv", "anniversary", "yield", "article_blog", "social_post", "video"]
CT_LABEL = {c: c.replace("_", " ") for c, _, _ in CTYPES}


def load_rules():
    rules = []
    for f in sorted(RULES_DIR.glob("*.json")):
        rules.extend(json.loads(f.read_text(encoding="utf-8")))
    return rules


def in_scope(rule, sel_areas, ctype):
    if ctype not in rule["creative_type"]:
        return False
    ap = set(rule["applies_to"])
    return "all" in ap or bool(ap & sel_areas)


def cell(rules, sel_areas, ctype):
    hits = [r for r in rules if in_scope(r, sel_areas, ctype)]
    uncond = sum(1 for r in hits if r["trigger"]["type"] == "unconditional")
    return len(hits), uncond


def build_md(rules):
    total = len(rules)
    L = []
    L.append("# Marketing-material segmentation")
    L.append("")
    L.append("How the checker breaks a piece of marketing material into segments, and which rules")
    L.append("light up for each. **Generated from `corpus/rules/*.json` by `scripts/build_segments.py`** —")
    L.append("regenerate after any corpus change.")
    L.append("")
    L.append("A creative is classified on three axes. Two of them filter the rule corpus; the third")
    L.append("only chooses the extraction path.")
    L.append("")
    L.append("```mermaid")
    L.append("flowchart LR")
    L.append('    U["Upload"] --> A["Business areas — multi-select"]')
    L.append('    U --> C["Creative type — single-select"]')
    L.append('    U --> F["File format — auto-detected"]')
    L.append('    A --> FIL["Filter corpus"]')
    L.append('    C --> FIL')
    L.append('    F --> EXT["Extraction path: text / vision"]')
    L.append(f'    FIL --> R["In-scope rules (subset of {total})"]')
    L.append("```")
    L.append("")
    L.append("**Filter rule:** a rule is in scope when its `creative_type` includes the selected type")
    L.append("**and** its `applies_to` contains `all` or one of the selected areas. Conditional rules")
    L.append("then fire only if their trigger feature is present in the content.")
    L.append("")

    # Axis 1
    L.append("## Axis 1 — Business area (`applies_to`)")
    L.append("")
    L.append("*What the material is about.* Multi-select; tags are additive, so an NFO creative is")
    L.append("reviewed as **mf_scheme + nfo** (select every area that applies).")
    L.append("")
    L.append("| Segment | Meaning | Status | Rules |")
    L.append("|---|---|---|---|")
    for key, desc, status in AREAS:
        if key == "all":
            n = sum(1 for r in rules if "all" in r["applies_to"])
        else:
            n = sum(1 for r in rules if key in r["applies_to"] or "all" in r["applies_to"])
            if status == "future":
                n = sum(1 for r in rules if key in r["applies_to"])  # concrete-only
        L.append(f"| `{key}` | {desc} | {status} | {n} |")
    L.append("")
    L.append("*(`all`/`mf_scheme`/`nfo`/`iap` counts include the `all`-tagged baseline that applies")
    L.append("to every area; `future` areas show only rules explicitly tagged to them — currently 0.)*")
    L.append("")

    # Axis 2
    L.append("## Axis 2 — Creative type (`creative_type`)")
    L.append("")
    L.append("*What kind of creative it is.* Single-select.")
    L.append("")
    L.append("| Segment | Meaning | Status | Rules |")
    L.append("|---|---|---|---|")
    for key, desc, status in CTYPES:
        n = sum(1 for r in rules if key in r["creative_type"])
        L.append(f"| `{key}` | {desc} | {status} | {n} |")
    L.append("")

    # Axis 3
    L.append("## Axis 3 — File format (auto-detected)")
    L.append("")
    L.append("*How it was supplied.* Chooses the extraction path, **not** which rules apply.")
    L.append("")
    L.append("| Format | Handling |")
    L.append("|---|---|")
    for key, desc in FILE_FORMATS:
        L.append(f"| {key} | {desc} |")
    L.append("")

    # Coverage matrix
    L.append("## Coverage matrix — rules in scope per segment")
    L.append("")
    L.append("Rows = creative type, columns = a realistic area selection. Each cell is")
    L.append("**total in scope** with **always-on (unconditional)** in parentheses; the remainder are")
    L.append("conditional and fire only when their feature is detected.")
    L.append("")
    header = "| Creative type | " + " | ".join(lbl for lbl, _ in SCENARIOS) + " |"
    L.append(header)
    L.append("|" + "---|" * (len(SCENARIOS) + 1))
    for ctype in ROW_CTYPES:
        cells = []
        for _, areas in SCENARIOS:
            tot, unc = cell(rules, areas, ctype)
            cells.append(f"{tot} ({unc})")
        note = " *(inactive)*" if ctype == "video" else ""
        L.append(f"| {CT_LABEL[ctype]}{note} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("> Video is encoded but inactive in v1 — its column counts are what *would* apply once")
    L.append("> video is switched on. IAP is sparse because only its own disclaimer (DISC-027) plus")
    L.append("> the `all`-baseline rules apply to a pure investor-awareness creative.")
    L.append("")
    return "\n".join(L), total


# --- HTML heatmap -----------------------------------------------------------
CSS = """
:root{--ground:#F1F3F6;--surface:#fff;--ink:#1B2330;--muted:#586171;--faint:#8A94A2;
--line:#E3E7ED;--line2:#D2D8E0;--accent:#2E5A87;--heat:46,90,135}
@media (prefers-color-scheme:dark){:root{--ground:#11151B;--surface:#1A1F28;--ink:#E7ECF2;
--muted:#9CA7B4;--faint:#6E7A88;--line:#29313C;--line2:#3A4450;--accent:#7FB0DB;--heat:127,176,219}}
:root[data-theme="dark"]{--ground:#11151B;--surface:#1A1F28;--ink:#E7ECF2;--muted:#9CA7B4;
--faint:#6E7A88;--line:#29313C;--line2:#3A4450;--accent:#7FB0DB;--heat:127,176,219}
:root[data-theme="light"]{--ground:#F1F3F6;--surface:#fff;--ink:#1B2330;--muted:#586171;
--faint:#8A94A2;--line:#E3E7ED;--line2:#D2D8E0;--accent:#2E5A87;--heat:46,90,135}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif;line-height:1.5}
.wrap{max-width:900px;margin:0 auto;padding:32px 24px 72px}
.eyebrow{font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;letter-spacing:.14em;
font-size:11px;color:var(--accent);margin:0 0 10px}
h1{font-family:'Palatino Linotype',Palatino,Georgia,serif;font-weight:600;font-size:28px;margin:0;
letter-spacing:-.01em}
.lede{color:var(--muted);font-size:14.5px;margin:12px 0 26px;max-width:64ch}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
caption{text-align:left;font-family:ui-monospace,Consolas,monospace;text-transform:uppercase;
font-size:10.5px;letter-spacing:.08em;color:var(--faint);padding:0 0 9px}
th,td{border:1px solid var(--line);padding:9px 11px;text-align:center}
thead th{background:var(--surface);font-size:12px;color:var(--muted);font-weight:600}
tbody th{background:var(--surface);text-align:left;font-weight:600;font-size:13.5px;white-space:nowrap}
td .tot{font-weight:700;font-size:15px}
td .unc{display:block;font-size:10.5px;color:var(--muted);font-family:ui-monospace,Consolas,monospace}
tr.inactive th,tr.inactive td{opacity:.5}
.axes{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:28px 0 8px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card h2{font-family:'Palatino Linotype',Palatino,Georgia,serif;font-size:15px;margin:0 0 8px}
.card ul{margin:0;padding-left:16px}
.card li{font-size:12.5px;color:var(--ink);margin:2px 0}
.card li b{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;color:var(--accent);font-weight:600}
.note{font-size:12px;color:var(--muted);margin:16px 0 0}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);
font-family:ui-monospace,Consolas,monospace;font-size:11px;color:var(--faint)}
@media (max-width:640px){.axes{grid-template-columns:1fr}}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def build_html(rules):
    total = len(rules)
    # max for heat scaling
    vals = [cell(rules, areas, ct)[0] for _, areas in SCENARIOS for ct in ROW_CTYPES]
    mx = max(vals) or 1

    head_cells = "".join(f"<th>{esc(lbl)}</th>" for lbl, _ in SCENARIOS)
    rows_html = []
    for ct in ROW_CTYPES:
        cls = ' class="inactive"' if ct == "video" else ""
        tds = []
        for _, areas in SCENARIOS:
            tot, unc = cell(rules, areas, ct)
            a = 0.05 + 0.5 * (tot / mx)
            tds.append(
                f'<td style="background:rgba(var(--heat),{a:.2f})">'
                f'<span class="tot">{tot}</span><span class="unc">{unc} always-on</span></td>'
            )
        rows_html.append(f'<tr{cls}><th>{esc(CT_LABEL[ct])}</th>{"".join(tds)}</tr>')

    def axis_card(title, items):
        lis = "".join(f"<li><b>{esc(k)}</b> — {esc(d)}</li>" for k, d, _ in items)
        return f'<div class="card"><h2>{esc(title)}</h2><ul>{lis}</ul></div>'

    body = f"""<title>Marketing-material segmentation — coverage matrix</title>
<style>{CSS}</style>
<div class="wrap">
  <p class="eyebrow">SEBI ad-code checker · catalogue segmentation</p>
  <h1>Which rules apply to which marketing material</h1>
  <p class="lede">A creative is filtered to the corpus by two axes — business area and creative type.
  Each cell shows how many of the {total} rules are in scope for that segment; the smaller number is
  the always-on (unconditional) rules that run regardless of content.</p>

  <table>
    <caption>Rules in scope — total (always-on) per segment</caption>
    <thead><tr><th>Creative type</th>{head_cells}</tr></thead>
    <tbody>{"".join(rows_html)}</tbody>
  </table>

  <div class="axes">
    {axis_card("Business area — applies_to", [a for a in AREAS if a[2] in ("implicit","v1")])}
    {axis_card("Creative type — creative_type", CTYPES)}
  </div>
  <p class="note">Business-area tags are additive: an NFO creative is reviewed as
  <b>mf_scheme + nfo</b>. Video is encoded but inactive in v1. File format (DOCX / PDF / image /
  carousel) is a third axis that only selects the extraction path, not which rules apply.</p>

  <footer>Generated from corpus/rules/*.json by scripts/build_segments.py — regenerate after any corpus change.</footer>
</div>"""
    return body


def main():
    rules = load_rules()
    md, total = build_md(rules)
    OUT_MD.write_text(md, encoding="utf-8")
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(rules), encoding="utf-8")
    print(f"wrote {OUT_MD}  ({OUT_MD.stat().st_size} bytes)")
    print(f"wrote {OUT_HTML}  ({OUT_HTML.stat().st_size} bytes)  — {total} rules")


if __name__ == "__main__":
    main()
