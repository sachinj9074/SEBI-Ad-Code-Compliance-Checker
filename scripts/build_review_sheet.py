"""Generate a human-readable review sheet (HTML) from the rule corpus.

Reads corpus/rules/*.json and emits a single self-contained page for reviewing
every rule's trigger, severity, check_type, provenance, citation, and pass/fail
examples. Regenerate whenever the corpus changes.

Run:  .venv\\Scripts\\python.exe scripts/build_review_sheet.py [out.html]
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "corpus" / "rules"
DEFAULT_OUT = ROOT / "review" / "corpus_review.html"

ACTIVE_CREATIVE_TYPES = {"general_kv", "anniversary", "yield", "article_blog", "social_post"}
ALL6 = {"general_kv", "anniversary", "yield", "article_blog", "social_post", "video"}

CATEGORIES = {
    "01_prohibitions": "General prohibitions",
    "02_celebrity": "Celebrity / prominent person",
    "03_disclaimers": "Mandatory disclaimers",
    "04_performance": "Performance — Master Circular Ch. 14",
    "05_yield_aum_anniversary": "Yield · AUM · Anniversary",
    "06_video": "Video — encoded, inactive in v1",
    "07_amfi": "AMFI guidelines",
}

CAT_SOURCE = {
    "01_prohibitions": "Sixth Schedule (Advertisement Code)",
    "02_celebrity": "Sixth Schedule (e) + internal celebrity checklist",
    "03_disclaimers": "Disclaimer repository + product-labelling",
    "04_performance": "MF Master Circular 2026-03-20, Chapter 14",
    "05_yield_aum_anniversary": "MC Ch.14 + internal KV/yield/anniversary checklist",
    "06_video": "Sixth Schedule (j) + internal video checkpoints",
    "07_amfi": "AMFI Best Practices Circular 109/2023-24",
}

TOKENS = {
    "light": {
        "ground": "#F1F3F6", "surface": "#FFFFFF", "surface-2": "#F7F9FB",
        "ink": "#1B2330", "muted": "#586171", "faint": "#8A94A2",
        "line": "#E3E7ED", "line-2": "#D2D8E0",
        "accent": "#2E5A87", "accent-soft": "#E9EFF6",
        "sev-critical": "#C0392B", "sev-high": "#BE7A2C", "sev-medium": "#4C7399", "sev-low": "#7C8896",
        "auto": "#2F7D6B", "auto-bg": "#E4F1ED", "assist": "#6E52A3", "assist-bg": "#ECE6F5",
        "pass-bg": "#EBF4EE", "pass-bd": "#C3DBCB", "pass-ink": "#2C6B44",
        "fail-bg": "#F8ECEC", "fail-bd": "#E6C6C6", "fail-ink": "#9E3B33",
    },
    "dark": {
        "ground": "#11151B", "surface": "#1A1F28", "surface-2": "#20262F",
        "ink": "#E7ECF2", "muted": "#9CA7B4", "faint": "#6E7A88",
        "line": "#29313C", "line-2": "#3A4450",
        "accent": "#7FB0DB", "accent-soft": "#1E2B38",
        "sev-critical": "#E38177", "sev-high": "#DCA660", "sev-medium": "#78A7D6", "sev-low": "#95A2B0",
        "auto": "#5FBFA6", "auto-bg": "#16302A", "assist": "#B79BDD", "assist-bg": "#241C33",
        "pass-bg": "#16281D", "pass-bd": "#2C4A37", "pass-ink": "#8FCFA3",
        "fail-bg": "#2A1A1A", "fail-bd": "#4A2F2F", "fail-ink": "#E4A199",
    },
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def tokens_block(selector: str, theme: str) -> str:
    body = "; ".join(f"--{k}:{v}" for k, v in TOKENS[theme].items())
    return f"{selector}{{{body}}}"


def load_rules():
    cats = []
    for stem, name in CATEGORIES.items():
        f = RULES_DIR / f"{stem}.json"
        rules = json.loads(f.read_text(encoding="utf-8"))
        cats.append((stem, name, rules))
    return cats


def chip(text, cls="") -> str:
    return f'<span class="chip {cls}">{esc(text)}</span>'


def rule_card(rule: dict) -> str:
    sev = rule["severity"]
    active = bool(set(rule["creative_type"]) & ACTIVE_CREATIVE_TYPES)
    trig = rule["trigger"]
    trig_txt = "unconditional" if trig["type"] == "unconditional" else f'if · {trig.get("feature","")}'
    ct_val = rule["check_type"]
    ct_txt = "automated" if ct_val == "automated" else "assisted · needs review"

    badges = [
        f'<span class="chip sev sev-{sev}">{esc(sev)}</span>',
        f'<span class="chip ct ct-{ct_val}">{esc(ct_txt)}</span>',
        f'<span class="chip trig">{esc(trig_txt)}</span>',
    ]
    for area in rule["applies_to"]:
        badges.append(f'<span class="chip area">{esc(area)}</span>')
    # only show creative_type when it is specific (not the full active-or-all set)
    ctypes = set(rule["creative_type"])
    if ctypes != ALL6:
        badges.append('<span class="chip type">' + esc(" · ".join(rule["creative_type"])) + "</span>")
    for p in rule["provenance"]:
        badges.append(f'<span class="chip prov prov-{p}">{esc(p)}</span>')
    if not active:
        badges.append('<span class="chip inactive">inactive v1</span>')

    cite = esc(rule["source_clause"])
    if rule.get("source_date"):
        cite += f' <span class="cite-date">· {esc(rule["source_date"])}</span>'

    mandated = ""
    if "mandated_text" in rule:
        mt = rule["mandated_text"]
        meta = []
        if mt.get("language"):
            meta.append(esc(mt["language"]))
        if mt.get("match_threshold") is not None:
            meta.append(f'≥{esc(mt["match_threshold"])}')
        meta_txt = f' <span class="mt-meta">{" · ".join(meta)}</span>' if meta else ""
        mandated = (
            f'<div class="mandated"><span class="mt-lbl">mandated text</span>{meta_txt}'
            f'<span class="mt-body">“{esc(mt["text"])}”</span></div>'
        )

    ex = rule["examples"]

    def ex_block(kind, data):
        note = f'<span class="ex-note">{esc(data["note"])}</span>' if data.get("note") else ""
        return (
            f'<div class="ex ex-{kind}"><span class="ex-lbl">{kind}</span>'
            f'<span class="ex-body">{esc(data["content"])}</span>{note}</div>'
        )

    inactive_cls = "" if active else " is-inactive"
    return f"""<article class="rule sev-border-{sev}{inactive_cls}">
  <div class="rule-top">
    <span class="rid">{esc(rule["rule_id"])}</span>
    <h3 class="rtitle">{esc(rule.get("title", rule["rule_id"]))}</h3>
  </div>
  <div class="badges">{"".join(badges)}</div>
  <p class="rdesc">{esc(rule["description"])}</p>
  <p class="cite"><span class="cite-lbl">cites</span> {cite}</p>
  {mandated}
  <div class="examples">{ex_block("pass", ex["pass"])}{ex_block("fail", ex["fail"])}</div>
</article>"""


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    cats = load_rules()

    total = sum(len(r) for _, _, r in cats)
    active = sum(1 for _, _, rs in cats for r in rs if set(r["creative_type"]) & ACTIVE_CREATIVE_TYPES)
    auto = sum(1 for _, _, rs in cats for r in rs if r["check_type"] == "automated")
    assist = total - auto
    sev_counts = {s: 0 for s in ("critical", "high", "medium", "low")}
    for _, _, rs in cats:
        for r in rs:
            sev_counts[r["severity"]] += 1

    sections = []
    for stem, name, rules in cats:
        cards = "\n".join(rule_card(r) for r in rules)
        sections.append(
            f'<section class="cat" id="{esc(stem)}">'
            f'<div class="cat-head"><h2>{esc(name)}</h2>'
            f'<span class="cat-src">{esc(CAT_SOURCE[stem])}</span>'
            f'<span class="cat-count">{len(rules)}</span></div>'
            f'<div class="cards">{cards}</div></section>'
        )

    css = f"""
{tokens_block(":root", "light")}
@media (prefers-color-scheme: dark){{{tokens_block(":root", "dark")}}}
{tokens_block(':root[data-theme="dark"]', "dark")}
{tokens_block(':root[data-theme="light"]', "light")}

*{{box-sizing:border-box}}
body{{margin:0;background:var(--ground);color:var(--ink);
  font-family:var(--f-body);line-height:1.55;-webkit-font-smoothing:antialiased}}
:root{{
  --f-display:'Palatino Linotype',Palatino,'Iowan Old Style','Book Antiqua',Georgia,serif;
  --f-body:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,system-ui,sans-serif;
  --f-mono:ui-monospace,'Cascadia Code','SF Mono',Menlo,Consolas,monospace;
}}
.wrap{{max-width:1080px;margin:0 auto;padding:32px 24px 80px}}
a{{color:var(--accent)}}
:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}

.masthead{{display:flex;flex-wrap:wrap;gap:28px;justify-content:space-between;
  align-items:flex-end;padding-bottom:22px;border-bottom:2px solid var(--line-2)}}
.mast-titles{{max-width:60ch}}
.eyebrow{{font-family:var(--f-mono);text-transform:uppercase;letter-spacing:.14em;
  font-size:11px;color:var(--accent);margin:0 0 10px}}
h1{{font-family:var(--f-display);font-weight:600;font-size:31px;line-height:1.12;
  margin:0;letter-spacing:-.01em;text-wrap:balance}}
.lede{{color:var(--muted);font-size:14.5px;margin:12px 0 0}}
.stats{{display:flex;gap:10px;flex-wrap:wrap}}
.stat{{background:var(--surface);border:1px solid var(--line);border-radius:9px;
  padding:10px 14px;min-width:74px;text-align:center}}
.stat .num{{display:block;font-family:var(--f-display);font-size:22px;font-weight:600;
  font-variant-numeric:tabular-nums}}
.stat .lbl{{display:block;font-family:var(--f-mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--faint);margin-top:3px}}

.legend{{display:flex;flex-wrap:wrap;gap:18px 26px;padding:16px 0 4px;margin-top:22px;
  border-bottom:1px solid var(--line);font-size:12.5px;color:var(--muted)}}
.legend .grp{{display:flex;align-items:center;gap:10px}}
.legend .grp b{{font-family:var(--f-mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--faint);font-weight:600}}
.sw{{display:inline-flex;align-items:center;gap:5px}}
.sw i{{width:11px;height:11px;border-radius:3px;display:inline-block}}

.cat{{margin-top:38px}}
.cat-head{{display:flex;align-items:baseline;gap:12px;
  padding-bottom:9px;border-bottom:1px solid var(--line-2);margin-bottom:16px}}
.cat-head h2{{font-family:var(--f-display);font-size:19px;font-weight:600;margin:0}}
.cat-src{{font-size:12px;color:var(--faint);flex:1}}
.cat-count{{font-family:var(--f-mono);font-size:12px;color:var(--muted);
  background:var(--surface-2);border:1px solid var(--line);border-radius:20px;padding:2px 10px}}
.cards{{display:flex;flex-direction:column;gap:12px}}

.rule{{background:var(--surface);border:1px solid var(--line);border-left-width:4px;
  border-radius:10px;padding:15px 17px}}
.sev-border-critical{{border-left-color:var(--sev-critical)}}
.sev-border-high{{border-left-color:var(--sev-high)}}
.sev-border-medium{{border-left-color:var(--sev-medium)}}
.sev-border-low{{border-left-color:var(--sev-low)}}
.rule.is-inactive{{opacity:.62}}
.rule-top{{display:flex;align-items:baseline;gap:11px;flex-wrap:wrap}}
.rid{{font-family:var(--f-mono);font-size:12px;font-weight:600;color:var(--accent);
  background:var(--accent-soft);border-radius:5px;padding:2px 7px;letter-spacing:.02em}}
.rtitle{{font-size:15.5px;font-weight:650;margin:0}}
.badges{{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0}}
.chip{{font-family:var(--f-mono);font-size:10.5px;letter-spacing:.02em;
  padding:2px 8px;border-radius:20px;border:1px solid var(--line-2);color:var(--muted);
  white-space:nowrap}}
.chip.sev{{color:#fff;border:0;font-weight:600;text-transform:uppercase;letter-spacing:.05em}}
.sev-critical{{background:var(--sev-critical)}} .sev-high{{background:var(--sev-high)}}
.sev-medium{{background:var(--sev-medium)}} .sev-low{{background:var(--sev-low)}}
.chip.ct{{font-weight:600}}
.ct-automated{{color:var(--auto);background:var(--auto-bg);border-color:transparent}}
.ct-assisted{{color:var(--assist);background:var(--assist-bg);border-color:transparent}}
.chip.trig{{color:var(--ink);background:var(--surface-2)}}
.chip.area,.chip.type{{background:transparent}}
.chip.prov{{text-transform:uppercase;letter-spacing:.05em;font-size:9.5px}}
.chip.inactive{{color:var(--faint);border-style:dashed;text-transform:uppercase;letter-spacing:.06em}}
.rdesc{{font-size:14px;color:var(--ink);margin:12px 0 0}}
.cite{{font-size:12.5px;color:var(--muted);margin:9px 0 0;font-family:var(--f-mono);line-height:1.5}}
.cite-lbl{{text-transform:uppercase;font-size:9.5px;letter-spacing:.08em;color:var(--faint);
  margin-right:6px}}
.cite-date{{color:var(--faint)}}
.mandated{{margin:11px 0 0;padding:9px 12px;background:var(--surface-2);
  border:1px solid var(--line);border-radius:8px}}
.mt-lbl{{font-family:var(--f-mono);text-transform:uppercase;font-size:9.5px;letter-spacing:.08em;
  color:var(--accent)}}
.mt-meta{{font-family:var(--f-mono);font-size:10px;color:var(--faint)}}
.mt-body{{display:block;margin-top:5px;font-size:13px;color:var(--ink)}}
.examples{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px}}
.ex{{border-radius:8px;padding:9px 11px;font-size:12.5px;border:1px solid transparent}}
.ex-pass{{background:var(--pass-bg);border-color:var(--pass-bd)}}
.ex-fail{{background:var(--fail-bg);border-color:var(--fail-bd)}}
.ex-lbl{{font-family:var(--f-mono);font-size:9.5px;font-weight:700;text-transform:uppercase;
  letter-spacing:.08em;display:block;margin-bottom:4px}}
.ex-pass .ex-lbl{{color:var(--pass-ink)}}
.ex-fail .ex-lbl{{color:var(--fail-ink)}}
.ex-body{{color:var(--ink)}}
.ex-note{{display:block;margin-top:5px;color:var(--muted);font-style:italic;font-size:11.5px}}
footer{{margin-top:46px;padding-top:18px;border-top:1px solid var(--line);
  font-family:var(--f-mono);font-size:11px;color:var(--faint)}}
@media (max-width:640px){{
  .examples{{grid-template-columns:1fr}}
  h1{{font-size:26px}}
  .masthead{{align-items:flex-start}}
}}
"""

    body = f"""<title>SEBI Ad-Code Rule Corpus — Review Sheet</title>
<style>{css}</style>
<div class="wrap">
  <header class="masthead">
    <div class="mast-titles">
      <p class="eyebrow">v1 corpus · review sheet</p>
      <h1>SEBI Advertisement-Code Rule Corpus</h1>
      <p class="lede">{total} rules screening mutual-fund creatives against the Sixth Schedule,
      Master Circular Chapter 14, and the internal checklist. Review each rule's trigger, severity,
      check type, and citation — and read its pass/fail examples — then flag anything to change
      before we build the checker on top.</p>
    </div>
    <div class="stats">
      <div class="stat"><span class="num">{total}</span><span class="lbl">rules</span></div>
      <div class="stat"><span class="num">{active}</span><span class="lbl">v1-active</span></div>
      <div class="stat"><span class="num">{auto}/{assist}</span><span class="lbl">auto/assist</span></div>
      <div class="stat"><span class="num">{active*2}</span><span class="lbl">seed cases</span></div>
    </div>
  </header>

  <div class="legend">
    <div class="grp"><b>severity</b>
      <span class="sw"><i style="background:var(--sev-critical)"></i>critical {sev_counts['critical']}</span>
      <span class="sw"><i style="background:var(--sev-high)"></i>high {sev_counts['high']}</span>
      <span class="sw"><i style="background:var(--sev-medium)"></i>medium {sev_counts['medium']}</span>
      <span class="sw"><i style="background:var(--sev-low)"></i>low {sev_counts['low']}</span>
    </div>
    <div class="grp"><b>check</b>
      <span class="sw"><i style="background:var(--auto)"></i>automated (machine-decidable)</span>
      <span class="sw"><i style="background:var(--assist)"></i>assisted → needs_review</span>
    </div>
    <div class="grp"><b>provenance</b> sebi · amfi · internal_policy</div>
  </div>

  {"".join(sections)}

  <footer>Generated from corpus/rules/*.json by scripts/build_review_sheet.py — regenerate after any rule change. Genericized per corpus/GENERICIZATION.md.</footer>
</div>"""

    out.write_text(body, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size} bytes)  — {total} rules, {active} active")
    return 0


if __name__ == "__main__":
    sys.exit(main())
