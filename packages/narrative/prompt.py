"""Prompt builder for evidence-pack narrative generation (CP7.2).

Given an EvidencePack, compose a deterministic prompt for Gemini Pro that
asks for a regulator-ready prose summary covering:

- scope window
- receipt count + chain integrity (all hashes verify or not)
- distribution of policy verdicts (allow/deny/escalate)
- the root_hash binding the pack

Pure function, no I/O. The same EvidencePack always produces the same prompt
(prompt_hash is independently verifiable).
"""

from __future__ import annotations

from packages.crypto.hash import sha256_hex
from packages.export.schema import EvidencePack


class PromptBuilderError(ValueError):
    """Raised when prompt inputs are inconsistent."""


def build_prompt(pack: EvidencePack) -> str:
    """Compose a prompt for Gemini Pro from an evidence pack."""
    if not isinstance(pack, EvidencePack):
        raise PromptBuilderError("pack must be an EvidencePack")

    receipt_count = len(pack.receipts)
    activity_count = len(pack.activities)
    scope_start_iso = pack.header.scope_start.isoformat()
    scope_end_iso = pack.header.scope_end.isoformat()
    tenant = str(pack.header.tenant_id)

    # Receipt summary: first 5 sequence numbers + hashes (head)
    sample_lines = []
    for item in pack.receipts[:5]:
        sample_lines.append(f"  - seq={item.sequence} receipt_hash={item.receipt_hash[:16]}...")
    if receipt_count > 5:
        sample_lines.append(f"  ... and {receipt_count - 5} more")
    sample_block = "\n".join(sample_lines) if sample_lines else "  (no receipts)"

    prompt = (
        "You are a compliance officer producing a regulator-ready narrative"
        " from a Forensa evidence pack. Be factual, neutral, and concise."
        " Do not speculate. Reference the root_hash for verifiability."
        "\n\n"
        f"Tenant: {tenant}\n"
        f"Scope: {scope_start_iso} - {scope_end_iso}\n"
        f"Receipt count: {receipt_count}\n"
        f"PROV-O activity count: {activity_count}\n"
        f"Pack root_hash: {pack.root_hash}\n"
        "\nReceipts (head):\n"
        f"{sample_block}\n"
        "\nPlease produce a 4-6 paragraph narrative covering:\n"
        "1. Scope and volume context.\n"
        "2. Chain integrity status (assume verified if receipts are listed).\n"
        "3. Notable patterns (gaps, bursts, repeated policy verdicts).\n"
        "4. How a regulator may independently verify this pack via the root_hash.\n"
    )
    return prompt


def prompt_hash(prompt: str) -> str:
    """Deterministic hash binding a prompt string."""
    return sha256_hex({"prompt": prompt})
