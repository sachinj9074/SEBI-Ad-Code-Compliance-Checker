"""SEBI Ad-Code Compliance Checker, Streamlit UI (README §7).

Display layer only (README §9): it saves the upload, calls
`src.checker.build_verdict`, and hands the result to the per-layer renderers in
`app/render.py`. No compliance logic lives here. The three layers are rendered
in clearly separated, differently-styled sections and are never merged.

Hosting posture (see docs/DEPLOY.md):
  * DEMO_MODE on the public deploy makes bundled samples load from demo_cache/
    (pre-computed verdicts, zero API calls). A visitor clicking around costs $0.
  * Live uploads (which do call the model) are gated behind LIVE_PASSWORD and a
    per-session run cap, so only people you share the code with can spend the key.
  * Locally, with no DEMO_MODE / LIVE_PASSWORD set, everything runs live as usual.

Run:  .venv\\Scripts\\python.exe -m streamlit run app/app.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))              # for `src`
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for the sibling `render`

from src import model  # noqa: E402
from src.checker import build_verdict  # noqa: E402
from src.corpus import AREAS, AREA_CTYPE_OPTIONS  # noqa: E402
import render  # noqa: E402  (sibling module; not `from app import ...` because the script itself is module 'app')

DEMO_CACHE = ROOT / "demo_cache"


# ---- config plumbing (secrets on Streamlit Cloud, env locally) --------------
def _secret(name: str, default: str | None = None) -> str | None:
    """Read from st.secrets first (hosted), then the environment (local)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # no secrets.toml present locally, that's fine
        pass
    return os.environ.get(name, default)


def _truthy(v: str | None) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


# Bridge the hosted secret into the environment so src.model picks it up. This
# is the user's own key that they paste into the Streamlit dashboard; the code
# only wires it through, it is never entered or handled here.
_key = _secret("ANTHROPIC_API_KEY")
if _key and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = _key
for _k in ("ANTHROPIC_MODEL", "ANTHROPIC_FAST_MODEL"):
    _v = _secret(_k)
    if _v:
        os.environ[_k] = _v

DEMO_MODE = _truthy(_secret("DEMO_MODE", "false"))
LIVE_PASSWORD = _secret("LIVE_PASSWORD", "") or ""
MAX_LIVE_RUNS = int(_secret("MAX_LIVE_RUNS", "15") or "15")

# ---- vocabularies (human labels over the internal tags) ---------------------
# The 'all' tag is the mandatory baseline on rules and is never a user option.
AREA_LABELS = {
    "scheme_related": "Scheme-related",
    "iap": "Investor Awareness Programme (IAP)",
    "others_media": "Others & Media",
}
CTYPE_LABELS = {
    "nfo": "NFO",
    "key_visual": "Key visual",
    "yield": "Yield / debt",
    "social_post": "Social media post",
    "article": "Article",
    "blog": "Blog",
    "anniversary": "Anniversary",
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


def _cache_path(sample_filename: str) -> Path:
    return DEMO_CACHE / f"{Path(sample_filename).stem}.json"


def _live_allowed() -> bool:
    """Whether live model calls (real uploads) are permitted right now."""
    if not DEMO_MODE:
        return True                                   # local / full mode
    if not LIVE_PASSWORD:
        return False                                  # demo with no code set: cached-only
    return bool(st.session_state.get("live_ok", False))


# ---- page -------------------------------------------------------------------
st.title("🛡️ SEBI Ad-Code Compliance Checker")
st.caption(
    "A first-pass compliance self-check for the people who make the creatives (marketing, product, design) "
    "to run **before** sending anything to the compliance team. It screens against the SEBI ad code, AMFI "
    "guidelines and the internal checklist in three separated layers (rule checks · factsheet fact-check · "
    "advisory) and tells you what to change. It flags issues to resolve; it is **not** a compliance sign-off."
)

with st.sidebar:
    st.header("Check a creative")

    # In the hosted demo, tell visitors how to use it cost-free and how to go live.
    if DEMO_MODE:
        st.info(
            "**Demo mode.** Pick a bundled sample below to see full, real results instantly "
            "(pre-computed, no API calls). To run your own upload live, enter the access code."
        )
        if LIVE_PASSWORD and not st.session_state.get("live_ok", False):
            with st.form("live_unlock", clear_on_submit=True):
                code = st.text_input("Access code for live uploads", type="password")
                if st.form_submit_button("Unlock live mode"):
                    if code == LIVE_PASSWORD:
                        st.session_state["live_ok"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect code.")
        elif LIVE_PASSWORD and st.session_state.get("live_ok", False):
            st.success("Live mode unlocked, you can upload your own creatives.")

    st.caption("1 · Upload a creative (or pick a bundled sample)  •  2 · Choose the business area(s) and creative type  •  3 · Run. "
               "You'll get a plain-language verdict: what to fix, what a human should check, and factual mismatches.")

    if not DEMO_MODE:
        if model.available():
            st.success(f"Model: {model.model_id()}")
        else:
            st.warning("No API key. Deterministic checks only: feature detection is heuristic; "
                       "automated rules defer to needs-review; fact-check and advisory are empty.")

    uploads = st.file_uploader(
        "Upload creative (DOCX, PDF, image; multiple images = carousel)",
        type=UPLOAD_TYPES, accept_multiple_files=True,
        help=("Live uploads are gated in the demo. Enter the access code above, or pick a bundled sample."
              if DEMO_MODE else None),
    )
    sample_choice = st.selectbox(
        "…or try a bundled sample", [NO_SAMPLE, *SAMPLES],
        help="Generic sample creatives written for this tool, no upload needed.",
    )
    area = st.radio(
        "Business area", options=AREAS,
        format_func=lambda a: AREA_LABELS[a],
    )
    _ctype_opts = AREA_CTYPE_OPTIONS[area]
    if _ctype_opts:
        ctypes = st.multiselect(
            "Creative type(s)", options=_ctype_opts,
            default=["key_visual"] if "key_visual" in _ctype_opts else [],
            format_func=lambda c: CTYPE_LABELS.get(c, c),
            help="Pick every type that applies; the matching rules are added together.",
        )
    else:
        ctypes = []
        st.caption("IAP creatives take no creative-type input; the IAP and mandatory rules run.")
    run = st.button("Run compliance check", type="primary", use_container_width=True)

# ---- run: compute (or load cached) and persist in session state --------------
# The verdict lives in st.session_state so the results survive every widget
# interaction (section switching, acknowledgements, the report gate). A new run
# replaces it and bumps run_id, which namespaces the per-run widget keys.
if run:
    if not uploads and sample_choice == NO_SAMPLE:
        st.error("Please upload a file or pick a bundled sample.")
        st.stop()
    if area != "iap" and not ctypes:
        st.error("Please select at least one creative type.")
        st.stop()

    # Decide the source and whether this is a zero-cost cached run or a live one.
    use_cache = False
    cache_file: Path | None = None
    if uploads:
        path = _stage_uploads(uploads)
    else:
        sample_filename = SAMPLES[sample_choice]
        path = str(ROOT / "samples" / sample_filename)
        cache_file = _cache_path(sample_filename)
        if DEMO_MODE and cache_file.exists():
            use_cache = True

    # Gate live runs in the demo.
    if not use_cache and not _live_allowed():
        st.warning(
            "Live runs are gated in this demo to keep API cost controlled. "
            "Pick a **bundled sample** to see full results instantly, or enter the **access code** "
            "in the sidebar to run your own upload live."
        )
        st.stop()
    if not use_cache and DEMO_MODE and st.session_state.get("live_runs", 0) >= MAX_LIVE_RUNS:
        st.warning("You've reached the live-run limit for this session. Reload the page to reset, "
                   "or explore the bundled samples.")
        st.stop()

    if use_cache:
        verdict = json.loads(cache_file.read_text(encoding="utf-8"))
        from_cache = True
    else:
        with st.spinner("Extracting and checking…"):
            try:
                verdict = build_verdict(path, area, ctypes)
            except Exception as exc:  # noqa: BLE001 — surface, never a blank page
                st.error(f"Could not process the creative: {type(exc).__name__}: {exc}")
                st.stop()
        st.session_state["live_runs"] = st.session_state.get("live_runs", 0) + 1
        from_cache = False

    st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
    st.session_state["verdict"] = verdict
    st.session_state["verdict_from_cache"] = from_cache

# ---- results (rendered from session state on every rerun) --------------------
verdict = st.session_state.get("verdict")
if verdict is None:
    st.info("⬅ Upload a creative (or pick a bundled sample), choose the business area and "
            "creative type(s), then run the check.")
    st.stop()
run_id = st.session_state["run_id"]

st.divider()
if st.session_state.get("verdict_from_cache"):
    st.caption("Showing a pre-computed demo result for this bundled sample (no API call). "
               "It reflects the default business area and creative type.")
render.selection_warnings(verdict)
render.headline(verdict)
render.features(verdict)
render.showback(verdict)
st.divider()
render.results(verdict, run_id)
render.clearance(verdict, run_id)

with st.expander("Full verdict JSON (for debugging / export)"):
    st.json(verdict)
