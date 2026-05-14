"""Gemini narrative client wrapper (CP7.1).

Abstract base + Mock + (deferred) Live implementation. The Live impl is wired
in Phase 8 demo polish via google-generativeai; tests use MockNarrativeClient.

The contract is intentionally minimal: generate_narrative(prompt, max_tokens)
returns a NarrativeResult with the produced text + the model id used + a
deterministic content_hash binding (so a regulator can verify the narrative
was produced from a specific prompt without trusting the LLM transcript).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.crypto.hash import sha256_hex


class NarrativeClientError(Exception):
    """Raised when the narrative client fails to produce output."""


@dataclass(frozen=True)
class NarrativeResult:
    """One generated narrative bound to its prompt.

    content_hash = sha256_hex(canonical_json({prompt, model_id, narrative_text}))
    so the (prompt - pairing is independently verifiable.
    """

    narrative_text: str
    model_id: str
    prompt_token_count: int
    completion_token_count: int
    content_hash: str
    generated_at: datetime


class NarrativeClient(ABC):
    """Abstract narrative client. Mock + Live implementations."""

    @abstractmethod
    async def generate_narrative(self, prompt: str, max_tokens: int = 1024) -> NarrativeResult:
        """Produce a narrative for the given prompt."""


class MockNarrativeClient(NarrativeClient):
    """Deterministic mock for tests and demo dry-runs.

    Produces a fixed-template narrative referencing the prompt. Token counts
    are estimated from len(prompt)/4 and len(narrative)/4 (rough Gemini ratio).
    """

    def __init__(self, model_id: str = "gemini-3-pro-mock", fail: bool = False) -> None:
        self._model_id = model_id
        self._fail = fail

    async def generate_narrative(self, prompt: str, max_tokens: int = 1024) -> NarrativeResult:
        if self._fail:
            raise NarrativeClientError("mock client configured to fail")
        if max_tokens <= 0:
            raise NarrativeClientError("max_tokens must be positive")

        # Deterministic template - depends on prompt content for content_hash uniqueness
        narrative_text = (
            "Evidence pack summary: this narrative is a deterministic mock"
            f" produced for a prompt of {len(prompt)} characters."
            " In production this would be a regulator-ready prose summary of the"
            " receipts, policy decisions, and chain integrity findings."
        )
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(narrative_text) // 4)
        bind = {
            "prompt": prompt,
            "model_id": self._model_id,
            "narrative_text": narrative_text,
        }
        return NarrativeResult(
            narrative_text=narrative_text,
            model_id=self._model_id,
            prompt_token_count=prompt_tokens,
            completion_token_count=completion_tokens,
            content_hash=sha256_hex(bind),
            generated_at=datetime.now(UTC),
        )
