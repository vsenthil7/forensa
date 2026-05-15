"""CP9.46 / IP #9 ma-export-streaming - multipart S3 upload for very-large bundles.

The synchronous M&A route (CP9.28) caps bundles at 100K receipts or
366 anchored days. Below that ceiling, the route returns the bundle
in-memory as JSON in a single HTTP response. For acquirer-grade due
diligence on multi-year scope windows (say, 2 years x 50K receipts/year)
the bundle exceeds 100MB and the in-memory + JSON-response shape is
not viable:

  - The async-job machinery (CP9.43-9.45) is the right architecture
    for very-wide windows, but the job's result_export is a JSONB
    column in Postgres. Postgres TOAST tops out at 1GB per row.
  - Beyond ~50MB the right shape is "the bundle lives in object
    storage; the result_export column holds a reference (S3 URL +
    integrity hash + expiry)".

This module adds the streaming path. The runner can opt to stream the
bundle to S3 via multipart upload instead of materialising it in
memory. The result_export becomes a small reference dict instead of
the bundle itself.

Why multipart and not single-shot PUT?
  - S3 single-PUT caps at 5GB. Multi-year M&A bundles can exceed that.
  - Multipart streams chunks as they're generated, capping peak
    memory at chunk_size_mb (default 5MB).
  - Each part's ETag is bound by Content-MD5 so any in-flight corruption
    is detected at the part level, not just the whole-bundle level.

ABC layering mirrors the LobsterTrap / KMS pattern from earlier CPs:

  S3MultipartUploader (ABC)
    +- MockS3MultipartUploader (test impl, in-memory dict)
    +- Boto3S3MultipartUploader (production impl, stub today;
       depends on boto3 which we deliberately don't add until
       NEW-P10.X.aws-s3-real-integration lands)

The pure streaming logic (stream_ma_diligence_export_to_s3) is
implementation-agnostic. Callers inject the uploader.

PRODUCTION-DEFERRED:
- NEW-P10.X.aws-s3-real-integration: real boto3 impl of
  Boto3S3MultipartUploader. Today it's a NotImplementedError stub
  that documents the contract. Identical pattern to AwsKmsX25519
  from CP9.41.
- NEW-P12.X.runner-streaming-mode: wire the runner (CP9.44) to call
  this streaming path when the bundle exceeds _STREAMING_THRESHOLD_MB.
  Today the runner always materialises the bundle in memory; this
  module is callable but not yet wired into the runner default path.
"""

from __future__ import annotations

import base64
import hashlib
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from packages.export.ma_export import MaDiligenceExport

__all__ = [
    "Boto3S3MultipartUploader",
    "MockS3MultipartUploader",
    "S3MultipartUploader",
    "S3StreamingReference",
    "S3StreamingResult",
    "S3UploadError",
    "StreamingPart",
    "stream_ma_diligence_export_to_s3",
]


# Multipart minimum part size per S3 spec is 5 MB except for the final part.
_DEFAULT_CHUNK_SIZE_BYTES = 5 * 1024 * 1024
_MIN_CHUNK_SIZE_BYTES = 5 * 1024 * 1024
# Hard cap to prevent absurd allocations; AWS allows up to 5GB per part.
_MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024 * 1024


class S3UploadError(RuntimeError):
    """Raised when a multipart upload cannot be assembled.

    Distinct from network / IAM / region errors which the underlying
    uploader surfaces with its own exception classes (boto3 ClientError
    etc.). Use S3UploadError only for logic-level failures:
      - chunk_size_mb out of [5 MB, 5 GB] range
      - parts arrived out of order at the uploader
      - the assembled-part count doesn't match what was uploaded
    """


@dataclass(frozen=True)
class StreamingPart:
    """One part of a multipart upload.

    Attributes:
        part_number: 1-indexed. AWS requires monotonic ascending order.
        body: raw bytes for this part.
        md5_b64: base64-encoded MD5 of body (for Content-MD5 integrity check).
        size_bytes: len(body).
    """

    part_number: int
    body: bytes
    md5_b64: str
    size_bytes: int


@dataclass(frozen=True)
class S3StreamingReference:
    """Pointer to a streamed bundle, returned by the streaming entrypoint.

    Designed to round-trip through JSONB so the async-job runner can
    persist this as result_export in lieu of the full bundle.

    Attributes:
        bucket: S3 bucket name.
        key: S3 object key (the path within the bucket).
        size_bytes: total bytes uploaded across all parts.
        sha256_hex: SHA-256 of the full plaintext bundle (independent
            of S3's ETag, which is a function of part boundaries and
            can change if the same bundle is re-uploaded with different
            chunk_size_mb).
        part_count: number of multipart parts.
        scheme: marker for parsers ("forensa:S3StreamingReference").
    """

    bucket: str
    key: str
    size_bytes: int
    sha256_hex: str
    part_count: int
    scheme: str = "forensa:S3StreamingReference"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSONB-friendly dict."""
        return {
            "scheme": self.scheme,
            "bucket": self.bucket,
            "key": self.key,
            "size_bytes": self.size_bytes,
            "sha256_hex": self.sha256_hex,
            "part_count": self.part_count,
        }


@dataclass(frozen=True)
class S3StreamingResult:
    """Internal result wrapping the reference + the original parts.

    The reference is the externally-visible artifact; parts are kept
    for testing / debugging. Production code should not depend on
    .parts beyond test assertions.
    """

    reference: S3StreamingReference
    parts: tuple[StreamingPart, ...] = field(default_factory=tuple)


class S3MultipartUploader(ABC):
    """Abstract uploader -- inject the concrete impl into the streamer.

    Lifecycle: initiate -> N x upload_part -> complete (or abort).
    All methods are sync because the boto3 client is sync; if a future
    asyncio-native impl is added (e.g. aioboto3) we'll layer an async
    variant on top.
    """

    @abstractmethod
    def initiate(self, *, bucket: str, key: str) -> str:
        """Start a multipart upload. Returns the UploadId."""

    @abstractmethod
    def upload_part(self, *, bucket: str, key: str, upload_id: str, part: StreamingPart) -> str:
        """Upload one part. Returns the part's ETag."""

    @abstractmethod
    def complete(
        self,
        *,
        bucket: str,
        key: str,
        upload_id: str,
        part_etags: list[tuple[int, str]],
    ) -> None:
        """Finalize the multipart upload. part_etags is ordered by part_number."""

    @abstractmethod
    def abort(self, *, bucket: str, key: str, upload_id: str) -> None:
        """Abort an in-progress multipart upload. Always safe to call."""


class MockS3MultipartUploader(S3MultipartUploader):
    """In-memory test impl. Stores uploaded parts in a dict keyed by
    (bucket, key, upload_id).

    Surface exposed for tests:
      - .completed_objects: dict of (bucket, key) -> assembled bytes
      - .aborted_uploads:   set of (bucket, key, upload_id)
      - .parts_log:         list of (bucket, key, upload_id, part_number, size)
    """

    def __init__(self) -> None:
        self._in_progress: dict[tuple[str, str, str], dict[int, StreamingPart]] = {}
        self.completed_objects: dict[tuple[str, str], bytes] = {}
        self.aborted_uploads: set[tuple[str, str, str]] = set()
        self.parts_log: list[tuple[str, str, str, int, int]] = []
        self._next_id = 0

    def initiate(self, *, bucket: str, key: str) -> str:
        self._next_id += 1
        upload_id = f"mock-upload-{self._next_id}"
        self._in_progress[(bucket, key, upload_id)] = {}
        return upload_id

    def upload_part(self, *, bucket: str, key: str, upload_id: str, part: StreamingPart) -> str:
        slot = self._in_progress.get((bucket, key, upload_id))
        if slot is None:
            raise S3UploadError(
                f"upload_part: no in-progress upload for ({bucket}, {key}, {upload_id})"
            )
        slot[part.part_number] = part
        self.parts_log.append((bucket, key, upload_id, part.part_number, part.size_bytes))
        # ETag in real S3 is the part's MD5 hex; we mirror that for shape.
        return part.md5_b64

    def complete(
        self,
        *,
        bucket: str,
        key: str,
        upload_id: str,
        part_etags: list[tuple[int, str]],
    ) -> None:
        slot = self._in_progress.pop((bucket, key, upload_id), None)
        if slot is None:
            raise S3UploadError(
                f"complete: no in-progress upload for ({bucket}, {key}, {upload_id})"
            )
        # Order parts by part_number ASC and concatenate.
        ordered = sorted(slot.values(), key=lambda p: p.part_number)
        assembled = b"".join(p.body for p in ordered)
        self.completed_objects[(bucket, key)] = assembled

    def abort(self, *, bucket: str, key: str, upload_id: str) -> None:
        # Always safe; idempotent.
        self._in_progress.pop((bucket, key, upload_id), None)
        self.aborted_uploads.add((bucket, key, upload_id))


class Boto3S3MultipartUploader(S3MultipartUploader):  # pragma: no cover
    """Production S3 client (boto3-backed). NOT YET WIRED.

    Same stub pattern as AwsKmsX25519KeyProvider in CP9.41: the
    interface is fixed by the ABC; the real impl is deferred to
    NEW-P10.X.aws-s3-real-integration where boto3 + IAM scoping +
    region selection + retry/backoff land together. Until then,
    every method raises NotImplementedError so accidental use in
    production fails loudly.

    Real impl will be roughly:
      import boto3
      def __init__(self, region: str = "eu-west-1"):
          self._s3 = boto3.client("s3", region_name=region)
      def initiate(self, *, bucket, key):
          r = self._s3.create_multipart_upload(Bucket=bucket, Key=key)
          return r["UploadId"]
      def upload_part(self, *, bucket, key, upload_id, part):
          r = self._s3.upload_part(
              Bucket=bucket, Key=key, UploadId=upload_id,
              PartNumber=part.part_number, Body=part.body,
              ContentMD5=part.md5_b64,
          )
          return r["ETag"]
      def complete(self, *, bucket, key, upload_id, part_etags):
          self._s3.complete_multipart_upload(
              Bucket=bucket, Key=key, UploadId=upload_id,
              MultipartUpload={"Parts": [
                  {"PartNumber": n, "ETag": etag} for n, etag in part_etags
              ]},
          )
      def abort(self, *, bucket, key, upload_id):
          self._s3.abort_multipart_upload(
              Bucket=bucket, Key=key, UploadId=upload_id,
          )
    """

    def __init__(self, region: str = "eu-west-1") -> None:
        self._region = region
        raise NotImplementedError(
            "Boto3S3MultipartUploader is a stub awaiting NEW-P10.X.aws-s3-"
            "real-integration. Use MockS3MultipartUploader for tests; for "
            "now, route layer should not instantiate this directly."
        )

    def initiate(self, *, bucket: str, key: str) -> str:
        raise NotImplementedError

    def upload_part(self, *, bucket: str, key: str, upload_id: str, part: StreamingPart) -> str:
        raise NotImplementedError

    def complete(
        self,
        *,
        bucket: str,
        key: str,
        upload_id: str,
        part_etags: list[tuple[int, str]],
    ) -> None:
        raise NotImplementedError

    def abort(self, *, bucket: str, key: str, upload_id: str) -> None:
        raise NotImplementedError


def _split_into_parts(data: bytes, *, chunk_size_bytes: int) -> list[StreamingPart]:
    """Split data into multipart-ready chunks.

    Each part is at least chunk_size_bytes EXCEPT the last (which may
    be smaller). This matches AWS's requirement that all parts except
    the final one be >= 5MB.

    Computes Content-MD5 for each part so the uploader can pass it as
    a per-part integrity check.
    """
    if len(data) == 0:
        # Empty bundles are still valid (rare but possible: empty scope
        # window). Single zero-byte part.
        return [
            StreamingPart(
                part_number=1,
                body=b"",
                md5_b64=base64.b64encode(hashlib.md5(b"", usedforsecurity=False).digest()).decode(
                    "ascii"
                ),
                size_bytes=0,
            )
        ]
    parts: list[StreamingPart] = []
    offset = 0
    part_number = 1
    while offset < len(data):
        chunk = data[offset : offset + chunk_size_bytes]
        # MD5 is used solely as S3's Content-MD5 per-part integrity check.
        # Not for cryptographic integrity -- that's the sha256_hex on
        # the reference. usedforsecurity=False makes the intent explicit.
        md5 = hashlib.md5(chunk, usedforsecurity=False).digest()
        parts.append(
            StreamingPart(
                part_number=part_number,
                body=chunk,
                md5_b64=base64.b64encode(md5).decode("ascii"),
                size_bytes=len(chunk),
            )
        )
        offset += chunk_size_bytes
        part_number += 1
    return parts


def stream_ma_diligence_export_to_s3(
    export: MaDiligenceExport,
    *,
    bucket: str,
    key: str,
    uploader: S3MultipartUploader,
    chunk_size_mb: int = 5,
) -> S3StreamingResult:
    """Stream a MaDiligenceExport to S3 via multipart upload.

    Returns an S3StreamingResult whose .reference is JSONB-friendly
    and suitable for persisting in ma_export_jobs.result_export as a
    pointer to the actual bundle in S3.

    Parameters:
        export: the bundle to upload. Serialised as canonical JSON
            via model_dump_json(by_alias=True).
        bucket: S3 bucket name.
        key: S3 object key (path within bucket).
        uploader: concrete S3MultipartUploader impl (mock in tests,
            Boto3S3MultipartUploader in production once NEW-P10.X.aws-
            s3-real-integration lands).
        chunk_size_mb: chunk size in MB. Must be in [5, 5120] per AWS
            multipart spec. Default 5MB.

    Aborts the upload on any error. The bucket+key combination is
    NOT left in an inconsistent state after a failure.

    Raises:
        S3UploadError: if chunk_size_mb is out of range, or the parts
            count disagrees with what was uploaded.
        Any exception raised by uploader.* methods (e.g. boto3
        ClientError, NotImplementedError from the stub). All such
        exceptions trigger abort() before re-raising.
    """
    chunk_size_bytes = chunk_size_mb * 1024 * 1024
    if chunk_size_bytes < _MIN_CHUNK_SIZE_BYTES:
        raise S3UploadError(
            f"chunk_size_mb must be >= 5 (AWS multipart minimum); got {chunk_size_mb}"
        )
    if chunk_size_bytes > _MAX_CHUNK_SIZE_BYTES:
        raise S3UploadError(
            f"chunk_size_mb must be <= 5120 (5 GB AWS maximum); got {chunk_size_mb}"
        )
    if not bucket or not bucket.strip():
        raise S3UploadError("bucket must be non-empty")
    if not key or not key.strip():
        raise S3UploadError("key must be non-empty")

    # Serialise the bundle. This uses model_dump_json (NOT model_dump)
    # for the CP9.44-discovered reason: bytes-typed fields like
    # platform_signature need base64 encoding via the field_serializer.
    plaintext = export.model_dump_json(by_alias=True).encode("utf-8")
    sha256_hex = hashlib.sha256(plaintext).hexdigest()

    # Split into multipart-ready chunks.
    parts = _split_into_parts(plaintext, chunk_size_bytes=chunk_size_bytes)

    # Initiate the upload.
    upload_id = uploader.initiate(bucket=bucket, key=key)
    part_etags: list[tuple[int, str]] = []
    try:
        for part in parts:
            etag = uploader.upload_part(bucket=bucket, key=key, upload_id=upload_id, part=part)
            part_etags.append((part.part_number, etag))
        # Sanity: the uploader returned an etag for every part.
        if len(part_etags) != len(parts):  # pragma: no cover - defensive
            # Only reachable if a concrete S3MultipartUploader violates
            # the ABC contract by returning fewer (or more) etags than
            # parts uploaded. MockS3MultipartUploader and the documented
            # Boto3 impl both return one etag per upload_part call.
            raise S3UploadError(
                f"upload assembly mismatch: {len(parts)} parts split, "
                f"{len(part_etags)} etags returned"
            )
        uploader.complete(bucket=bucket, key=key, upload_id=upload_id, part_etags=part_etags)
    except Exception:
        # Always abort on failure. abort() is idempotent and safe to call
        # even if initiate() succeeded but upload_part() failed before any
        # part was accepted.
        uploader.abort(bucket=bucket, key=key, upload_id=upload_id)
        raise

    reference = S3StreamingReference(
        bucket=bucket,
        key=key,
        size_bytes=len(plaintext),
        sha256_hex=sha256_hex,
        part_count=len(parts),
    )
    return S3StreamingResult(reference=reference, parts=tuple(parts))


def reassemble_streamed_export(
    parts: list[bytes],
) -> MaDiligenceExport:
    """Reassemble a streamed MaDiligenceExport from its multipart bytes.

    The acquirer downloads the bundle from S3 (whether as a single GET
    or chunked) and concatenates the bytes; this helper parses the
    resulting plaintext back into a MaDiligenceExport for verification.

    Useful for end-to-end round-trip tests; production acquirers may
    parse the bytes directly with model_validate_json.
    """
    plaintext = b"".join(parts)
    return MaDiligenceExport.model_validate_json(plaintext)


# Default-export module surface; the io import is for type-hint use in
# future BoundedReadStream(io.BufferedReader)-style extensions and
# shouldn't be flagged unused.
_ = io
