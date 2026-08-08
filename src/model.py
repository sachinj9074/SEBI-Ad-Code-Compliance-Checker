"""Single Anthropic model client for all model calls (README §9).

Isolated here so the provider stays swappable. Reads ANTHROPIC_API_KEY (and an
optional ANTHROPIC_MODEL override) from the environment / .env. If no key is
set, `available()` is False and callers fall back to deterministic paths.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
try:  # load .env if python-dotenv is present; harmless if the file is absent
    from dotenv import load_dotenv

    # override=True so a project .env wins over any stale key in the shell env.
    load_dotenv(_ROOT / ".env", override=True)
except Exception:  # pragma: no cover
    pass

# Tiered on cost (README §9 — the intelligence is in the corpus, so model choice
# is a cost decision). JUDGMENT is the nuanced tier: rule judgment, advisory, and
# vision/legibility. FAST is the cheap classification tier: feature detection and
# claim extraction. Both overridable via env for a one-line swap.
JUDGMENT_MODEL = "claude-sonnet-5"   # ~40% cheaper than Opus 5, near-Opus quality
FAST_MODEL = "claude-haiku-4-5"      # ~80% cheaper; simple classification only

# Back-compat alias — model_id() is the judgment/default tier.
DEFAULT_MODEL = JUDGMENT_MODEL


def model_id() -> str:
    """The judgment/default model (rule judgment, advisory, vision)."""
    return os.environ.get("ANTHROPIC_MODEL", JUDGMENT_MODEL)


def fast_model_id() -> str:
    """The cheap classification model (feature detection, claim extraction)."""
    return os.environ.get("ANTHROPIC_FAST_MODEL", FAST_MODEL)


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported lazily so deterministic paths need no SDK

        _client = anthropic.Anthropic()
    return _client


def structured(system: str, user: str, schema: dict, max_tokens: int = 4096,
               model: str | None = None) -> dict:
    """Text-only structured call. See structured_content for image inputs."""
    return structured_content(system, [{"type": "text", "text": user}], schema, max_tokens, model)


def structured_content(system: str, content: list, schema: dict, max_tokens: int = 4096,
                       model: str | None = None) -> dict:
    """Call the model with an arbitrary user-content list (text and/or image
    blocks) and return JSON validated against `schema` (structured outputs).
    `model` overrides the default. Raises RuntimeError if no API key is set."""
    if not available():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set — copy .env.example to .env and add your key."
        )
    client = _get_client()
    resp = client.messages.create(
        model=model or model_id(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Model declined the request (stop_reason=refusal).")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)
