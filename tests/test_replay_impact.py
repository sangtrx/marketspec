"""Evidence replay and CLI acceptance for contract revision reports."""

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

from test_contract_diff import example_contract

from marketspec.cli import main
from marketspec.compiler import compile_contract, parse_evidence
from marketspec.contract_diff import diff_contracts


def evidence_rows() -> list[dict]:
    return [
        {
            "source_id": "synthetic-demo-feed",
            "field": "value",
            "observed_at": "2026-11-01T12:00:00Z",
            "value": "100.5",
            "final": True,
            "revision": 1,
        },
        {
            "source_id": "synthetic-demo-feed",
            "field": "official_final_value",
            "observed_at": "2026-11-01T12:00:00Z",
            "value": "100.5",
            "final": True,
            "revision": 1,
        },
    ]


def invoke(*args: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch.object(sys, "argv", ["marketspec", *args]),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        returncode = main()
    return returncode, stdout.getvalue(), stderr.getvalue()


class ReplayImpactTest(unittest.TestCase):
    def test_outcome_flip_on_same_evidence_and_new_threshold(self) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        after["predicate"]["threshold"] = "101"
        report = diff_contracts(
            compile_contract(before),
            compile_contract(after),
            parse_evidence(evidence_rows()),
        )
        replay = report["replay"]
        self.assertEqual(replay["classification"], "outcome_flip")
        self.assertTrue(replay["status_changed"])
        self.assertTrue(replay["outcome_changed"])
        self.assertEqual(replay["before"]["status"], "yes")
        self.assertEqual(replay["after"]["status"], "no")
        self.assertEqual(
            replay["before"]["evidence_hash"], replay["after"]["evidence_hash"]
        )
        self.assertEqual(replay["evidence_hash"], replay["before"]["evidence_hash"])

    def test_label_only_change_is_not_called_yes_no_flip(self) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        after["outcomes"]["yes"] = "SETTLED_YES"
        report = diff_contracts(
            compile_contract(before),
            compile_contract(after),
            parse_evidence(evidence_rows()),
        )
        replay = report["replay"]
        self.assertEqual(replay["classification"], "outcome_label_changed")
        self.assertFalse(replay["status_changed"])
        self.assertTrue(replay["outcome_changed"])
        self.assertEqual(replay["before"]["status"], "yes")
        self.assertEqual(replay["after"]["status"], "yes")
        self.assertEqual(replay["after"]["outcome"], "SETTLED_YES")

    def test_rule_change_but_fixture_outcome_unchanged(self) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        before["predicate"]["threshold"] = "95"
        after["predicate"]["threshold"] = "99"
        report = diff_contracts(
            compile_contract(before),
            compile_contract(after),
            parse_evidence(evidence_rows()),
        )
        self.assertTrue(report["changed"])
        self.assertTrue(report["settlement_relevant"])
        self.assertEqual(report["replay"]["classification"], "same_outcome_on_fixture")
        self.assertFalse(report["replay"]["outcome_changed"])
        self.assertNotEqual(
            report["replay"]["before"]["result_hash"],
            report["replay"]["after"]["result_hash"],
        )

    def test_replay_does_not_consume_evidence_generator_twice(self) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        after["predicate"]["threshold"] = "101"
        evidence = (item for item in parse_evidence(evidence_rows()))
        report = diff_contracts(
            compile_contract(before), compile_contract(after), evidence
        )
        self.assertEqual(report["replay"]["classification"], "outcome_flip")

    def test_change_to_missing_source_is_explicitly_inconclusive(self) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        after["source"]["id"] = "no-such-feed"
        report = diff_contracts(
            compile_contract(before),
            compile_contract(after),
            parse_evidence(evidence_rows()),
        )
        self.assertEqual(report["replay"]["classification"], "inconclusive")
        self.assertEqual(report["replay"]["after"]["status"], "unknown")
        self.assertEqual(report["replay"]["after"]["reason"], "insufficient_evidence")

    def test_no_change_with_evidence_remains_no_change(self) -> None:
        before = compile_contract(example_contract())
        report = diff_contracts(before, before, parse_evidence(evidence_rows()))
        self.assertFalse(report["changed"])
        self.assertEqual(report["replay"]["classification"], "same_outcome_on_fixture")

    def test_same_status_different_observed_value_is_not_called_outcome_flip(
        self,
    ) -> None:
        before = example_contract()
        after = copy.deepcopy(before)
        after["aggregation"] = "max"
        rows = evidence_rows()
        rows.append(
            {
                "source_id": "synthetic-demo-feed",
                "field": "value",
                "observed_at": "2026-11-01T10:00:00Z",
                "value": "103",
                "final": True,
                "revision": 1,
            }
        )
        report = diff_contracts(
            compile_contract(before), compile_contract(after), parse_evidence(rows)
        )
        self.assertEqual(
            report["replay"]["classification"], "resolution_detail_changed"
        )
        self.assertFalse(report["replay"]["outcome_changed"])

    def test_cli_with_evidence_and_output_path(self) -> None:
        baseline = example_contract()
        variant = copy.deepcopy(baseline)
        variant["predicate"]["threshold"] = "101"
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            a, b, evidence, reportfile = (
                p / "before.json",
                p / "after.json",
                p / "evidence.json",
                p / "report.json",
            )
            a.write_text(json.dumps(baseline), encoding="utf-8")
            b.write_text(json.dumps(variant), encoding="utf-8")
            evidence.write_text(json.dumps(evidence_rows()), encoding="utf-8")
            code, stdout, stderr = invoke(
                "diff",
                str(a),
                str(b),
                "--evidence",
                str(evidence),
                "--output",
                str(reportfile),
            )
            self.assertEqual(code, 1)
            self.assertFalse(stdout)
            self.assertFalse(stderr)
            report = json.loads(reportfile.read_text(encoding="utf-8"))
            self.assertEqual(report["replay"]["classification"], "outcome_flip")

    def test_cli_invalid_evidence_returns_two_and_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            doc, invalid, output = (
                p / "contract.json",
                p / "bad.json",
                p / "report.json",
            )
            doc.write_text(json.dumps(example_contract()), encoding="utf-8")
            invalid.write_text("{not-json", encoding="utf-8")
            code, stdout, stderr = invoke(
                "diff",
                str(doc),
                str(doc),
                "--evidence",
                str(invalid),
                "--output",
                str(output),
            )
            self.assertEqual(code, 2)
            self.assertFalse(stdout)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(stderr)["error"]["code"], "parse_error")

    def test_cli_bad_output_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            doc = p / "contract.json"
            doc.write_text(json.dumps(example_contract()), encoding="utf-8")
            code, stdout, stderr = invoke(
                "diff",
                str(doc),
                str(doc),
                "--output",
                str(p / "missing" / "report.json"),
            )
            self.assertEqual(code, 2)
            self.assertFalse(stdout)
            self.assertEqual(json.loads(stderr)["error"]["code"], "io_error")

    def test_cli_output_never_overwrites_evidence_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = root / "contract.json"
            evidence_path = root / "observations.json"
            contract.write_text(json.dumps(example_contract()), encoding="utf-8")
            original_evidence = json.dumps(evidence_rows())
            evidence_path.write_text(original_evidence, encoding="utf-8")
            code, stdout, stderr = invoke(
                "diff",
                str(contract),
                str(contract),
                "--evidence",
                str(evidence_path),
                "--output",
                str(evidence_path),
            )
            self.assertEqual(code, 2)
            self.assertFalse(stdout)
            self.assertEqual(
                json.loads(stderr)["error"]["code"], "output_input_conflict"
            )
            self.assertEqual(
                evidence_path.read_text(encoding="utf-8"), original_evidence
            )

    def test_input_order_does_not_change_evidence_hash_or_resolution(self) -> None:
        first = example_contract()
        second = copy.deepcopy(first)
        second["predicate"]["threshold"] = "101"
        rows = evidence_rows()
        forward = diff_contracts(
            compile_contract(first), compile_contract(second), parse_evidence(rows)
        )
        backward = diff_contracts(
            compile_contract(first),
            compile_contract(second),
            parse_evidence(list(reversed(rows))),
        )
        self.assertEqual(
            forward["replay"]["evidence_hash"], backward["replay"]["evidence_hash"]
        )
        self.assertEqual(forward["replay"]["before"], backward["replay"]["before"])
        self.assertEqual(forward["replay"]["after"], backward["replay"]["after"])


if __name__ == "__main__":
    unittest.main()
