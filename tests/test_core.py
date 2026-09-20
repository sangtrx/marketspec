import json
import unittest
from decimal import ROUND_DOWN, localcontext
from pathlib import Path

from marketspec.compiler import (
    CompileError,
    compile_contract,
    compile_text,
    parse_evidence,
)
from marketspec.evaluator import evaluate


def contract(**updates):
    value = {
        "schema_version": "0.1",
        "market_id": "market-1",
        "event_id": "event-1",
        "predicate": {"operator": "above", "threshold": "100.00"},
        "window": {
            "start": "2026-09-19T00:00:00+00:00",
            "end": "2026-09-20T00:00:00+00:00",
            "timezone": "UTC",
        },
        "source": {"id": "official-feed", "field": "value"},
        "aggregation": "last",
        "sampling": "all",
        "revision_policy": "final_only",
        "tie_behavior": "no",
        "fallback": "unknown",
        "outcomes": {"yes": "YES", "no": "NO", "unknown": "UNKNOWN", "invalid": "INVALID"},
    }
    value.update(updates)
    return value


class CompilerTest(unittest.TestCase):
    def test_canonicalization_and_hash_are_stable(self):
        first = compile_contract(contract())
        second = compile_text(json.dumps(contract()), format="json")
        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.canonical_json, second.canonical_json)
        self.assertIn('"threshold":"100"', first.canonical_json)
        self.assertIn('"start":"2026-09-19T00:00:00.000000Z"', first.canonical_json)

    def test_yaml_and_json_compile_to_same_contract(self):
        yaml_text = """
schema_version: "0.1"
market_id: market-1
event_id: event-1
predicate: {operator: above, threshold: "100.00"}
window:
  start: 2026-09-19T00:00:00+00:00
  end: 2026-09-20T00:00:00+00:00
  timezone: UTC
source: {id: official-feed, field: value}
aggregation: last
sampling: all
revision_policy: final_only
tie_behavior: no
fallback: unknown
outcomes: {yes: YES, no: NO, unknown: UNKNOWN, invalid: INVALID}
"""
        self.assertEqual(
            compile_text(yaml_text, format="yaml").content_hash,
            compile_text(json.dumps(contract()), format="json").content_hash,
        )

    def test_binary_float_is_rejected(self):
        raw = contract()
        raw["predicate"]["threshold"] = 100.0
        with self.assertRaises(CompileError) as caught:
            compile_contract(raw)
        self.assertEqual(caught.exception.code, "binary_float")

    def test_threshold_schema_and_compiler_require_decimal_string(self):
        schema_path = Path(__file__).resolve().parents[1] / "src/marketspec/schema/marketspec.schema.json"
        schema = json.loads(schema_path.read_text())
        threshold_schema = schema["properties"]["predicate"]["properties"]["threshold"]
        self.assertEqual(threshold_schema["type"], "string")
        self.assertIn("pattern", threshold_schema)

        for numeric_threshold in (100, 100.5):
            raw = contract()
            raw["predicate"]["threshold"] = numeric_threshold
            with self.assertRaises(CompileError) as caught:
                compile_text(json.dumps(raw), format="json")
            self.assertEqual(caught.exception.code, "decimal_representation")

        compiled = compile_text(
            json.dumps(contract(predicate={"operator": "above", "threshold": "100.5"})),
            format="json",
        )
        self.assertIn('"threshold":"100.5"', compiled.canonical_json)

    def test_naive_datetime_is_rejected(self):
        raw = contract()
        raw["window"]["start"] = "2026-09-19T00:00:00"
        with self.assertRaises(CompileError) as caught:
            compile_contract(raw)
        self.assertEqual(caught.exception.code, "naive_datetime")

    def test_decimal_canonicalization_is_exact_and_context_independent(self):
        raw = contract(predicate={
            "operator": "above",
            "threshold": "123456789012345678901234567890.1234500",
        })
        baseline = compile_contract(raw)
        with localcontext() as context:
            context.prec = 6
            context.rounding = ROUND_DOWN
            altered = compile_contract(raw)

        self.assertEqual(baseline.canonical_json, altered.canonical_json)
        self.assertEqual(baseline.content_hash, altered.content_hash)
        self.assertIn(
            '"threshold":"123456789012345678901234567890.12345"',
            baseline.canonical_json,
        )


class EvaluatorTest(unittest.TestCase):
    def test_bounded_final_source_observation_replays_identically(self):
        compiled = compile_contract(contract())
        evidence = parse_evidence([
            {
                "source_id": "official-feed",
                "field": "value",
                "observed_at": "2026-09-19T12:00:00+00:00",
                "value": "99",
                "final": False,
                "revision": 1,
            },
            {
                "source_id": "official-feed",
                "field": "value",
                "observed_at": "2026-09-19T12:00:00+00:00",
                "value": "101.0",
                "final": True,
                "revision": 2,
            },
            {
                "source_id": "official-feed",
                "field": "value",
                "observed_at": "2026-09-21T12:00:00+00:00",
                "value": "1000",
                "final": True,
                "revision": 1,
            },
            {
                "source_id": "other-feed",
                "field": "value",
                "observed_at": "2026-09-19T13:00:00+00:00",
                "value": "1000",
                "final": True,
                "revision": 1,
            },
        ])
        first = evaluate(compiled, evidence)
        second = evaluate(compiled, evidence)
        self.assertEqual(first.status, "yes")
        self.assertEqual(first.outcome, "YES")
        self.assertEqual(first.observed_value, "101")
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.evidence_hash, second.evidence_hash)

    def test_tie_and_insufficient_evidence_are_explicit(self):
        raw = contract(tie_behavior="insufficient")
        compiled = compile_contract(raw)
        evidence = parse_evidence([{
            "source_id": "official-feed",
            "field": "value",
            "observed_at": "2026-09-19T12:00:00+00:00",
            "value": "100",
            "final": True,
            "revision": 1,
        }])
        result = evaluate(compiled, evidence)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "threshold_tie")

    def test_mean_is_exact_and_context_independent(self):
        compiled = compile_contract(contract(
            aggregation="mean",
            predicate={"operator": "above", "threshold": "1.5"},
        ))
        evidence = parse_evidence([
            {
                "source_id": "official-feed",
                "field": "value",
                "observed_at": "2026-09-19T12:00:00+00:00",
                "value": "1.111111111111111111111111111111",
                "final": True,
                "revision": 1,
            },
            {
                "source_id": "official-feed",
                "field": "value",
                "observed_at": "2026-09-19T13:00:00+00:00",
                "value": "1.888888888888888888888888888889",
                "final": True,
                "revision": 1,
            },
        ])
        baseline = evaluate(compiled, evidence)
        with localcontext() as context:
            context.prec = 4
            context.rounding = ROUND_DOWN
            altered = evaluate(compiled, evidence)

        self.assertEqual(baseline.result_hash, altered.result_hash)
        self.assertEqual(baseline.observed_value, "1.5")
        self.assertEqual(baseline.status, "no")

    def test_non_terminating_mean_fails_closed(self):
        compiled = compile_contract(contract(
            aggregation="mean",
            predicate={"operator": "above", "threshold": "1"},
        ))
        evidence = parse_evidence([
            {
                "source_id": "official-feed",
                "field": "value",
                "observed_at": f"2026-09-19T{hour:02d}:00:00+00:00",
                "value": value,
                "final": True,
                "revision": 1,
            }
            for hour, value in enumerate(("1", "2", "2"), start=10)
        ])
        result = evaluate(compiled, evidence)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "non_terminating_mean")


if __name__ == "__main__":
    unittest.main()
