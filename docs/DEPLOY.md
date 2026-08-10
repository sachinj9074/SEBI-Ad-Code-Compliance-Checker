# Deploying the hosted demo

Goal: a public URL a recruiter can click, where the app is fully usable at **zero
API cost**, plus a private "live" path you can hand to specific people.

How it works:
- **Public visitors** pick a bundled sample and see a real, full verdict loaded
  from `demo_cache/` (pre-computed). No model call happens, so it costs nothing.
- **Live uploads** (which do call the model) are hidden behind an access code and
  a per-session run cap. Only people you give the code to can spend your key.

You need a GitHub account (the repo) and an Anthropic account (the key). The steps
that touch your key or your accounts are done by **you** in those dashboards; this
project never stores the key.

## 1. Pre-generate the demo cache (already done, redo after pipeline changes)

```bash
.venv\Scripts\python.exe scripts\build_demo_cache.py
```

This writes `demo_cache/*.json` for the four bundled samples. Commit those files.
Rerun it whenever the corpus, prompts, or samples change, so the cached results
stay in sync.

## 2. Set a spend cap on your Anthropic key (the real backstop)

In the **Anthropic Console -> Billing / Limits**, set a monthly spend limit on the
key. Even if the live path were abused, this bounds the worst case. Do this first.

## 3. Push and make the repo public

The repo being public does not cost anything (only your hosted app calling your
key does). Flip visibility in **GitHub -> repo -> Settings -> General -> Danger
Zone -> Change visibility -> Public**.

## 4. Deploy on Streamlit Community Cloud (free)

1. Go to <https://share.streamlit.io> and sign in with GitHub. Authorize it to
   read the repo.
2. **Create app -> Deploy a public app from GitHub.**
3. Fill in:
   - Repository: `sachinj9074/SEBI-Ad-Code-Compliance-Checker`
   - Branch: `main`
   - Main file path: `app/app.py`
   - (Advanced) Python version: **3.12**
4. Deploy. It installs from `requirements.txt` automatically.

## 5. Add your secrets

In the app's **Settings -> Secrets**, paste the block below (values are yours;
`.streamlit/secrets.toml.example` is the template). Keep `LIVE_PASSWORD` private.

```toml
ANTHROPIC_API_KEY = "sk-ant-...your key..."
DEMO_MODE = "true"
LIVE_PASSWORD = "a-code-you-choose"
MAX_LIVE_RUNS = "15"
```

Save. The app restarts with these applied.

## 6. Verify

- Open the public URL. Pick a bundled sample and run it: you get a full verdict,
  and no API call is made (cost stays $0).
- Try an upload without the code: it is blocked with a message.
- Enter the access code in the sidebar, then upload: it runs live.

## 7. Share

Give recruiters the URL for the cost-free sample walkthrough. Hand the access code
only to people you want to try their own creatives live. Rotate the code (edit the
secret) if it ever leaks.

## Notes

- To run the public site as **cached-only** (no live path at all), just leave
  `LIVE_PASSWORD` out of the secrets.
- To run **everything live** (e.g. a private internal deploy), set
  `DEMO_MODE = "false"`.
- Locally, none of this applies: with no secrets set, the app runs live against
  your `.env` key as before.
