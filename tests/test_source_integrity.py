"""Fail-closed reference source time and numeric integrity regressions."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from marketspec.sources import (
    AdapterResult,
    EcbReferenceRateXmlAdapter,
    FailureKind,
    Finality,
    HealthPolicy,
    HealthStatus,
    NwsLatestTemperatureJsonAdapter,
    assess_health,
)
from marketspec.sources.core import SourceIdentity, SourceObservation
from marketspec.sources.reference import _json_schema_fingerprint

NOW = datetime(2026, 11, 11, 15, tzinfo=UTC)
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
NWS_URL = "https://api.weather.gov/stations/KPHL/observations/latest"


def valid_observation() -> SourceObservation:
    return SourceObservation(
        identity=SourceIdentity("example", "measurement", "v1"),
        retrieved_at=NOW - timedelta(minutes=5),
        published_at=NOW - timedelta(minutes=10),
        observed_at=NOW - timedelta(minutes=15),
        value=Decimal("1.25"),
        unit="index",
        provenance="https://example.invalid/fixture",
        finality=Finality.FINAL,
        revision_id="v1",
        revision_pending=False,
        schema_fingerprint="a" * 64,
        raw_evidence_sha256="b" * 64,
    )


class SourceIntegrityTest(unittest.TestCase):
    def test_future_timestamps_never_produce_healthy_receipt(self) -> None:
        old = valid_observation()
        cases = {
            "observed": replace(
                old,
                observed_at=NOW + timedelta(minutes=1),
                published_at=NOW + timedelta(minutes=2),
                retrieved_at=NOW + timedelta(minutes=3),
            ),
            "published": replace(
                old,
                published_at=NOW + timedelta(minutes=1),
                retrieved_at=NOW + timedelta(minutes=2),
            ),
            "retrieved": replace(old, retrieved_at=NOW + timedelta(minutes=1)),
        }
        for label, candidate in cases.items():
            with self.subTest(label=label):
                status = assess_health(
                    AdapterResult(observation=candidate),
                    policy=HealthPolicy(max_age=timedelta(hours=1)),
                    now=NOW,
                )
                self.assertEqual(status, HealthStatus.UNKNOWN)

    def test_direct_nonfinite_or_binary_float_observation_is_invalid(self) -> None:
        old = valid_observation()
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), 1.25):
            with (
                self.subTest(value=str(value)),
                self.assertRaises((TypeError, ValueError)),
            ):
                replace(old, value=value)

    def test_ecb_rejects_nonfinite_source_rate(self) -> None:
        adapter = EcbReferenceRateXmlAdapter("USD")
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                raw = (
                    "<Cube><Cube time='2026-11-11'><Cube currency='USD' "
                    f"rate='{token}'/></Cube></Cube>"
                ).encode()
                result = adapter.parse(raw, retrieved_at=NOW, provenance=ECB_URL)
                self.assertIsNone(result.observation)
                self.assertIsNotNone(result.failure)
                self.assertEqual(result.failure.kind, FailureKind.SEMANTIC)

    def test_nws_rejects_nonfinite_json_temperature(self) -> None:
        adapter = NwsLatestTemperatureJsonAdapter()
        for token in ('"NaN"', '"Infinity"', "NaN", "-Infinity"):
            with self.subTest(token=token):
                raw = (
                    '{"properties":{"timestamp":"2026-11-11T14:00:00Z",'
                    '"temperature":{"unitCode":"wmoUnit:degC","value":' + token + "}}}"
                ).encode("utf-8")
                result = adapter.parse(raw, retrieved_at=NOW, provenance=NWS_URL)
                self.assertIsNone(result.observation)
                self.assertIsNotNone(result.failure)
                self.assertIn(
                    result.failure.kind, (FailureKind.SEMANTIC, FailureKind.PARSE)
                )

    def test_nws_json_decimal_numbers_remain_exact(self) -> None:
        raw = (
            b'{"properties":{"timestamp":"2026-11-11T14:00:00Z",'
            b'"temperature":{"unitCode":"wmoUnit:degC",'
            b'"value":0.123456789012345678901234567890}}}'
        )
        result = NwsLatestTemperatureJsonAdapter().parse(
            raw, retrieved_at=NOW, provenance=NWS_URL
        )
        self.assertIsNone(result.failure)
        self.assertEqual(
            result.observation.value, Decimal("0.123456789012345678901234567890")
        )
        parsed_with_float = json.loads(raw)
        parsed_with_decimal = json.loads(raw, parse_float=Decimal)
        self.assertEqual(
            _json_schema_fingerprint(parsed_with_float),
            _json_schema_fingerprint(parsed_with_decimal),
        )

    def test_impossible_observation_chronology_is_rejected(self) -> None:
        old = valid_observation()
        with self.assertRaises(ValueError):
            replace(old, observed_at=NOW - timedelta(minutes=6))

    def test_ecb_duplicate_quotes_or_dates_fail_closed(self) -> None:
        payloads = {
            "duplicate_currency": (
                b"<Cube><Cube time='2026-11-11'>"
                b"<Cube currency='USD' rate='1.2'/>"
                b"<Cube currency='USD' rate='2.5'/>"
                b"</Cube></Cube>"
            ),
            "multiple_dates": (
                b"<Cube><Cube time='2026-11-10'>"
                b"<Cube currency='USD' rate='1.2'/></Cube>"
                b"<Cube time='2026-11-11'>"
                b"<Cube currency='USD' rate='2.5'/></Cube></Cube>"
            ),
        }
        for name, raw in payloads.items():
            with self.subTest(name=name):
                result = EcbReferenceRateXmlAdapter("USD").parse(
                    raw, retrieved_at=NOW, provenance=ECB_URL
                )
                self.assertIsNone(result.observation)
                self.assertIsNotNone(result.failure)
                self.assertEqual(result.failure.kind, FailureKind.PARSE)

    def test_nws_duplicate_keys_fail_closed(self) -> None:
        raw = (
            b'{"properties":{"timestamp":"2026-11-11T14:00:00Z",'
            b'"temperature":{"value":1.25,"value":10,'
            b'"unitCode":"wmoUnit:degC"}}}'
        )
        result = NwsLatestTemperatureJsonAdapter().parse(
            raw, retrieved_at=NOW, provenance=NWS_URL
        )
        self.assertIsNone(result.observation)
        self.assertIsNotNone(result.failure)
        self.assertEqual(result.failure.kind, FailureKind.PARSE)

    def test_nws_missing_or_invalid_unit_is_not_accepted(self) -> None:
        for bad in (None, 42, "", "   "):
            with self.subTest(unit=bad):
                raw = json.dumps(
                    {
                        "properties": {
                            "timestamp": "2026-11-11T14:00:00Z",
                            "temperature": {"value": 1.25, "unitCode": bad},
                        }
                    }
                ).encode()
                result = NwsLatestTemperatureJsonAdapter().parse(
                    raw, retrieved_at=NOW, provenance=NWS_URL
                )
                self.assertIsNone(result.observation)
                self.assertIsNotNone(result.failure)
                self.assertEqual(result.failure.kind, FailureKind.SEMANTIC)

    def test_excessive_source_nesting_returns_typed_parse_failure(self) -> None:
        depth = 1050
        nws_raw = (
            b'{"properties":{"timestamp":"2026-11-11T14:00:00Z",'
            b'"temperature":{"value":25,"unitCode":"wmoUnit:degC"}},'
            b'"extra":' + b"[" * depth + b"0" + b"]" * depth + b"}"
        )
        ecb_raw = (
            b"<root><Cube time='2026-11-11'>"
            b"<Cube currency='USD' rate='1.2'/></Cube>"
            + b"<extra>" * depth
            + b"</extra>" * depth
            + b"</root>"
        )
        for label, adapter, raw, provenance in (
            ("NWS", NwsLatestTemperatureJsonAdapter(), nws_raw, NWS_URL),
            ("ECB", EcbReferenceRateXmlAdapter(), ecb_raw, ECB_URL),
        ):
            with self.subTest(source=label):
                result = adapter.parse(raw, retrieved_at=NOW, provenance=provenance)
                self.assertIsNone(result.observation)
                self.assertIsNotNone(result.failure)
                self.assertEqual(result.failure.kind, FailureKind.PARSE)

    def test_source_adapters_cap_input_bytes_before_parsing(self) -> None:
        padding = b" " * (8 * 1024 * 1024 + 1)
        for label, adapter, raw, provenance in (
            (
                "NWS",
                NwsLatestTemperatureJsonAdapter(),
                b'{"properties":{"timestamp":"2026-11-11T14:00:00Z",'
                b'"temperature":{"value":25,"unitCode":"wmoUnit:degC"}}}' + padding,
                NWS_URL,
            ),
            (
                "ECB",
                EcbReferenceRateXmlAdapter(),
                b"<root><Cube time='2026-11-11'>"
                b"<Cube currency='USD' rate='1.2'/></Cube></root>" + padding,
                ECB_URL,
            ),
        ):
            with self.subTest(source=label):
                result = adapter.parse(raw, retrieved_at=NOW, provenance=provenance)
                self.assertIsNone(result.observation)
                self.assertIsNotNone(result.failure)
                self.assertEqual(result.failure.kind, FailureKind.PARSE)

    def test_source_observation_decimal_range_matches_evaluator(self) -> None:
        old = valid_observation()
        for text in ("1E+256", "1E-257", "9" * 257):
            with self.subTest(value=text), self.assertRaises(ValueError):
                replace(old, value=Decimal(text))
        self.assertEqual(replace(old, value=Decimal("1E+255")).value, Decimal("1E+255"))

    def test_ecb_and_nws_reject_unsafe_numeric_exponents(self) -> None:
        for text in ("1e1000000000", "1e-1000000000"):
            ecb_raw = (
                "<Cube><Cube time='2026-11-11'>"
                f"<Cube currency='USD' rate='{text}'/></Cube></Cube>"
            ).encode()
            nws_raw = (
                '{"properties":{"timestamp":"2026-11-11T14:00:00Z",'
                '"temperature":{"unitCode":"wmoUnit:degC","value":' + text + "}}}"
            ).encode()
            for label, adapter, raw, url in (
                ("ECB", EcbReferenceRateXmlAdapter(), ecb_raw, ECB_URL),
                ("NWS", NwsLatestTemperatureJsonAdapter(), nws_raw, NWS_URL),
            ):
                with self.subTest(source=label, number=text):
                    result = adapter.parse(raw, retrieved_at=NOW, provenance=url)
                    self.assertIsNone(result.observation)
                    self.assertIsNotNone(result.failure)
                    self.assertEqual(result.failure.kind, FailureKind.SEMANTIC)


if __name__ == "__main__":
    unittest.main()
