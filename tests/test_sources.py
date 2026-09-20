import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from marketspec.sources import (
    AdapterResult,
    EcbReferenceRateXmlAdapter,
    FailureKind,
    Finality,
    HealthPolicy,
    HealthStatus,
    NwsLatestTemperatureJsonAdapter,
    assess_health,
    retrieval_failure,
)

FIXTURES = Path(__file__).with_name("fixtures")
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class SourceAdapterTest(unittest.TestCase):
    def test_ecb_xml_normalizes_deterministically(self) -> None:
        raw = (FIXTURES / "ecb_eurofxref_2026-09-18.xml").read_bytes()
        adapter = EcbReferenceRateXmlAdapter("USD")
        first = adapter.parse(
            raw,
            retrieved_at=NOW,
            provenance="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        )
        second = adapter.parse(
            raw,
            retrieved_at=NOW,
            provenance="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        )

        self.assertIsNone(first.failure)
        self.assertEqual(first, second)
        assert first.observation is not None
        self.assertEqual(first.observation.value, Decimal("1.1460"))
        self.assertEqual(first.observation.unit, "USD/EUR")
        self.assertEqual(len(first.observation.raw_evidence_sha256), 64)
        self.assertEqual(len(first.observation.schema_fingerprint), 64)

    def test_nws_json_normalizes_deterministically(self) -> None:
        raw = (FIXTURES / "nws_kphl_observation_2026-09-20T20-30-00Z.json").read_bytes()
        adapter = NwsLatestTemperatureJsonAdapter()
        result = adapter.parse(
            raw,
            retrieved_at=NOW,
            provenance="https://api.weather.gov/stations/KPHL/observations/latest",
        )

        self.assertIsNone(result.failure)
        assert result.observation is not None
        self.assertEqual(result.observation.value, Decimal(26))
        self.assertEqual(result.observation.unit, "wmoUnit:degC")
        self.assertEqual(
            result.observation.observed_at,
            datetime(2026, 9, 20, 20, 30, tzinfo=UTC),
        )

    def test_unofficial_mirror_is_rejected(self) -> None:
        raw = (FIXTURES / "nws_kphl_observation_2026-09-20T20-30-00Z.json").read_bytes()
        result = NwsLatestTemperatureJsonAdapter().parse(
            raw,
            retrieved_at=NOW,
            provenance="https://weather-mirror.example/observation.json",
        )

        self.assertIsNone(result.observation)
        assert result.failure is not None
        self.assertEqual(result.failure.kind, FailureKind.SEMANTIC)

    def test_health_states_cover_outage_drift_revision_conflict_and_staleness(self) -> None:
        raw = (FIXTURES / "nws_kphl_observation_2026-09-20T20-30-00Z.json").read_bytes()
        adapter = NwsLatestTemperatureJsonAdapter()
        good = adapter.parse(
            raw,
            retrieved_at=NOW,
            provenance="https://api.weather.gov/stations/KPHL/observations/latest",
        )
        assert good.observation is not None
        policy = HealthPolicy(
            max_age=timedelta(days=2),
            expected_schema_fingerprint=good.observation.schema_fingerprint,
        )

        self.assertEqual(assess_health(good, policy=policy, now=NOW), HealthStatus.HEALTHY)
        self.assertEqual(
            assess_health(good, policy=policy, now=NOW, conflicting=True),
            HealthStatus.CONFLICT,
        )
        self.assertEqual(
            assess_health(
                retrieval_failure(
                    adapter.identity,
                    provenance="https://api.weather.gov/stations/KPHL/observations/latest",
                    message="timeout",
                ),
                policy=policy,
                now=NOW,
            ),
            HealthStatus.UNAVAILABLE,
        )

        drifted = AdapterResult(
            observation=replace(good.observation, schema_fingerprint="0" * 64)
        )
        self.assertEqual(
            assess_health(drifted, policy=policy, now=NOW),
            HealthStatus.SCHEMA_DRIFT,
        )

        pending = AdapterResult(
            observation=replace(
                good.observation,
                finality=Finality.PRELIMINARY,
                revision_pending=True,
            )
        )
        self.assertEqual(
            assess_health(pending, policy=policy, now=NOW),
            HealthStatus.REVISION_PENDING,
        )

        stale_policy = replace(policy, max_age=timedelta(hours=1))
        self.assertEqual(
            assess_health(good, policy=stale_policy, now=NOW),
            HealthStatus.STALE,
        )

    def test_parse_failure_maps_to_unknown_not_fallback(self) -> None:
        result = NwsLatestTemperatureJsonAdapter().parse(
            b"{not-json",
            retrieved_at=NOW,
            provenance="https://api.weather.gov/stations/KPHL/observations/latest",
        )
        self.assertIsNotNone(result.failure)
        self.assertEqual(
            assess_health(result, policy=HealthPolicy(max_age=timedelta(hours=1)), now=NOW),
            HealthStatus.UNKNOWN,
        )


if __name__ == "__main__":
    unittest.main()
