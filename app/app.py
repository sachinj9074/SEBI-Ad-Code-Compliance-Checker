"""SEBI Ad-Code Compliance Checker — Streamlit UI (README §7).

Display layer only (README §9): it saves the upload, calls
`src.checker.build_verdict`, and hands the result to the per-layer renderers in
`app/render.py`. No compliance logic lives here. The three layers are rendered
in clearly separated, differently-styled sections and are never merged.

Run:  .venv\\Scripts\\python.exe -m streamlit run app/app.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))              # for `src`
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for the sibling `render`

from src import model  # noqa: E402
from src.checker import build_verdict  # noqa: E402
from src.corpus import ACTIVE_CREATIVE_TYPES  # noqa: E402
import render  # noqa: E402  (sibling module; not `from app import …` — the script itself is module 'app')

# ---- vocabularies (human labels over the internal tags) ---------------------
AREA_LABELS = {
    "all": "All materials",
    "mf_scheme": "Mutual-fund scheme",
    "nfo": "New Fund Offer (NFO)",
    "iap": "Investor Awareness Programme",
}
CTYPE_LABELS = {
    "general_kv": "General / key visual",
    "anniversary": "Anniversary creative",
    "yield": "Yield / debt creative",
    "article_blog": "Article / blog",
    "social_post": "Social post",
}
UPLOAD_TYPES = ["docx", "pdf", "txt", "png", "jpg", "jpeg", "webp"]

# Bundled generic samples so the tool is self-serve (no file needed to try it).
NO_SAMPLE = "— none —"
SAMPLES = {
    "Clean creative (compliant)": "sample_clean.txt",
    "Planted violations": "sample_with_violations.txt",
    "Wrong return figure": "sample_wrong_return.txt",
    "Banner image (illegible disclaimer)": "sample_banner.png",
}

st.set_page_config(page_title="SEBI Ad-Code Compliance Checker", page_icon="🛡️", layout="wide")


def _stage_uploads(files) -> str:
    """Write the upload(s) to a temp dir. One file -> its path; several -> the
    dir (extract() treats a directory as a carousel)."""
    tmp = Path(tempfile.mkdtemp(prefix="sebi_creative_"))
    saved = []
    for f in files:
        dest = tmp / f.name
        dest.write_bytes(f.getbuffer())
        saved.append(dest)
    return str(saved[0]) if len(saved) == 1 else str(tmp)


# ---- page -------------------------------------------------------------------
st.title("🛡️ SEBI Ad-Code Compliance Checker")
st.caption(
    "A first-pass compliance self-check for the people who make the creatives — marketing, product, design — "
    "to run **before** sending anything to the compliance team. It screens against the SEBI ad code, AMFI "
    "guidelines and the internal checklist in three separated layers (rule checks · factsheet fact-check · "
    "advisory) and tells you what to change. It flags issues to resolve — it is **not** a compliance sign-off."
)

with st.sidebar:
    st.header("Check a creative")
    st.caption("1 · Upload a creative (or pick a bundled sample)  •  2 · Choose the business area(s) and creative type  •  3 · Run. "
               "You'll get a plain-language verdict: what to fix, what a human should check, and factual mismatches.")
    if model.available():
        st.success(f"Model: {model.model_id()}")
    else:
        st.warning("No API key — deterministic checks only. Feature detection is heuristic; "
                   "automated rules defer to needs-review; fact-check and advisory are empty.")
    uploads = st.file_uploader(
        "Upload creative (DOCX, PDF, image; multiple images = carousel)",
        type=UPLOAD_TYPES, accept_multiple_files=True,
    )
    sample_choice = st.selectbox(
        "…or try a bundled sample", [NO_SAMPLE, *SAMPLES],
        help="Generic sample creatives written for this tool — no upload needed.",
    )
    areas = st.multiselect(
        "Business area(s)", options=list(AREA_LABELS),
        default=["mf_scheme"], format_func=lambda a: AREA_LABELS[a],
    )
    _ctype_opts = sorted(ACTIVE_CREATIVE_TYPES)
    ctype = st.selectbox(
        "Creative type", options=_ctype_opts,
        index=_ctype_opts.index("general_kv") if "general_kv" in _ctype_opts else 0,
        format_func=lambda c: CTYPE_LABELS.get(c, c),
    )
    run = st.button("Run compliance check", type="primary", use_container_width=True)

if not run:
    st.info("⬅ Upload a creative, pick the business area(s) and creative type, then run the check.")
    st.stop()

if not uploads and sample_choice == NO_SAMPLE:
    st.error("Please upload a file or pick a bundled sample.")
    st.stop()
if not areas:
    st.error("Please select at least one business area.")
    st.stop()

if uploads:
    path = _stage_uploads(uploads)
else:
    path = str(ROOT / "samples" / SAMPLES[sample_choice])
with st.spinner("Extracting and checking…"):
    try:
        verdict = build_verdict(path, areas, ctype)
    except Exception as exc:  # noqa: BLE001 — surface, never a blank page
        st.error(f"Could not process the creative: {type(exc).__name__}: {exc}")
        st.stop()

st.divider()
render.headline(verdict)
render.summary_strip(verdict)
render.features(verdict)
render.showback(verdict)
st.divider()
render.rule_layer(verdict)
st.divider()
render.fact_layer(verdict)
st.divider()
render.advisory_layer(verdict)

with st.expander("Full verdict JSON (for debugging / export)"):
    st.json(verdict)
