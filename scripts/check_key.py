"""Quick, free check that the configured API key + model work.

Uses count_tokens (no output tokens billed) to validate auth and model access.
Run:  .venv\\Scripts\\python.exe scripts/check_key.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import model  # noqa: E402  (import also loads .env with override=True)


def main() -> int:
    print(f"key present : {model.available()}")
    print(f"model       : {model.model_id()}")
    if not model.available():
        print("No API key found — add one to .env (ANTHROPIC_API_KEY=sk-ant-...).")
        return 1
    try:
        import anthropic

        client = anthropic.Anthropic()
        r = client.messages.count_tokens(
            model=model.model_id(),
            messages=[{"role": "user", "content": "ping"}],
        )
        print(f"result      : OK — auth valid, model reachable ({r.input_tokens} input tokens for 'ping').")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"result      : FAILED — {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
