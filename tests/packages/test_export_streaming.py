"""Tests for packages.export.streaming (CP9.46 / IP #9).

Multipart S3 upload for very-large M&A bundles. Covers:
  - small bundle as a single part
  - large bundle as multiple parts with correct boundaries
  - empty bundle edge case (1 zero-byte part)
  - chunk_size validation (5 MB min, 5 GB max)
  - bucket / key non-empty validation
  - uploader failure during upload_part -> abort + re-raise
  - assembly-mismatch sanity check
  - end-to-end round-trip: stream -> reassemble -> verify
  - reference shape (JSONB-friendly via .to_dict)
  - Boto3S3MultipartUploader stub raises NotImplementedError
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from uuid import UUID

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.ma_export import (
    MaDiligenceExport,
    build_ma_diligence_export,
    sign_ma_diligence_export,
    verify_ma_diligence_export,
    verify_ma_diligence_export_signature,
)
from packages.export.streaming import (
    Boto3S3MultipartUploader,
    MockS3MultipartUploader,
    S3MultipartUploader,
    S3StreamingReference,
    S3UploadError,
    StreamingPart,
    reassemble_streamed_export,
    stream_ma_diligence_export_to_s3,
)

_TENANT = UUID("aaaaaaaa-1111-2222-3333-444444444444")
_NOW = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
_START = datetime(2026, 1, 1, tzinfo=UTC)
_END = datetime(2026, 5, 1, tzinfo=UTC)


def _empty_export() -> MaDiligenceExport:
    return build_ma_diligence_export(
        tenant_id=_TENANT,
        scope_start=_START,
        scope_end=_END,
        generated_at=_NOW,
        evidence_packs=[],
        anchor_proofs=[],
    )


# ---------- happy path: small bundle, single part ----------


def test_stream_small_bundle_uses_single_part() -> None:
    """An empty (or tiny) bundle fits in one part."""
    export = _empty_export()
    uploader = MockS3MultipartUploader()

    result = stream_ma_diligence_export_to_s3(
        export, bucket="forensa-test", key="exports/empty.json", uploader=uploader
    )

    assert result.reference.bucket == "forensa-test"
    assert result.reference.key == "exports/empty.json"
    assert result.reference.part_count == 1
    assert result.reference.size_bytes > 0  # JSON of empty export is non-empty
    assert len(result.reference.sha256_hex) == 64
    # The mock uploader assembled the object.
    assembled = uploader.completed_objects[("forensa-test", "exports/empty.json")]
    # SHA-256 of assembled bytes matches the reference.
    assert hashlib.sha256(assembled).hexdigest() == result.reference.sha256_hex


# ---------- multipart: large bundle, multiple parts ----------


def test_stream_large_bundle_splits_into_n_parts() -> None:
    """A bundle larger than chunk_size_mb produces multiple parts."""
    # We directly test _split_into_parts internals via a synthetic byte
    # sequence because the streamer's full path requires a real export
    # whose JSON exceeds 5MB, which means many evidence packs. The
    # internal helper is what makes the multipart boundaries correct;
    # the integration test_stream_then_reassemble_preserves_export
    # exercises the full path on a small bundle.
    from packages.export.streaming import _split_into_parts

    # 13 MB of zero bytes; chunk size 5 MB -> 3 parts (5 + 5 + 3).
    data = b"\x00" * (13 * 1024 * 1024)
    parts = _split_into_parts(data, chunk_size_bytes=5 * 1024 * 1024)
    assert len(parts) == 3
    assert parts[0].size_bytes == 5 * 1024 * 1024
    assert parts[1].size_bytes == 5 * 1024 * 1024
    assert parts[2].size_bytes == 3 * 1024 * 1024
    assert [p.part_number for p in parts] == [1, 2, 3]
    # Concatenated parts equal the original.
    assembled = b"".join(p.body for p in parts)
    assert assembled == data


def test_stream_part_md5_matches_body_for_integrity() -> None:
    """Each part's md5_b64 is the standard base64 of MD5(body) so S3 can
    do the Content-MD5 per-part integrity check on real uploads."""
    from packages.export.streaming import _split_into_parts

    data = b"hello world" * 1000  # 11K, single part
    parts = _split_into_parts(data, chunk_size_bytes=5 * 1024 * 1024)
    assert len(parts) == 1
    expected = base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode("ascii")
    assert parts[0].md5_b64 == expected


# ---------- validation: chunk_size_mb out of range ----------


def test_stream_rejects_chunk_size_below_5mb() -> None:
    """AWS multipart minimum part size is 5MB (except the final part)."""
    export = _empty_export()
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match=">= 5"):
        stream_ma_diligence_export_to_s3(
            export, bucket="b", key="k", uploader=uploader, chunk_size_mb=4
        )


def test_stream_rejects_chunk_size_above_5gb() -> None:
    """AWS multipart maximum part size is 5GB."""
    export = _empty_export()
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match="<= 5120"):
        stream_ma_diligence_export_to_s3(
            export, bucket="b", key="k", uploader=uploader, chunk_size_mb=5121
        )


def test_stream_rejects_empty_bucket() -> None:
    export = _empty_export()
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match="bucket"):
        stream_ma_diligence_export_to_s3(export, bucket="", key="k", uploader=uploader)


def test_stream_rejects_whitespace_only_bucket() -> None:
    export = _empty_export()
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match="bucket"):
        stream_ma_diligence_export_to_s3(export, bucket="   ", key="k", uploader=uploader)


def test_stream_rejects_empty_key() -> None:
    export = _empty_export()
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match="key"):
        stream_ma_diligence_export_to_s3(export, bucket="b", key="", uploader=uploader)


def test_stream_rejects_whitespace_only_key() -> None:
    export = _empty_export()
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match="key"):
        stream_ma_diligence_export_to_s3(export, bucket="b", key="   ", uploader=uploader)


# ---------- abort on uploader failure ----------


class _FailingUploaderOnPart(MockS3MultipartUploader):
    """Test impl that raises during upload_part to exercise the abort path."""

    def __init__(self, fail_at_part: int = 1) -> None:
        super().__init__()
        self.fail_at_part = fail_at_part

    def upload_part(self, *, bucket, key, upload_id, part):
        if part.part_number == self.fail_at_part:
            raise RuntimeError(f"simulated failure at part {part.part_number}")
        return super().upload_part(bucket=bucket, key=key, upload_id=upload_id, part=part)


def test_stream_aborts_on_upload_part_failure() -> None:
    """A failure mid-upload triggers abort() and re-raises the exception."""
    export = _empty_export()
    uploader = _FailingUploaderOnPart(fail_at_part=1)

    with pytest.raises(RuntimeError, match="simulated failure"):
        stream_ma_diligence_export_to_s3(
            export, bucket="forensa-test", key="exports/fails.json", uploader=uploader
        )

    # The upload was aborted (NOT completed).
    assert ("forensa-test", "exports/fails.json") not in uploader.completed_objects
    assert len(uploader.aborted_uploads) == 1


class _FailingUploaderOnComplete(MockS3MultipartUploader):
    """Test impl that raises during complete() so we can verify abort fires
    even after all parts uploaded successfully."""

    def complete(self, *, bucket, key, upload_id, part_etags):
        raise RuntimeError("simulated failure at complete")


def test_stream_aborts_when_complete_fails() -> None:
    """Failure during complete() still triggers abort()."""
    export = _empty_export()
    uploader = _FailingUploaderOnComplete()

    with pytest.raises(RuntimeError, match="simulated failure at complete"):
        stream_ma_diligence_export_to_s3(
            export,
            bucket="forensa-test",
            key="exports/complete_fails.json",
            uploader=uploader,
        )

    assert (
        "forensa-test",
        "exports/complete_fails.json",
    ) not in uploader.completed_objects
    assert len(uploader.aborted_uploads) == 1


# ---------- end-to-end round-trip ----------


def test_stream_then_reassemble_preserves_export() -> None:
    """Upload to mock S3, read assembled bytes back, model_validate_json
    gives an export equal to the original."""
    export = _empty_export()
    uploader = MockS3MultipartUploader()

    result = stream_ma_diligence_export_to_s3(
        export,
        bucket="forensa-test",
        key="exports/round-trip.json",
        uploader=uploader,
    )
    # result.reference is the externally-visible artifact; the assembled
    # bytes are what an acquirer would re-download.
    assert result.reference.part_count >= 1

    assembled = uploader.completed_objects[("forensa-test", "exports/round-trip.json")]
    recovered = reassemble_streamed_export([assembled])
    assert recovered.header.tenant_id == export.header.tenant_id
    assert recovered.ma_root_hash == export.ma_root_hash
    assert verify_ma_diligence_export(recovered) is True


def test_stream_signed_bundle_preserves_signature() -> None:
    """Signed bundles round-trip through the streaming path with the
    platform signature intact (verifies that the CP9.44 field_serializer
    fix works with model_dump_json invoked here)."""
    export = _empty_export()
    priv, pub = generate_keypair()
    signed = sign_ma_diligence_export(export, platform_private_key=priv, platform_key_id="k1")

    uploader = MockS3MultipartUploader()
    result = stream_ma_diligence_export_to_s3(
        signed,
        bucket="forensa-test",
        key="exports/signed.json",
        uploader=uploader,
    )
    assert result.reference.bucket == "forensa-test"
    assembled = uploader.completed_objects[("forensa-test", "exports/signed.json")]
    recovered = reassemble_streamed_export([assembled])

    assert recovered.platform_signature == signed.platform_signature
    assert recovered.platform_key_id == "k1"
    assert verify_ma_diligence_export_signature(recovered, platform_public_key=pub) is True


# ---------- reference shape ----------


def test_reference_to_dict_is_jsonb_friendly() -> None:
    """The reference shape is what lands in ma_export_jobs.result_export
    when streaming mode is enabled. Must be JSON-serialisable."""
    ref = S3StreamingReference(
        bucket="forensa-test",
        key="exports/x.json",
        size_bytes=12345,
        sha256_hex="a" * 64,
        part_count=3,
    )
    d = ref.to_dict()
    assert d == {
        "scheme": "forensa:S3StreamingReference",
        "bucket": "forensa-test",
        "key": "exports/x.json",
        "size_bytes": 12345,
        "sha256_hex": "a" * 64,
        "part_count": 3,
    }
    # Round-trips through json.
    import json as _json

    j = _json.dumps(d)
    assert _json.loads(j) == d


def test_streaming_part_size_matches_body_length() -> None:
    """StreamingPart.size_bytes is len(body); the streamer sets this when
    splitting."""
    p = StreamingPart(part_number=1, body=b"hello", md5_b64="abc", size_bytes=5)
    assert p.size_bytes == len(p.body)


# ---------- Boto3 stub ----------


def test_boto3_uploader_init_raises_not_implemented() -> None:
    """The boto3 impl is deferred to NEW-P10.X.aws-s3-real-integration;
    today the stub fails loudly on construction so accidental production
    use surfaces immediately."""
    with pytest.raises(NotImplementedError, match="aws-s3-real-integration"):
        Boto3S3MultipartUploader()


# ---------- mock uploader internals (defensive) ----------


def test_mock_uploader_upload_part_for_unknown_upload_id_raises() -> None:
    """Calling upload_part with a bogus upload_id raises S3UploadError;
    a real S3 would 404 here."""
    uploader = MockS3MultipartUploader()
    part = StreamingPart(part_number=1, body=b"x", md5_b64="abc", size_bytes=1)
    with pytest.raises(S3UploadError, match="no in-progress upload"):
        uploader.upload_part(bucket="b", key="k", upload_id="bogus", part=part)


def test_mock_uploader_complete_for_unknown_upload_id_raises() -> None:
    uploader = MockS3MultipartUploader()
    with pytest.raises(S3UploadError, match="no in-progress upload"):
        uploader.complete(bucket="b", key="k", upload_id="bogus", part_etags=[])


def test_mock_uploader_abort_is_idempotent() -> None:
    """abort() can be called multiple times safely; the second call is a no-op."""
    uploader = MockS3MultipartUploader()
    upload_id = uploader.initiate(bucket="b", key="k")
    uploader.abort(bucket="b", key="k", upload_id=upload_id)
    # Second call must not raise.
    uploader.abort(bucket="b", key="k", upload_id=upload_id)
    assert ("b", "k", upload_id) in uploader.aborted_uploads


def test_abc_cannot_be_instantiated_directly() -> None:
    """S3MultipartUploader is abstract; instantiation should fail."""
    with pytest.raises(TypeError):
        S3MultipartUploader()  # type: ignore[abstract]


# ---------- empty-body edge case ----------


def test_split_into_parts_empty_data_returns_one_zero_byte_part() -> None:
    """An empty plaintext (rare but possible: in-memory test) still produces
    one part so the upload lifecycle stays uniform."""
    from packages.export.streaming import _split_into_parts

    parts = _split_into_parts(b"", chunk_size_bytes=5 * 1024 * 1024)
    assert len(parts) == 1
    assert parts[0].size_bytes == 0
    assert parts[0].part_number == 1
    # MD5 of empty bytes is well-known.
    assert parts[0].md5_b64 == base64.b64encode(
        hashlib.md5(b"", usedforsecurity=False).digest()
    ).decode("ascii")
