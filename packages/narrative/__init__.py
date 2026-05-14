"""Forensa narrative package.

Public surface:
- ``NarrativeClient`` (abstract base) + ``MockNarrativeClient`` from client.py
- ``LiveNarrativeClient`` from live_client.py with 4-layer prompt-injection defence
- Error types: ``NarrativeClientError``, ``NarrativeInjectionDetectedError``,
  ``NarrativeStructuralViolationError``
"""

from packages.narrative.client import (
    MockNarrativeClient,
    NarrativeClient,
    NarrativeClientError,
    NarrativeResult,
)
from packages.narrative.live_client import (
    LiveNarrativeClient,
    NarrativeInjectionDetectedError,
    NarrativeStructuralViolationError,
)

__all__ = [
    "LiveNarrativeClient",
    "MockNarrativeClient",
    "NarrativeClient",
    "NarrativeClientError",
    "NarrativeInjectionDetectedError",
    "NarrativeResult",
    "NarrativeStructuralViolationError",
]
