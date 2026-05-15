"""Unit tests for packages.jobs.ma_export_runner (CP9.44 / IP #8).

Runner half of NEW-P12.X.ma-export-async-job. The PG integration test
at tests/integration/test_ma_export_runner_pg.py exercises the runner
end-to-end against a real Postgres + seeded receipts. These unit tests
cover branches that are hard to provoke with a real DB:

- The job row disappears between Session A and Session B (a runner-internal
  race).
- The job is not in 'pending' status at runner start (a state-machine
  precondition violation).
- The Session B work raises -> Session C records failure with the
  exception's name + message.
- Session C ALSO fails -> MaExportRunnerError is raised so the caller
  knows the runner couldn't finalise.

Strategy: monkeypatch the repository helpers + the SQL execute paths to
script the responses Session A/B/C see. The runner's branching logic is
the test target, not the export pipeline (which has its own dedicated
test suites in tests/packages/test_ma_export.py).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from packages.jobs import ma_export_runner
from packages.jobs.ma_export_runner import (
    MaExportRunnerError,
    _serialise_result,
    run_ma_export_job,
)
from packages.ledger.ma_export_job_repository import MaExportJobStateError

_TENANT_ID = UUID("aaaaaaaa-1111-2222-3333-444444444444")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_sessionmaker(open_sessions: list[MagicMock]) -> MagicMock:
    """Build a fake sessionmaker that yields each session in order.

    Each call to sessionmaker() returns the next entry in open_sessions
    wrapped in an async context manager.
    """
    call_index = {"n": 0}

    def _factory():
        idx = call_index["n"]
        call_index["n"] += 1
        session = open_sessions[idx]
        # Wrap in an async context manager.
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    sm = MagicMock(side_effect=_factory)
    return sm


def _make_session() -> MagicMock:
    """Build a fake AsyncSession with the typical mock helpers."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


# ---------- happy path is covered by PG integration; here we cover failure paths ----------


def test_run_ma_export_job_raises_when_session_a_state_error(monkeypatch) -> None:
    """If the row is not in 'pending' status, Session A's mark fails;
    the runner raises MaExportRunnerError without touching Session B."""
    session_a = _make_session()
    sm = _make_sessionmaker([session_a])

    async def _bad_mark_running(*a, **kw):
        raise MaExportJobStateError("already running")

    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_pending_to_running", _bad_mark_running
    )

    job_id = uuid4()
    with pytest.raises(MaExportRunnerError, match="cannot start"):
        _run(run_ma_export_job(sm, job_id=job_id))

    # Only Session A was opened; Session B never built.
    assert sm.call_count == 1
    session_a.rollback.assert_awaited_once()
    session_a.commit.assert_not_awaited()


def test_run_ma_export_job_raises_when_row_disappears_between_a_and_b(
    monkeypatch,
) -> None:
    """Row deleted between Session A's commit and Session B's fetch ->
    Session B can't proceed. Session C is opened to attempt a failure
    write but the row is also gone so that mark itself fails ->
    MaExportRunnerError surfaces.
    """
    session_a = _make_session()
    session_b = _make_session()
    session_c = _make_session()
    sm = _make_sessionmaker([session_a, session_b, session_c])

    async def _good_mark_running(*a, **kw):
        return None

    async def _row_gone(session, jid, **kw):
        return None  # Session B + C both see None

    async def _cannot_mark_failed_either(*a, **kw):
        raise MaExportJobStateError("job not found")

    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_pending_to_running", _good_mark_running
    )
    monkeypatch.setattr(ma_export_runner, "get_ma_export_job_by_id", _row_gone)
    monkeypatch.setattr(ma_export_runner, "mark_ma_export_job_failed", _cannot_mark_failed_either)

    job_id = uuid4()
    with pytest.raises(MaExportRunnerError, match="could not be marked failed"):
        _run(run_ma_export_job(sm, job_id=job_id))

    # Session A locked + committed, Session B opened + found nothing,
    # Session C tried to mark failed and ALSO failed.
    assert sm.call_count == 3


def test_run_ma_export_job_session_b_throws_session_c_records_failure(
    monkeypatch,
) -> None:
    """Session B's work raises a generic exception. Session C opens, marks
    the row failed with the exception type + message, commits cleanly.
    The runner does NOT re-raise -- the failure is the user-visible
    outcome via the row.
    """
    session_a = _make_session()
    session_b = _make_session()
    session_c = _make_session()
    sm = _make_sessionmaker([session_a, session_b, session_c])

    async def _good_mark_running(*a, **kw):
        return None

    row = MagicMock()
    row.tenant_id = _TENANT_ID
    row.scope_start = datetime(2026, 1, 1, tzinfo=UTC)
    row.scope_end = datetime(2026, 5, 1, tzinfo=UTC)
    row.encrypt_for_pubkey_b64 = None
    row.platform_sign_key_id = None

    async def _row_present(session, jid, **kw):
        return row

    async def _build_export_blows_up(*a, **kw):
        raise RuntimeError("anchor table on fire")

    mark_failed_calls: list[dict] = []

    async def _record_failed(session, jid, *, error_message, **kw):
        mark_failed_calls.append({"job_id": jid, "error_message": error_message})

    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_pending_to_running", _good_mark_running
    )
    monkeypatch.setattr(ma_export_runner, "get_ma_export_job_by_id", _row_present)
    monkeypatch.setattr(ma_export_runner, "_build_export", _build_export_blows_up)
    monkeypatch.setattr(ma_export_runner, "mark_ma_export_job_failed", _record_failed)

    job_id = uuid4()
    # No raise: the failure is recorded in the row, not propagated.
    _run(run_ma_export_job(sm, job_id=job_id))

    assert len(mark_failed_calls) == 1
    err = mark_failed_calls[0]["error_message"]
    assert err.startswith("RuntimeError: ")
    assert "anchor table on fire" in err
    session_c.commit.assert_awaited_once()


def test_run_ma_export_job_skips_signing_when_no_platform_key(monkeypatch) -> None:
    """If platform_signing_key is None, we don't even call the sign path.

    Covers the runner's branch where the job row says platform_sign_key_id
    is None (and the caller passed no key either).
    """
    session_a = _make_session()
    session_b = _make_session()
    sm = _make_sessionmaker([session_a, session_b])

    async def _good_mark_running(*a, **kw):
        return None

    row = MagicMock()
    row.tenant_id = _TENANT_ID
    row.scope_start = datetime(2026, 1, 1, tzinfo=UTC)
    row.scope_end = datetime(2026, 5, 1, tzinfo=UTC)
    row.encrypt_for_pubkey_b64 = None
    row.platform_sign_key_id = None  # NO key id on the row

    async def _row_present(session, jid, **kw):
        return row

    # Fake export object; the test asserts mark_completed sees its dict.
    fake_export = MagicMock()
    fake_export.model_dump_json = MagicMock(
        return_value='{"@type": "forensa:MaDiligenceExport", "ma_root_hash": "' + "a" * 64 + '"}'
    )

    async def _build_returns(*a, **kw):
        return fake_export

    completed_calls: list[dict] = []

    async def _record_completed(session, jid, *, result_export, **kw):
        completed_calls.append({"job_id": jid, "result_export": result_export})

    sign_called = {"n": 0}

    def _no_sign(*a, **kw):  # pragma: no cover - asserted to NOT be called
        sign_called["n"] += 1
        return fake_export

    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_pending_to_running", _good_mark_running
    )
    monkeypatch.setattr(ma_export_runner, "get_ma_export_job_by_id", _row_present)
    monkeypatch.setattr(ma_export_runner, "_build_export", _build_returns)
    monkeypatch.setattr(ma_export_runner, "sign_ma_diligence_export", _no_sign)
    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_running_to_completed", _record_completed
    )

    job_id = uuid4()
    _run(run_ma_export_job(sm, job_id=job_id, platform_signing_key=None))

    assert len(completed_calls) == 1
    assert sign_called["n"] == 0  # sign was NOT called


def test_run_ma_export_job_signs_when_platform_key_and_keyid_both_present(
    monkeypatch,
) -> None:
    """If the row has platform_sign_key_id AND the runner has a private key,
    sign_ma_diligence_export IS called.
    """
    session_a = _make_session()
    session_b = _make_session()
    sm = _make_sessionmaker([session_a, session_b])

    async def _good_mark_running(*a, **kw):
        return None

    row = MagicMock()
    row.tenant_id = _TENANT_ID
    row.scope_start = datetime(2026, 1, 1, tzinfo=UTC)
    row.scope_end = datetime(2026, 5, 1, tzinfo=UTC)
    row.encrypt_for_pubkey_b64 = None
    row.platform_sign_key_id = "platform-key-v1"

    async def _row_present(session, jid, **kw):
        return row

    unsigned_export = MagicMock()
    unsigned_export.model_dump_json = MagicMock(
        return_value='{"@type": "forensa:MaDiligenceExport", "platform_signature": null}'
    )
    signed_export = MagicMock()
    signed_export.model_dump_json = MagicMock(
        return_value='{"@type": "forensa:MaDiligenceExport", "platform_signature": "signed"}'
    )

    async def _build_returns(*a, **kw):
        return unsigned_export

    sign_calls: list[dict] = []

    def _record_sign(export, *, platform_private_key, platform_key_id):
        sign_calls.append({"private_key_len": len(platform_private_key), "key_id": platform_key_id})
        return signed_export

    completed_calls: list[dict] = []

    async def _record_completed(session, jid, *, result_export, **kw):
        completed_calls.append({"job_id": jid, "result_export": result_export})

    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_pending_to_running", _good_mark_running
    )
    monkeypatch.setattr(ma_export_runner, "get_ma_export_job_by_id", _row_present)
    monkeypatch.setattr(ma_export_runner, "_build_export", _build_returns)
    monkeypatch.setattr(ma_export_runner, "sign_ma_diligence_export", _record_sign)
    monkeypatch.setattr(
        ma_export_runner, "mark_ma_export_job_running_to_completed", _record_completed
    )

    job_id = uuid4()
    fake_key = b"\x01" * 32
    _run(run_ma_export_job(sm, job_id=job_id, platform_signing_key=fake_key))

    assert len(sign_calls) == 1
    assert sign_calls[0]["private_key_len"] == 32
    assert sign_calls[0]["key_id"] == "platform-key-v1"
    # The signed_export is what got serialised + persisted.
    assert completed_calls[0]["result_export"]["platform_signature"] == "signed"


# ---------- _serialise_result branches ----------


def test_serialise_result_no_encryption_returns_export_dump() -> None:
    """Encryption OFF -> json.loads(model_dump_json(by_alias=True)) directly."""
    fake_export = MagicMock()
    fake_export.model_dump_json = MagicMock(
        return_value='{"@type": "forensa:MaDiligenceExport", "ma_root_hash": "abc"}'
    )
    result = _serialise_result(fake_export, encrypt_for_pubkey_b64=None)
    assert result == {"@type": "forensa:MaDiligenceExport", "ma_root_hash": "abc"}
    fake_export.model_dump_json.assert_called_once_with(by_alias=True)


def test_serialise_result_invalid_base64_raises_ma_export_error() -> None:
    """Encryption ON with non-base64 input -> MaExportError so the runner's
    outer handler marks the job failed cleanly.

    base64.urlsafe_b64decode is forgiving of unknown ASCII chars but
    raises ValueError on non-ASCII bytes. Pass an explicit non-ASCII
    char to trigger the decode failure deterministically.
    """
    from packages.export.ma_export import MaExportError

    fake_export = MagicMock()
    # chr(255) is non-ASCII; the base64 decoder raises ValueError.
    bad_b64 = "AAAA" + chr(255)
    with pytest.raises(MaExportError, match="not valid base64"):
        _serialise_result(fake_export, encrypt_for_pubkey_b64=bad_b64)


def test_serialise_result_encrypt_failure_raises_ma_export_error(monkeypatch) -> None:
    """If encrypt_for_recipient itself fails (e.g. wrong key length),
    _serialise_result wraps the EncryptError in MaExportError."""
    from packages.crypto.encrypt import EncryptError
    from packages.export.ma_export import MaExportError

    fake_export = MagicMock()
    fake_export.model_dump_json = MagicMock(return_value='{"x": 1}')

    def _bad_encrypt(*a, **kw):
        raise EncryptError("wrong key length")

    monkeypatch.setattr(ma_export_runner, "encrypt_for_recipient", _bad_encrypt)

    # 32 bytes b64 encoded = ~44 chars urlsafe
    pubkey_b64 = "A" * 43  # decode-safe length but bad key bytes
    with pytest.raises(MaExportError, match="encryption failed"):
        _serialise_result(fake_export, encrypt_for_pubkey_b64=pubkey_b64)


def test_serialise_result_encryption_on_returns_envelope_dump(monkeypatch) -> None:
    """Encryption ON happy path -> CipherEnvelope dict via model_dump_json + json.loads."""
    fake_export = MagicMock()
    fake_export.model_dump_json = MagicMock(return_value='{"x": 1}')

    fake_envelope = MagicMock()
    fake_envelope.model_dump_json = MagicMock(
        return_value='{"scheme": "x25519-chacha20poly1305-v1", "ciphertext_b64": "abc"}'
    )

    def _good_encrypt(plaintext, *, recipient_public_key):
        return fake_envelope

    monkeypatch.setattr(ma_export_runner, "encrypt_for_recipient", _good_encrypt)

    # Valid url-safe base64 of 32 bytes.
    pubkey_b64 = "AAAA" + "B" * 39  # 43 chars, urlsafe alphabet, decodes to 32 bytes
    result = _serialise_result(fake_export, encrypt_for_pubkey_b64=pubkey_b64)
    assert result == {
        "scheme": "x25519-chacha20poly1305-v1",
        "ciphertext_b64": "abc",
    }


def test_serialise_result_pads_missing_base64_equals(monkeypatch) -> None:
    """A 43-char urlsafe-b64 string (no trailing '=') is padded before decode."""
    fake_export = MagicMock()
    fake_export.model_dump_json = MagicMock(return_value="{}")

    captured = {}

    def _capture_encrypt(plaintext, *, recipient_public_key):
        captured["key_len"] = len(recipient_public_key)
        envelope = MagicMock()
        envelope.model_dump_json = MagicMock(
            return_value='{"scheme": "x25519-chacha20poly1305-v1"}'
        )
        return envelope

    monkeypatch.setattr(ma_export_runner, "encrypt_for_recipient", _capture_encrypt)

    # 43-char urlsafe-b64 of 32 bytes (no padding).
    pubkey_b64 = "AAAA" + "B" * 39
    _serialise_result(fake_export, encrypt_for_pubkey_b64=pubkey_b64)
    # 32-byte key recovered after padding.
    assert captured["key_len"] == 32


# ---------- module surface ----------


def test_runner_module_exports() -> None:
    """Public surface is the two names; everything else is internal."""
    assert run_ma_export_job is not None
    assert MaExportRunnerError is not None
    assert issubclass(MaExportRunnerError, RuntimeError)
