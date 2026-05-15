"""Smoke tests for scripts/seed_demo_data.py (CP9.30).

The seed script is excluded from the 100% coverage gate (coverage.source is
limited to apps + packages in pyproject.toml). These tests are minimal
smoke checks that:

  1. The module imports cleanly (catches typos in function names against
     bundle_workflow, anchor, tsa, token modules).
  2. _resolve_hmac_secret honours FORENSA_DEMO_HMAC_SECRET when set.
  3. _resolve_hmac_secret falls back deterministically when the env var
     is unset (warns to stdout).
  4. _resolve_hmac_secret rejects too-short secrets.

The full end-to-end test that writes to a real PostgreSQL instance is
tracked as TRACKED-NEW-P10.X.seed-demo-data-pg-integration-test and lives
at tests/integration/test_seed_demo_data_pg.py (future CP).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from scripts import seed_demo_data


def test_module_imports_cleanly() -> None:
    """If function-name typos vs bundle_workflow/anchor/tsa land, this fails."""
    assert hasattr(seed_demo_data, "seed")
    assert hasattr(seed_demo_data, "_resolve_hmac_secret")
    assert callable(seed_demo_data._resolve_hmac_secret)


def test_resolve_hmac_secret_honours_env_var() -> None:
    """A valid hex-encoded 32-byte secret should be parsed and returned."""
    secret_hex = "00" * 32  # 32 bytes of zeros, hex-encoded
    with patch.dict(os.environ, {"FORENSA_DEMO_HMAC_SECRET": secret_hex}, clear=False):
        result = seed_demo_data._resolve_hmac_secret()
    assert len(result) == 32
    assert result == b"\x00" * 32


def test_resolve_hmac_secret_honours_long_env_var() -> None:
    """A 64-byte secret (longer than minimum) should be returned unchanged."""
    secret = b"\xab" * 64
    with patch.dict(os.environ, {"FORENSA_DEMO_HMAC_SECRET": secret.hex()}, clear=False):
        result = seed_demo_data._resolve_hmac_secret()
    assert result == secret


def test_resolve_hmac_secret_rejects_short_env_var() -> None:
    """A < 32-byte secret should be rejected with SystemExit."""
    secret_hex = "ff" * 16  # only 16 bytes
    with patch.dict(os.environ, {"FORENSA_DEMO_HMAC_SECRET": secret_hex}, clear=False):
        with pytest.raises(SystemExit, match=">= 32 bytes"):
            seed_demo_data._resolve_hmac_secret()


def test_resolve_hmac_secret_rejects_non_hex_env_var() -> None:
    """A non-hex secret should be rejected with SystemExit."""
    with patch.dict(os.environ, {"FORENSA_DEMO_HMAC_SECRET": "not-hex-at-all-zzz"}, clear=False):
        with pytest.raises(SystemExit, match="hex-encoded"):
            seed_demo_data._resolve_hmac_secret()


def test_resolve_hmac_secret_falls_back_when_env_unset(capsys) -> None:
    """When env var is unset, derive a deterministic secret from the slug."""
    # Clear the env var if it happens to be set in the test environment.
    env_without_secret = {k: v for k, v in os.environ.items() if k != "FORENSA_DEMO_HMAC_SECRET"}
    with patch.dict(os.environ, env_without_secret, clear=True):
        result1 = seed_demo_data._resolve_hmac_secret()
        result2 = seed_demo_data._resolve_hmac_secret()
    # Deterministic: same output across calls.
    assert result1 == result2
    assert len(result1) == 32
    # Warning printed to stdout (NOT for production).
    captured = capsys.readouterr()
    assert "WARN" in captured.out
    assert "Do NOT use in production" in captured.out


def test_constants_are_stable() -> None:
    """Demo constants should match what tools/demo.sh expects."""
    assert seed_demo_data.DEMO_TENANT_SLUG == "forensa-demo"
    assert seed_demo_data.DEMO_AGENT_SLUG == "demo-agent"
    # Anchored day comes first in the chain; recent day comes second.
    assert seed_demo_data.DAY_ANCHORED < seed_demo_data.DAY_RECENT
    # Bundle content allows tool_call (which the seeded events use).
    rules = seed_demo_data.BUNDLE_CONTENT["rules"]
    tool_call_rules = [r for r in rules if r["kind"] == "tool_call"]
    assert tool_call_rules and tool_call_rules[0]["decision"] == "allow"
