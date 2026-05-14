"""Tests for packages.narrative.client and packages.narrative.prompt (CP7.1, CP7.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack
from packages.ledger.receipt_builder import build_receipt
from packages.narrative.client import MockNarrativeClient, NarrativeClientError
from packages.narrative.prompt import PromptBuilderError, build_prompt, prompt_hash
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("abcd0000-0000-0000-0000-000000000123")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_pack(n: int):
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT_ID, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    for i in range(n):
        r = build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return build_evidence_pack(
        tenant_id=_TENANT_ID,
        generated_at=datetime.now(UTC),
        scope_start=base,
        scope_end=base + timedelta(hours=2),
        receipts_with_snapshots=pairs,
    )


# ========== CP7.2 prompt builder ==========


@pytest.mark.asyncio
async def test_build_prompt_includes_tenant_root_hash_and_counts():
    pack = await _make_pack(3)
    prompt = build_prompt(pack)
    assert str(_TENANT_ID) in prompt
    assert pack.root_hash in prompt
    assert "Receipt count: 3" in prompt
    assert "PROV-O activity count: 3" in prompt


@pytest.mark.asyncio
async def test_build_prompt_handles_empty_pack():
    pack = await _make_pack(0)
    prompt = build_prompt(pack)
    assert "Receipt count: 0" in prompt
    assert "(no receipts)" in prompt


@pytest.mark.asyncio
async def test_build_prompt_truncates_after_5_receipts():
    pack = await _make_pack(8)
    prompt = build_prompt(pack)
    assert "and 3 more" in prompt
    # 8 receipts but only 5 listed = first 5 sequence numbers appear
    assert "seq=0" in prompt
    assert "seq=4" in prompt
    # seq=5 truncated
    assert "seq=5 receipt_hash=" not in prompt


def test_build_prompt_rejects_non_evidence_pack():
    with pytest.raises(PromptBuilderError):
        build_prompt("not a pack")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_prompt_hash_is_deterministic():
    pack = await _make_pack(2)
    p1 = build_prompt(pack)
    p2 = build_prompt(pack)
    assert prompt_hash(p1) == prompt_hash(p2)


@pytest.mark.asyncio
async def test_prompt_hash_differs_for_different_packs():
    a = await _make_pack(1)
    b = await _make_pack(2)
    assert prompt_hash(build_prompt(a)) != prompt_hash(build_prompt(b))


# ========== CP7.1 client ==========


@pytest.mark.asyncio
async def test_mock_client_returns_narrative_with_content_hash():
    client = MockNarrativeClient()
    result = await client.generate_narrative("hello world")
    assert result.narrative_text
    assert result.model_id == "gemini-3-pro-mock"
    assert len(result.content_hash) == 64
    assert result.prompt_token_count >= 1
    assert result.completion_token_count >= 1
    assert result.generated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_mock_client_content_hash_deterministic_for_same_prompt():
    client = MockNarrativeClient()
    r1 = await client.generate_narrative("same prompt")
    r2 = await client.generate_narrative("same prompt")
    # narrative_text + model_id + prompt all match, so content_hash matches
    assert r1.content_hash == r2.content_hash


@pytest.mark.asyncio
async def test_mock_client_content_hash_differs_for_different_prompts():
    client = MockNarrativeClient()
    r1 = await client.generate_narrative("prompt A")
    r2 = await client.generate_narrative("prompt B")
    assert r1.content_hash != r2.content_hash


@pytest.mark.asyncio
async def test_mock_client_raises_when_configured_to_fail():
    client = MockNarrativeClient(fail=True)
    with pytest.raises(NarrativeClientError, match="configured to fail"):
        await client.generate_narrative("x")


@pytest.mark.asyncio
async def test_mock_client_rejects_zero_max_tokens():
    client = MockNarrativeClient()
    with pytest.raises(NarrativeClientError, match="max_tokens must be positive"):
        await client.generate_narrative("x", max_tokens=0)


@pytest.mark.asyncio
async def test_mock_client_accepts_custom_model_id():
    client = MockNarrativeClient(model_id="gemini-3-flash-mock")
    result = await client.generate_narrative("x")
    assert result.model_id == "gemini-3-flash-mock"
