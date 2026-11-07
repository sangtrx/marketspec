from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from marketspec.cli import main
from marketspec.compiler import compile_contract, compile_text
from marketspec.contract_diff import ContractComparisonError, diff_contracts


def example_contract() -> dict:
    return {
        "schema_version": "0.1",
        "market_id": "demo-market",
        "event_id": "demo-event",
        "predicate": {"operator": "above", "threshold": "100.00"},
        "window": {
            "start": "2026-11-01T00:00:00Z",
            "end": "2026-11-02T00:00:00Z",
            "timezone": "UTC",
        },
        "source": {"id": "synthetic-demo-feed", "field": "value"},
        "aggregation": "last",
        "sampling": "all",
        "revision_policy": "final_only",
        "tie_behavior": "no",
        "fallback": "unknown",
        "outcomes": {"yes": "YES", "no": "NO", "unknown": "UNKNOWN", "invalid": "INVALID"},
    }


def invoke(*args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch.object(sys, "argv", ["marketspec", *args]):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main()
    return code, stdout.getvalue(), stderr.getvalue()


class ContractDiffTest(unittest.TestCase):
    def test_identical_contract_has_no_drift(self) -> None:
        compiled = compile_contract(example_contract())
        report = diff_contracts(compiled, compiled)
        self.assertFalse(report["changed"])
        self.assertFalse(report["settlement_relevant"])
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["before_contract_hash"], report["after_contract_hash"])

    def test_canonical_equivalence_does_not_trigger_diff(self) -> None:
        first = example_contract()
        second = copy.deepcopy(first)
        second["predicate"]["threshold"] = "100.0000"
        second["window"]["start"] = "2026-11-01T07:00:00+07:00"
        second["window"]["end"] = "2026-11-02T00:00:00+00:00"
        report = diff_contracts(compile_contract(first), compile_contract(second))
        self.assertFalse(report["changed"])
        self.assertEqual(report["changes"], [])

    def test_threshold_source_changes_are_path_sorted(self) -> None:
        first = example_contract()
        second = copy.deepcopy(first)
        second["source"]["field"] = "official_close"
        second["predicate"]["threshold"] = "101"
        report = diff_contracts(compile_contract(first), compile_contract(second))
        self.assertTrue(report["changed"])
        self.assertTrue(report["settlement_relevant"])
        self.assertEqual(
            [change["path"] for change in report["changes"]],
            ["/predicate/threshold", "/source/field"],
        )
        self.assertEqual(
            [change["area"] for change in report["changes"]],
            ["decision_boundary", "source_binding"],
        )
        self.assertEqual(report["changes"][0]["before"], "100")
        self.assertEqual(report["changes"][0]["after"], "101")

    def test_all_settlement_semantics_are_reported(self) -> None:
        variants = [
            ("predicate", "operator", "below", "/predicate/operator", "decision_boundary"),
            ("window", "end", "2026-11-03T00:00:00Z", "/window/end", "observation_window"),
            ("window", "timezone", "Asia/Ho_Chi_Minh", "/window/timezone", "observation_window"),
            ("source", "id", "updated-source", "/source/id", "source_binding"),
            (None, "aggregation", "max", "/aggregation", "observation_policy"),
            (None, "sampling", "latest", "/sampling", "observation_policy"),
            (None, "revision_policy", "latest", "/revision_policy", "finality_policy"),
            (None, "tie_behavior", "insufficient", "/tie_behavior", "outcome_policy"),
            (None, "fallback", "invalid", "/fallback", "outcome_policy"),
            ("outcomes", "yes", "SETTLED_YES", "/outcomes/yes", "outcome_policy"),
        ]
        baseline = example_contract()
        for section, key, value, expected_path, expected_area in variants:
            with self.subTest(path=expected_path):
                changed = copy.deepcopy(baseline)
                target = changed if section is None else changed[section]
                target[key] = value
                report = diff_contracts(compile_contract(baseline), compile_contract(changed))
                self.assertTrue(report["changed"])
                self.assertEqual(len(report["changes"]), 1)
                self.assertEqual(report["changes"][0]["path"], expected_path)
                self.assertEqual(report["changes"][0]["area"], expected_area)

    def test_identity_changes_cannot_masquerade_as_revision(self) -> None:
        baseline = example_contract()
        for field in ("market_id", "event_id"):
            with self.subTest(field=field):
                different = copy.deepcopy(baseline)
                different[field] = "different"
                with self.assertRaises(ContractComparisonError) as error:
                    diff_contracts(compile_contract(baseline), compile_contract(different))
                self.assertEqual(error.exception.code, "contract_identity_mismatch")

    def test_change_order_and_json_are_reproducible(self) -> None:
        baseline = example_contract()
        variant = copy.deepcopy(baseline)
        variant["predicate"]["threshold"] = "102"
        variant["source"]["id"] = "another-feed"
        first = diff_contracts(compile_contract(baseline), compile_contract(variant))
        second = diff_contracts(compile_contract(baseline), compile_contract(variant))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_cli_reports_changes_and_exit_code_one(self) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        after["predicate"]["threshold"] = "101"
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / "before.json"
            new = Path(temp) / "after.json"
            old.write_text(json.dumps(before), encoding="utf-8")
            new.write_text(json.dumps(after), encoding="utf-8")
            code, output, stderr = invoke("diff", str(old), str(new))
        self.assertEqual(code, 1)
        self.assertFalse(stderr)
        report = json.loads(output)
        self.assertTrue(report["changed"])
        self.assertEqual(report["changes"][0]["path"], "/predicate/threshold")

    def test_cli_equal_contracts_return_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "same.json"
            path.write_text(json.dumps(example_contract()), encoding="utf-8")
            code, output, stderr = invoke("diff", str(path), str(path))
        self.assertEqual(code, 0)
        self.assertFalse(stderr)
        self.assertFalse(json.loads(output)["changed"])

    def test_cli_identity_mismatch_returns_two(self) -> None:
        old = example_contract()
        new = copy.deepcopy(old)
        new["event_id"] = "different-event"
        with tempfile.TemporaryDirectory() as temp:
            before = Path(temp) / "old.json"
            after = Path(temp) / "new.json"
            before.write_text(json.dumps(old), encoding="utf-8")
            after.write_text(json.dumps(new), encoding="utf-8")
            code, output, stderr = invoke("diff", str(before), str(after))
        self.assertEqual(code, 2)
        self.assertFalse(output)
        self.assertEqual(json.loads(stderr)["error"]["code"], "contract_identity_mismatch")

    def test_cli_malformed_contract_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bad = Path(temp) / "bad.json"
            good = Path(temp) / "good.json"
            bad.write_text("{bad json", encoding="utf-8")
            good.write_text(json.dumps(example_contract()), encoding="utf-8")
            code, output, stderr = invoke("diff", str(bad), str(good))
        self.assertEqual(code, 2)
        self.assertFalse(output)
        self.assertEqual(json.loads(stderr)["error"]["code"], "parse_error")

    def test_cli_cross_format_round_trip(self) -> None:
        yaml = """
schema_version: "0.1"
market_id: demo-market
event_id: demo-event
predicate: {operator: above, threshold: "100"}
window:
  start: 2026-11-01T00:00:00Z
  end: 2026-11-02T00:00:00Z
  timezone: UTC
source: {id: synthetic-demo-feed, field: value}
aggregation: last
sampling: all
revision_policy: final_only
tie_behavior: no
fallback: unknown
outcomes: {yes: YES, no: NO, unknown: UNKNOWN, invalid: INVALID}
"""
        self.assertEqual(
            compile_text(yaml, format="yaml").content_hash,
            compile_contract(example_contract()).content_hash,
        )
        with tempfile.TemporaryDirectory() as temp:
            yaml_path = Path(temp) / "before.yaml"
            json_path = Path(temp) / "after.json"
            yaml_path.write_text(yaml, encoding="utf-8")
            json_path.write_text(json.dumps(example_contract()), encoding="utf-8")
            code, stdout, stderr = invoke("diff", str(yaml_path), str(json_path))
        self.assertEqual(code, 0)
        self.assertFalse(stderr)
        self.assertFalse(json.loads(stdout)["changed"])


if __name__ == "__main__":
    unittest.main()
