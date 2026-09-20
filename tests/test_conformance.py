import copy
import random
import unittest
from datetime import datetime, timedelta

from marketspec.compiler import CompileError, compile_contract, parse_evidence
from marketspec.conformance_runner import run_corpus
from marketspec.evaluator import evaluate


def contract():
    return {
        "schema_version": "0.1",
        "market_id": "property-market",
        "event_id": "property-event",
        "predicate": {"operator": "above", "threshold": "100.00"},
        "window": {
            "start": "2026-09-19T00:00:00Z",
            "end": "2026-09-20T00:00:00Z",
            "timezone": "UTC",
        },
        "source": {"id": "official-feed", "field": "value"},
        "aggregation": "last",
        "sampling": "all",
        "revision_policy": "latest",
        "tie_behavior": "no",
        "fallback": "unknown",
        "outcomes": {"yes": "YES", "no": "NO", "unknown": "UNKNOWN", "invalid": "INVALID"},
    }


def evidence(value, *, revision=1):
    return {
        "source_id": "official-feed",
        "field": "value",
        "observed_at": "2026-09-19T12:00:00Z",
        "value": str(value),
        "final": True,
        "revision": revision,
    }


class GoldenCorpusTest(unittest.TestCase):
    def test_bundled_corpus(self):
        summary = run_corpus()
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["passed"], summary["cases"])
        self.assertGreaterEqual(summary["cases"], 10)


class PropertyFuzzTest(unittest.TestCase):
    def test_decimal_scale_does_not_change_contract_hash(self):
        hashes = set()
        for threshold in ("100", "100.0", "100.00", "100.000000"):
            raw = contract()
            raw["predicate"]["threshold"] = threshold
            hashes.add(compile_contract(raw).content_hash)
        self.assertEqual(len(hashes), 1)

    def test_randomized_threshold_ordering_invariant(self):
        rng = random.Random(728)
        for _ in range(250):
            threshold = rng.randint(-10000, 10000)
            delta = rng.choice([value for value in range(-25, 26) if value])
            operator = rng.choice(("above", "below"))
            raw = contract()
            raw["predicate"] = {"operator": operator, "threshold": f"{threshold}.000"}
            result = evaluate(compile_contract(raw), parse_evidence([evidence(threshold + delta)]))
            expected = (delta > 0) if operator == "above" else (delta < 0)
            self.assertEqual(result.status, "yes" if expected else "no")

    def test_evidence_order_is_deterministic(self):
        raw = contract()
        compiled = compile_contract(raw)
        source = [
            evidence("99", revision=1),
            evidence("101", revision=2),
            {
                **evidence("103", revision=1),
                "observed_at": "2026-09-19T13:00:00Z",
            },
        ]
        expected = evaluate(compiled, parse_evidence(source))
        rng = random.Random(728)
        for _ in range(100):
            shuffled = copy.deepcopy(source)
            rng.shuffle(shuffled)
            actual = evaluate(compiled, parse_evidence(shuffled))
            self.assertEqual(actual.evidence_hash, expected.evidence_hash)
            self.assertEqual(actual.result_hash, expected.result_hash)

    def test_seeded_time_boundary_invariant(self):
        raw = contract()
        compiled = compile_contract(raw)
        start = datetime.fromisoformat(raw["window"]["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(raw["window"]["end"].replace("Z", "+00:00"))
        rng = random.Random(728)
        offsets = [-1, 0, 1] + [rng.randint(-3600, 3600) for _ in range(247)]

        for boundary in (start, end):
            for offset_seconds in offsets:
                observed_at = boundary + timedelta(seconds=offset_seconds)
                record = evidence("101")
                record["observed_at"] = observed_at.isoformat().replace("+00:00", "Z")
                result = evaluate(compiled, parse_evidence([record]))
                admitted = start <= observed_at <= end
                self.assertEqual(result.status, "yes" if admitted else "unknown")
                self.assertEqual(
                    result.reason,
                    "predicate_evaluated" if admitted else "insufficient_evidence",
                )

    def test_invalid_contracts_fail_closed(self):
        bad_window = contract()
        bad_window["window"]["start"] = bad_window["window"]["end"]
        with self.assertRaises(CompileError) as caught:
            compile_contract(bad_window)
        self.assertEqual(caught.exception.code, "invalid_window")

        future = contract()
        future["schema_version"] = "0.2"
        with self.assertRaises(CompileError) as caught:
            compile_contract(future)
        self.assertEqual(caught.exception.code, "schema_version")


if __name__ == "__main__":
    unittest.main()
