"""Generate the marketing-material segmentation map from the corpus.

Emits:
  - corpus/SEGMENTS.md      taxonomy (3 axes) + coverage table (markdown, versioned)
  - review/segments_matrix.html  a visual heatmap of the same table (for an artifact)

Taxonomy (2026-08): the user picks ONE business area (Scheme-related / IAP /
Others & Media), then a conditional multi-select of creative types (IAP takes
none). Scope logic is imported from src.corpus so this map can never drift from
the checker.

Run:  .venv\\Scripts\\python.exe scripts/build_segments.py
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.corpus import AREA_CTYPE_OPTIONS, filter_rules, load_rules  # noqa: E402

OUT_MD = ROOT / "corpus" / "SEGMENTS.md"
OUT_HTML = ROOT / "review" / "segments_matrix.html"

AREA_LABEL = {"scheme_related": "Scheme-related", "iap": "IAP", "others_media": "Others & Media"}
CT_LABEL = {"nfo": "NFO", "key_visual": "Key visual", "yield": "Yield / debt",
            "social_post": "Social media post", "article": "Article", "blog": "Blog",
            "anniversary": "Anniversary"}
AREA_DESC = {
    "scheme_related": "Creatives about a mutual-fund scheme (incl. NFOs and yield/debt creatives).",
    "iap": "Investor awareness / education initiatives. Takes no creative-type input.",
    "others_media": "Brand, media and long-form material: social posts, articles, blogs, anniversaries.",
}

# Every user-selectable segment: (area, [creative types]) — IAP has none.
SEGMENTS = [(a, [c] if c else [])
            for a, cts in AREA_CTYPE_OPTIONS.items()
            for c in (cts or [None])]


def cell(rules, area, cts):
    hits = filter_rules(rules, area, cts)
    uncond = sum(1 for r in hits if r["trigger"]["type"] == "unconditional")
    return len(hits), uncond


def build_md(rules):
    total = len(rules)
    L = []
    L.append("# Marketing-material segmentation")
    L.append("")
    L.append("How the checker breaks a piece of marketing material into segments, and which rules")
    L.append("light up for each. **Generated from `corpus/rules/*.json` by `scripts/build_segments.py`** —")
    L.append("regenerate after any corpus change. Scope logic is imported from `src/corpus.py`.")
    L.append("")
    L.append("A creative is classified on three axes. Two of them filter the rule corpus; the third")
    L.append("only chooses the extraction path.")
    L.append("")
    L.append("```mermaid")
    L.append("flowchart LR")
    L.append('    U["Upload"] --> A["Business area — single-select"]')
    L.append('    A --> C["Creative types — conditional multi-select"]')
    L.append('    U --> F["File format — auto-detected"]')
    L.append('    A --> FIL["Filter corpus"]')
    L.append('    C --> FIL')
    L.append('    F --> EXT["Extraction path: text / vision"]')
    L.append(f'    FIL --> R["In-scope rules (subset of {total} active)"]')
    L.append("```")
    L.append("")
    L.append("**Filter rule:** a rule is in scope when its `applies_to` contains `all` or the selected")
    L.append("area, **and** its `creative_type` contains `all` or intersects the selected types (an")
    L.append("empty selection — IAP — matches only `all`-tagged rules). Conditional rules then fire only")
    L.append("if their trigger feature is present in the content. The `all` tags are the mandatory")
    L.append("baseline and are never user-facing options.")
    L.append("")
    L.append("**Warn-only scheme net:** if a non-Scheme-related run detects a scheme name or")
    L.append("performance figures, the verdict carries a selection warning (scheme rules stayed off).")
    L.append("")

    L.append("## Axis 1 — Business area (`applies_to`, single-select)")
    L.append("")
    L.append("| Segment | Meaning | Rules (incl. `all` baseline) |")
    L.append("|---|---|---|")
    n_all = sum(1 for r in rules if "all" in r["applies_to"])
    for key in AREA_CTYPE_OPTIONS:
        n = sum(1 for r in rules if key in r["applies_to"] or "all" in r["applies_to"])
        L.append(f"| `{key}` | {AREA_DESC[key]} | {n} |")
    L.append(f"| `all` *(baseline)* | Mandatory rules that run for every area. | {n_all} |")
    L.append("")

    L.append("## Axis 2 — Creative type (`creative_type`, conditional multi-select)")
    L.append("")
    L.append("| Area | Creative types offered |")
    L.append("|---|---|")
    for a, cts in AREA_CTYPE_OPTIONS.items():
        offered = ", ".join(f"`{c}`" for c in cts) if cts else "*(none — IAP takes no creative-type input)*"
        L.append(f"| `{a}` | {offered} |")
    L.append("")
    L.append("`video` is encoded on rules but inactive in v1 (no video option is offered).")
    L.append("")

    L.append("## Axis 3 — File format (auto-detected)")
    L.append("")
    L.append("| Format | Handling |")
    L.append("|---|---|")
    L.append("| DOCX | Text extracted directly. Build-first format. |")
    L.append("| PDF (text layer) | Text extracted directly. |")
    L.append("| PDF (scanned / image) | No text layer — vision pipeline. |")
    L.append("| Image / banner | Vision pipeline (layout, legibility, prominent-person). |")
    L.append("| Carousel | Multi-image — each frame through the image pipeline, grouped per frame. |")
    L.append("")

    L.append("## Coverage — rules in scope per user-selectable segment")
    L.append("")
    L.append("Each row is one selectable segment. **Total in scope** with **always-on (unconditional)**")
    L.append("in parentheses; the remainder are conditional and fire only when their feature is detected.")
    L.append("Multi-selecting creative types unions their rule sets.")
    L.append("")
    L.append("| Business area | Creative type | Rules in scope |")
    L.append("|---|---|---|")
    for area, cts in SEGMENTS:
        tot, unc = cell(rules, area, cts)
        ct_lbl = CT_LABEL[cts[0]] if cts else "*(none)*"
        L.append(f"| {AREA_LABEL[area]} | {ct_lbl} | {tot} ({unc} always-on) |")
    L.append("")
    L.append("> IAP and Others & Media segments are lean because only the mandatory `all` baseline plus")
    L.append("> their own segment rules apply; scheme-specific rules stay off there (warn-only net).")
    L.append("")
    return "\n".join(L), total


# --- HTML heatmap -----------------------------------------------------------
CSS = """
:root{--ground:#F1F3F6;--surface:#fff;--ink:#1B2330;--muted:#586171;--faint:#8A94A2;
--line:#E3E7ED;--line2:#D2D8E0;--accent:#2E5A87;--heat:46,90,135}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#11151B;--surface:#1A1F28;
--ink:#E7ECF2;--muted:#9CA7B4;--faint:#6E7A88;--line:#29313C;--line2:#3A4450;--accent:#7FB0DB;--heat:127,176,219}}
:root[data-theme="dark"]{--ground:#11151B;--surface:#1A1F28;--ink:#E7ECF2;--muted:#9CA7B4;
--faint:#6E7A88;--line:#29313C;--line2:#3A4450;--accent:#7FB0DB;--heat:127,176,219}
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
.note{font-size:12px;color:var(--muted);margin:16px 0 0}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);
font-family:ui-monospace,Consolas,monospace;font-size:11px;color:var(--faint)}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def build_html(rules):
    total = len(rules)
    vals = [cell(rules, a, c)[0] for a, c in SEGMENTS]
    mx = max(vals) or 1
    rows_html = []
    for area, cts in SEGMENTS:
        tot, unc = cell(rules, area, cts)
        a = 0.05 + 0.5 * (tot / mx)
        ct_lbl = CT_LABEL[cts[0]] if cts else "(none — IAP)"
        rows_html.append(
            f'<tr><th>{esc(AREA_LABEL[area])}</th><td>{esc(ct_lbl)}</td>'
            f'<td style="background:rgba(var(--heat),{a:.2f})">'
            f'<span class="tot">{tot}</span><span class="unc">{unc} always-on</span></td></tr>'
        )
    body = f"""<title>Marketing-material segmentation — coverage</title>
<style>{CSS}</style>
<div class="wrap">
  <p class="eyebrow">SEBI ad-code checker · catalogue segmentation</p>
  <h1>Which rules apply to which marketing material</h1>
  <p class="lede">The user picks one business area, then the creative types it offers (IAP takes
  none). Each row is a selectable segment; the cell shows how many of the {total} active rules are
  in scope, with the always-on (unconditional) count beneath. Multi-selecting types unions the sets.</p>
  <table>
    <caption>Rules in scope per segment</caption>
    <thead><tr><th>Business area</th><th>Creative type</th><th>Rules in scope</th></tr></thead>
    <tbody>{"".join(rows_html)}</tbody>
  </table>
  <p class="note">The <b>all</b> tags on rules are the mandatory baseline (never a user option).
  Scheme-specific rules stay off outside Scheme-related; if scheme content is detected there, the
  verdict carries a warning. Video is encoded but inactive in v1. File format (DOCX / PDF / image /
  carousel) only selects the extraction path.</p>
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
    print(f"wrote {OUT_HTML}  ({OUT_HTML.stat().st_size} bytes)  — {total} active rules")


if __name__ == "__main__":
    main()
