from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Operator(str, Enum):
    ABOVE = "above"
    BELOW = "below"


class TieBehavior(str, Enum):
    YES = "yes"
    NO = "no"
    INSUFFICIENT = "insufficient"


class Aggregation(str, Enum):
    LAST = "last"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"


class Sampling(str, Enum):
    ALL = "all"
    LATEST = "latest"


class RevisionPolicy(str, Enum):
    FINAL_ONLY = "final_only"
    LATEST = "latest"


class Fallback(str, Enum):
    UNKNOWN = "unknown"
    INVALID = "invalid"


@dataclass(frozen=True)
class Predicate:
    operator: Operator
    threshold: Decimal


@dataclass(frozen=True)
class ObservationWindow:
    start: datetime
    end: datetime
    timezone: str


@dataclass(frozen=True)
class SourceBinding:
    source_id: str
    field: str


@dataclass(frozen=True)
class OutcomeMapping:
    yes: str
    no: str
    unknown: str
    invalid: str

    def for_status(self, status: str) -> str:
        return getattr(self, status)


@dataclass(frozen=True)
class EventContract:
    schema_version: str
    market_id: str
    event_id: str
    predicate: Predicate
    window: ObservationWindow
    source: SourceBinding
    aggregation: Aggregation
    sampling: Sampling
    revision_policy: RevisionPolicy
    tie_behavior: TieBehavior
    fallback: Fallback
    outcomes: OutcomeMapping


@dataclass(frozen=True)
class Evidence:
    source_id: str
    field: str
    observed_at: datetime
    value: Decimal
    final: bool
    revision: int


@dataclass(frozen=True)
class CompiledContract:
    contract: EventContract
    canonical_json: str
    content_hash: str


@dataclass(frozen=True)
class EvaluationResult:
    contract_hash: str
    evidence_hash: str
    status: str
    outcome: str
    observed_value: str | None
    reason: str
    result_hash: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "contract_hash": self.contract_hash,
            "evidence_hash": self.evidence_hash,
            "status": self.status,
            "outcome": self.outcome,
            "observed_value": self.observed_value,
            "reason": self.reason,
            "result_hash": self.result_hash,
        }
