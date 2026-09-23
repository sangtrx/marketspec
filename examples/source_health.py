"""Minimal offline MarketSpec settlement-source example."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from marketspec.sources import (
    EcbReferenceRateXmlAdapter,
    HealthPolicy,
    assess_health,
)


raw = Path("tests/fixtures/ecb_eurofxref_2026-09-18.xml").read_bytes()
retrieved_at = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
result = EcbReferenceRateXmlAdapter("USD").parse(
    raw,
    retrieved_at=retrieved_at,
    provenance="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
)
policy = HealthPolicy(max_age=timedelta(days=2))
print(result)
print(assess_health(result, policy=policy, now=retrieved_at))
