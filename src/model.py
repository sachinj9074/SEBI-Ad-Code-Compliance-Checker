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

# Default per the claude-api guidance; override on cost via ANTHROPIC_MODEL
# (feature detection / claim extraction are simple classification tasks).
DEFAULT_MODEL = "claude-opus-5"


def model_id() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported lazily so deterministic paths need no SDK

        _client = anthropic.Anthropic()
    return _client


def structured(system: str, user: str, schema: dict, max_tokens: int = 4096) -> dict:
    """Call the model and return JSON validated against `schema` (structured
    outputs). Raises RuntimeError if no API key is configured."""
    if not available():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set — copy .env.example to .env and add your key."
        )
    client = _get_client()
    resp = client.messages.create(
        model=model_id(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Model declined the request (stop_reason=refusal).")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)
