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
    "Screens a mutual-fund creative against the SEBI ad code, AMFI guidelines and the internal "
    "checklist. Three separated layers: **scored rule checks**, **factsheet fact-check**, and an "
    "**advisory** read. It flags issues to resolve — it is not a compliance sign-off."
)

with st.sidebar:
    st.header("Check a creative")
    if model.available():
        st.success(f"Model: {model.model_id()}")
    else:
        st.warning("No API key — deterministic checks only. Feature detection is heuristic; "
                   "automated rules defer to needs-review; fact-check and advisory are empty.")
    uploads = st.file_uploader(
        "Upload creative (DOCX, PDF, image; multiple images = carousel)",
        type=UPLOAD_TYPES, accept_multiple_files=True,
    )
    areas = st.multiselect(
        "Business area(s)", options=list(AREA_LABELS),
        default=["mf_scheme"], format_func=lambda a: AREA_LABELS[a],
    )
    ctype = st.selectbox(
        "Creative type", options=sorted(ACTIVE_CREATIVE_TYPES),
        format_func=lambda c: CTYPE_LABELS.get(c, c),
    )
    run = st.button("Run compliance check", type="primary", use_container_width=True)

if not run:
    st.info("⬅ Upload a creative, pick the business area(s) and creative type, then run the check.")
    st.stop()

if not uploads:
    st.error("Please upload at least one file.")
    st.stop()
if not areas:
    st.error("Please select at least one business area.")
    st.stop()

path = _stage_uploads(uploads)
with st.spinner("Extracting and checking…"):
    try:
        verdict = build_verdict(path, areas, ctype)
    except Exception as exc:  # noqa: BLE001 — surface, never a blank page
        st.error(f"Could not process the creative: {type(exc).__name__}: {exc}")
        st.stop()

st.divider()
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
