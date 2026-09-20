"""Typed settlement-source observations and deterministic health assessment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TypeAlias


NormalizedValue: TypeAlias = Decimal | str | bool
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"
    REVISION_PENDING = "REVISION_PENDING"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class FailureKind(str, Enum):
    RETRIEVAL = "RETRIEVAL"
    PARSE = "PARSE"
    SEMANTIC = "SEMANTIC"


class Finality(str, Enum):
    PRELIMINARY = "PRELIMINARY"
    REVISED = "REVISED"
    FINAL = "FINAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceIdentity:
    provider: str
    dataset: str
    source_version: str

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.dataset.strip() or not self.source_version.strip():
            raise ValueError("source identity fields must be non-empty")


@dataclass(frozen=True)
class SourceFailure:
    identity: SourceIdentity
    kind: FailureKind
    provenance: str
    message: str

    def __post_init__(self) -> None:
        if not self.provenance.strip() or not self.message.strip():
            raise ValueError("failure provenance and message must be non-empty")


@dataclass(frozen=True)
class SourceObservation:
    identity: SourceIdentity
    retrieved_at: datetime
    observed_at: datetime
    published_at: datetime
    value: NormalizedValue
    unit: str | None
    provenance: str
    finality: Finality
    revision_id: str | None
    revision_pending: bool
    schema_fingerprint: str
    raw_evidence_sha256: str

    def __post_init__(self) -> None:
        for field_name in ("retrieved_at", "observed_at", "published_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.retrieved_at < self.published_at:
            raise ValueError("retrieved_at cannot precede published_at")
        if not self.provenance.strip():
            raise ValueError("provenance must be non-empty")
        if not _SHA256_RE.fullmatch(self.schema_fingerprint):
            raise ValueError("schema_fingerprint must be a lowercase SHA-256 hex digest")
        if not _SHA256_RE.fullmatch(self.raw_evidence_sha256):
            raise ValueError("raw_evidence_sha256 must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True)
class AdapterResult:
    observation: SourceObservation | None = None
    failure: SourceFailure | None = None

    def __post_init__(self) -> None:
        if (self.observation is None) == (self.failure is None):
            raise ValueError("adapter result must contain exactly one of observation or failure")


@dataclass(frozen=True)
class HealthPolicy:
    max_age: timedelta
    expected_schema_fingerprint: str | None = None
    require_final: bool = True

    def __post_init__(self) -> None:
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        if self.expected_schema_fingerprint is not None and not _SHA256_RE.fullmatch(
            self.expected_schema_fingerprint
        ):
            raise ValueError("expected_schema_fingerprint must be a lowercase SHA-256 hex digest")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("health clock must be timezone-aware")
    return value.astimezone(UTC)


def assess_health(
    result: AdapterResult,
    *,
    policy: HealthPolicy,
    now: datetime,
    conflicting: bool = False,
) -> HealthStatus:
    """Map one adapter result to an explicit fail-closed health state."""
    current = _utc(now)
    if result.failure is not None:
        if result.failure.kind is FailureKind.RETRIEVAL:
            return HealthStatus.UNAVAILABLE
        return HealthStatus.UNKNOWN

    observation = result.observation
    assert observation is not None

    if conflicting:
        return HealthStatus.CONFLICT
    if (
        policy.expected_schema_fingerprint is not None
        and observation.schema_fingerprint != policy.expected_schema_fingerprint
    ):
        return HealthStatus.SCHEMA_DRIFT
    if observation.revision_pending or (
        policy.require_final and observation.finality is not Finality.FINAL
    ):
        return HealthStatus.REVISION_PENDING
    if current - observation.published_at.astimezone(UTC) > policy.max_age:
        return HealthStatus.STALE
    return HealthStatus.HEALTHY


def retrieval_failure(
    identity: SourceIdentity,
    *,
    provenance: str,
    message: str,
) -> AdapterResult:
    """Represent caller-side network/transport failure without inventing fallback evidence."""
    return AdapterResult(
        failure=SourceFailure(
            identity=identity,
            kind=FailureKind.RETRIEVAL,
            provenance=provenance,
            message=message,
        )
    )
