"""Narrative client selector + startup announcement (CP9.4).

Resolves which `NarrativeClient` implementation to wire into the FastAPI app
based on environment variables. Live is the DEFAULT when a key is present;
Mock is the explicit fallback when no provider is configured.

The selection is made ONCE at app startup (module load time of the route module)
so every request inside the app instance uses the same client and the operator
sees one startup log line declaring the choice.

Future ordering when more providers land (per NEW-P13.X.vertex-migration and
NEW-P13.X.multi-provider-narrative in the review backlog):

1. ``FORENSA_VERTEX_PROJECT_ID`` -> VertexNarrativeClient (Phase 13)
2. ``FORENSA_ANTHROPIC_API_KEY`` -> ClaudeNarrativeClient (Phase 13)
3. ``FORENSA_OPENAI_API_KEY`` -> OpenAINarrativeClient (Phase 13)
4. ``FORENSA_GEMINI_API_KEY`` -> LiveNarrativeClient (CP9.1 - HERE TODAY)
5. (no env var set) -> MockNarrativeClient with explicit WARN log

Today only step 4 + step 5 are implemented; the others are noted so the
selection function has the right shape from day one.

Product visibility
------------------

The selected client's identifier is exposed via the ``/healthz`` endpoint so
end users of the Forensa product (auditors, compliance officers) know which
LLM is processing their evidence at any time. This is a procurement-visible
artefact, not just an operator one.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from packages.narrative.client import MockNarrativeClient, NarrativeClient
from packages.narrative.live_client import LiveNarrativeClient

logger = logging.getLogger(__name__)

_GEMINI_API_KEY_ENV = "FORENSA_GEMINI_API_KEY"
_GEMINI_MODEL_ID_ENV = "FORENSA_GEMINI_MODEL_ID"


@dataclass(frozen=True)
class NarrativeClientSelection:
    """Outcome of selecting a narrative client at startup.

    Fields are exposed via ``/healthz`` so the product user can see which
    LLM is wired without grepping logs.
    """

    client: NarrativeClient
    provider: str  # "gemini-live" | "mock"
    model_id: str
    is_fallback: bool  # True when no env var was set and Mock was chosen
    reason: str  # Short human-readable explanation


def select_narrative_client(env: dict[str, str] | None = None) -> NarrativeClientSelection:
    """Pick the narrative client implementation based on env vars.

    Live is the DEFAULT when a provider env var is present. Mock is the
    fallback when nothing is configured, AND the fallback emits a WARN log
    so operators never silently end up on mock in production.

    Args:
        env: Environment mapping. Defaults to ``os.environ`` for production;
            tests pass an explicit dict to avoid global state.

    Returns:
        ``NarrativeClientSelection`` with the wired client + provider metadata.
    """
    env_map = env if env is not None else dict(os.environ)
    gemini_key = env_map.get(_GEMINI_API_KEY_ENV, "").strip()
    gemini_model = env_map.get(_GEMINI_MODEL_ID_ENV, "").strip() or "gemini-1.5-pro-latest"

    client: NarrativeClient
    if gemini_key:
        client = LiveNarrativeClient(api_key=gemini_key, model_id=gemini_model)
        selection = NarrativeClientSelection(
            client=client,
            provider="gemini-live",
            model_id=gemini_model,
            is_fallback=False,
            reason=(
                f"{_GEMINI_API_KEY_ENV} is set;"
                f" LiveNarrativeClient wired with model {gemini_model}"
            ),
        )
        logger.info(
            "forensa.narrative.client_selected",
            extra={
                "provider": selection.provider,
                "model_id": selection.model_id,
                "is_fallback": selection.is_fallback,
            },
        )
        return selection

    # No provider configured -> Mock as explicit fallback. WARN-level: operators
    # should never silently end up on mock in production.
    client = MockNarrativeClient()
    selection = NarrativeClientSelection(
        client=client,
        provider="mock",
        model_id="gemini-3-pro-mock",
        is_fallback=True,
        reason=(
            f"{_GEMINI_API_KEY_ENV} is not set; MockNarrativeClient wired as fallback."
            " Set FORENSA_GEMINI_API_KEY in .env to enable live Gemini Pro narratives."
        ),
    )
    logger.warning(
        "forensa.narrative.fallback_to_mock",
        extra={
            "provider": selection.provider,
            "model_id": selection.model_id,
            "is_fallback": selection.is_fallback,
            "reason": selection.reason,
        },
    )
    return selection


# Module-level singleton: chosen once at process startup, reused for every
# request. Tests that need a fresh selection (or want to inject a fake env)
# call ``select_narrative_client(env=...)`` directly and override the
# FastAPI dependency.
_SELECTION: NarrativeClientSelection = select_narrative_client()


def get_selection() -> NarrativeClientSelection:
    """Return the module-level selection. Used by `/healthz` and the route DI."""
    return _SELECTION


__all__ = [
    "NarrativeClientSelection",
    "get_selection",
    "select_narrative_client",
]
