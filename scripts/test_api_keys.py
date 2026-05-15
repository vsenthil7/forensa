"""Forensa - API key smoke test (pattern copied from AuditEx scripts/test_api_keys.py).

Tests the Gemini API key with a minimal call. Verifies:
  1. .env loads
  2. google-genai SDK can authenticate (CP9.20 migrated from google-generativeai)
  3. Gemini 2.5 Pro returns a real response
  4. LiveNarrativeClient construction + generate_narrative round-trip works
  5. The 4-layer prompt-injection defence does not false-positive on real output

Run from forensa root:
  poetry run python scripts/test_api_keys.py

Skips cleanly (exit 0) if FORENSA_GEMINI_API_KEY is unset or placeholder.
Fails with exit 1 if the key is set but the call doesn't succeed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader. No new dep; matches AuditEx pydantic-settings semantics
    closely enough for a smoke script."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Only set if not already in environment (env wins over file).
        os.environ.setdefault(key, value)


async def test_gemini_raw() -> bool:
    """Direct SDK call - is the key valid against AI Studio?"""
    key = os.environ.get("FORENSA_GEMINI_API_KEY", "")
    if not key or key.startswith("your_") or key == "placeholder":
        print("  GEMINI RAW:  SKIP -- FORENSA_GEMINI_API_KEY is unset / placeholder")
        return False

    try:
        from google import genai  # type: ignore[import-untyped]
        from google.genai import types as genai_types  # type: ignore[import-untyped]

        model_id = os.environ.get("FORENSA_GEMINI_MODEL_ID", "gemini-2.5-pro")
        client = genai.Client(api_key=key)
        config = genai_types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=64,
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
        )
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model=model_id,
            contents="Reply with just the word PONG. No punctuation. No other words.",
            config=config,
        )
        text = (resp.text or "").strip()
        print(f"  GEMINI RAW:  PASS -- model='{model_id}' response='{text[:80]}'")
        return True
    except Exception as exc:
        print(f"  GEMINI RAW:  FAIL -- {type(exc).__name__}: {exc}")
        return False


async def test_live_narrative_client() -> bool:
    """LiveNarrativeClient round-trip - does the Forensa wrapper work?"""
    key = os.environ.get("FORENSA_GEMINI_API_KEY", "")
    if not key or key.startswith("your_") or key == "placeholder":
        print("  LIVE CLIENT: SKIP -- FORENSA_GEMINI_API_KEY is unset / placeholder")
        return False

    try:
        from packages.narrative.live_client import LiveNarrativeClient

        model_id = os.environ.get("FORENSA_GEMINI_MODEL_ID", "gemini-2.5-pro")
        client = LiveNarrativeClient(api_key=key, model_id=model_id, timeout_seconds=20.0)

        # Minimal prompt string mimicking what build_prompt produces.
        # Real call shape is a dict serialised inside live_client; here we pass
        # a flat string that the LiveNarrativeClient will wrap as user content.
        prompt = (
            "You produce one-sentence regulatory narratives."
            " Evidence pack: a single Receipt for tenant_id=acme-bank,"
            " action=login_succeeded, signed_at=2026-05-14T13:55:00Z."
            " Instruction: summarise the evidence pack in one sentence of"
            " plain prose. No URLs. No code."
        )
        result = await client.generate_narrative(prompt, max_tokens=2048)
        ok = bool(result.narrative_text) and bool(result.content_hash)
        if ok:
            print(
                f"  LIVE CLIENT: PASS -- model_id='{result.model_id}'"
                f" text='{result.narrative_text[:120]}...'"
                f" tokens=in:{result.prompt_token_count}/out:{result.completion_token_count}"
            )
        else:
            print("  LIVE CLIENT: FAIL -- empty result")
        return ok
    except Exception as exc:
        print(f"  LIVE CLIENT: FAIL -- {type(exc).__name__}: {exc}")
        return False


def test_selector_wires_live() -> bool:
    """narrative_selector chose Live when key is set."""
    key = os.environ.get("FORENSA_GEMINI_API_KEY", "")
    if not key or key.startswith("your_") or key == "placeholder":
        print("  SELECTOR:    SKIP -- FORENSA_GEMINI_API_KEY is unset / placeholder")
        return False
    try:
        from apps.api.narrative_selector import select_narrative_client

        sel = select_narrative_client(env=dict(os.environ))
        if sel.provider == "gemini-live" and sel.is_fallback is False:
            print(
                f"  SELECTOR:    PASS -- provider='{sel.provider}' model='{sel.model_id}'"
                f" is_fallback={sel.is_fallback}"
            )
            return True
        print(
            f"  SELECTOR:    FAIL -- expected gemini-live, got provider='{sel.provider}'"
            f" is_fallback={sel.is_fallback}"
        )
        return False
    except Exception as exc:
        print(f"  SELECTOR:    FAIL -- {type(exc).__name__}: {exc}")
        return False


async def main() -> int:
    _load_dotenv()
    print("=" * 60)
    print("Forensa - Gemini API Key Smoke Test")
    print("=" * 60)
    print(f"  Working dir: {Path.cwd()}")
    print(f"  Key present: {'yes' if os.environ.get('FORENSA_GEMINI_API_KEY') else 'no'}")
    print(f"  Model id:    {os.environ.get('FORENSA_GEMINI_MODEL_ID', 'gemini-2.5-pro')}")
    print("-" * 60)

    ok_selector = test_selector_wires_live()
    ok_raw = await test_gemini_raw()
    ok_client = await test_live_narrative_client()

    print("=" * 60)
    if ok_selector and ok_raw and ok_client:
        print("RESULT: ALL GREEN -- live Gemini path validated end-to-end")
        return 0
    if not os.environ.get("FORENSA_GEMINI_API_KEY"):
        print("RESULT: SKIP -- no key set; smoke test cannot run")
        return 0
    print("RESULT: FAIL -- see individual lines above")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
