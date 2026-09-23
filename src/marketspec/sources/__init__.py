"""Public settlement-source adapter SDK and health model."""

from marketspec.sources.core import (
    AdapterResult,
    FailureKind,
    Finality,
    HealthPolicy,
    HealthStatus,
    SourceFailure,
    SourceIdentity,
    SourceObservation,
    assess_health,
    retrieval_failure,
)
from marketspec.sources.reference import (
    EcbReferenceRateXmlAdapter,
    NwsLatestTemperatureJsonAdapter,
)

__all__ = [
    "AdapterResult",
    "EcbReferenceRateXmlAdapter",
    "FailureKind",
    "Finality",
    "HealthPolicy",
    "HealthStatus",
    "NwsLatestTemperatureJsonAdapter",
    "SourceFailure",
    "SourceIdentity",
    "SourceObservation",
    "assess_health",
    "retrieval_failure",
]
