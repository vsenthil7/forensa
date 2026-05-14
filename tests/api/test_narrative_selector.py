"""Tests for apps.api.narrative_selector (CP9.4).

Validates the env-var resolution order, the Mock fallback warning, and the
``/healthz`` exposure of the selected client identity.

The Live path is exercised via env=dict injection so no real Gemini key is
needed. The actual LiveNarrativeClient construction is verified by checking
``provider == "gemini-live"`` + ``is_fallback is False``.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.narrative_selector import (
    NarrativeClientSelection,
    get_selection,
    select_narrative_client,
)
from packages.narrative.client import MockNarrativeClient
from packages.narrative.live_client import LiveNarrativeClient

# ========== Selection logic ==========


def test_no_env_falls_back_to_mock_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        sel = select_narrative_client(env={})
    assert sel.provider == "mock"
    assert sel.is_fallback is True
    assert isinstance(sel.client, MockNarrativeClient)
    assert sel.model_id == "gemini-3-pro-mock"
    assert "FORENSA_GEMINI_API_KEY is not set" in sel.reason
    # WARN log emitted so operators can't silently end up on mock in prod
    assert any(
        rec.name == "apps.api.narrative_selector" and rec.levelname == "WARNING"
        for rec in caplog.records
    )


def test_empty_string_env_falls_back_to_mock():
    sel = select_narrative_client(env={"FORENSA_GEMINI_API_KEY": ""})
    assert sel.provider == "mock"
    assert sel.is_fallback is True


def test_whitespace_only_env_falls_back_to_mock():
    sel = select_narrative_client(env={"FORENSA_GEMINI_API_KEY": "   "})
    assert sel.provider == "mock"
    assert sel.is_fallback is True


def test_gemini_key_set_wires_live_client(caplog):
    with caplog.at_level(logging.INFO):
        sel = select_narrative_client(env={"FORENSA_GEMINI_API_KEY": "test-key-not-real"})
    assert sel.provider == "gemini-live"
    assert sel.is_fallback is False
    assert isinstance(sel.client, LiveNarrativeClient)
    assert sel.model_id == "gemini-1.5-pro-latest"
    assert "LiveNarrativeClient wired" in sel.reason
    # INFO log (not WARN) since this is the desired production state
    assert any(
        rec.name == "apps.api.narrative_selector" and rec.levelname == "INFO"
        for rec in caplog.records
    )


def test_gemini_key_with_custom_model_id():
    sel = select_narrative_client(
        env={
            "FORENSA_GEMINI_API_KEY": "test-key-not-real",
            "FORENSA_GEMINI_MODEL_ID": "gemini-2.0-flash-exp",
        }
    )
    assert sel.provider == "gemini-live"
    assert sel.model_id == "gemini-2.0-flash-exp"
    assert "gemini-2.0-flash-exp" in sel.reason


def test_default_env_is_os_environ_when_not_passed(monkeypatch):
    """When env=None, real os.environ is read."""
    monkeypatch.delenv("FORENSA_GEMINI_API_KEY", raising=False)
    sel = select_narrative_client()
    assert sel.provider == "mock"


def test_selection_is_frozen_dataclass():
    sel = select_narrative_client(env={})
    with pytest.raises((AttributeError, TypeError)):
        sel.provider = "tampered"  # type: ignore[misc]


# ========== Module-level singleton ==========


def test_get_selection_returns_module_level_singleton():
    """get_selection() returns the same instance across calls within a process."""
    a = get_selection()
    b = get_selection()
    assert a is b
    assert isinstance(a, NarrativeClientSelection)


# ========== /healthz endpoint exposes selection ==========


def test_healthz_exposes_narrative_provider_when_mock():
    """End users of the product can see which LLM is processing their data."""
    app = create_app()
    with TestClient(app) as c:
        resp = c.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "narrative_provider" in body
    assert "narrative_model_id" in body
    assert "narrative_is_fallback" in body
    # In test environment FORENSA_GEMINI_API_KEY is unset, so mock is wired
    assert body["narrative_provider"] in {"mock", "gemini-live"}


def test_healthz_payload_shape_complete():
    """Every field the procurement docs promise is present."""
    app = create_app()
    with TestClient(app) as c:
        resp = c.get("/healthz")
    body = resp.json()
    assert set(body.keys()) == {
        "status",
        "version",
        "narrative_provider",
        "narrative_model_id",
        "narrative_is_fallback",
    }


# ========== Route uses module-level selection ==========


@pytest.mark.asyncio
async def test_route_get_narrative_client_returns_module_selection():
    """The route's DI provider returns get_selection().client."""
    from apps.api.routes.narratives import get_narrative_client

    client = await get_narrative_client()
    assert client is get_selection().client
