"""Cross-format settlement numeric semantics and bounded rendering regressions."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import random
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from test_contract_diff import example_contract

from marketspec.cli import main
from marketspec.compiler import (
    CompileError,
    compile_contract,
    decimal_text,
    load_document,
    parse_evidence_text,
)
from marketspec.evaluator import evaluate


def record(value: str, *, quoted: bool = True) -> str:
    """Make JSON evidence with exact numeric token or decimal-string value."""
    fixture = {
        "source_id": "synthetic-demo-feed",
        "field": "value",
        "observed_at": "2026-11-01T12:00:00Z",
        "value": "__VALUE__",
        "final": True,
        "revision": 1,
    }
    result = json.dumps([fixture])
    token = json.dumps(value) if quoted else value
    return result.replace('"__VALUE__"', token)


def yaml_record(value: str, *, quoted: bool = False) -> str:
    token = json.dumps(value) if quoted else value
    return (
        "- source_id: synthetic-demo-feed\\n"
        "  field: value\\n"
        "  observed_at: 2026-11-01T12:00:00Z\\n"
        f"  value: {token}\\n"
        "  final: true\\n"
        "  revision: 1\\n"
    ).replace("\\n", "\n")


class StrictNumericYamlTest(unittest.TestCase):
    def test_yaml_legacy_number_literals_fail_closed(self) -> None:
        for text in ("010", "0x10", "1:00", "1_000", "+10"):
            with self.subTest(value=text):
                with self.assertRaises(CompileError) as caught:
                    load_document(f"value: {text}", format="yaml")
                self.assertEqual(caught.exception.code, "decimal_representation")

    def test_explicit_yaml_tags_cannot_bypass_decimal_grammar(self) -> None:
        for text in ("!!int 0x10", "!!int 010", "!!float .nan", "!!float +1.0"):
            with self.subTest(value=text):
                with self.assertRaises(CompileError) as caught:
                    load_document(f"value: {text}", format="yaml")
                self.assertEqual(caught.exception.code, "decimal_representation")

    def test_ambiguous_quoted_evidence_is_rejected(self) -> None:
        for value in ("010", "0x10", "0o10", "1:00", "+1", ".5", "1_000"):
            with self.subTest(value=value):
                with self.assertRaises(CompileError) as caught:
                    parse_evidence_text(yaml_record(value, quoted=True), format="yaml")
                self.assertEqual(caught.exception.code, "decimal_representation")

    def test_normal_yaml_and_json_evidence_hashes_match(self) -> None:
        compiled = compile_contract(example_contract())
        values = ["0", "-0", "1.25", "-1.5", "100.50", "1e2", "1E+2"]
        rng = random.Random(9)
        values.extend(f"{rng.randrange(-1000, 1000)}.25" for _ in range(14))
        for val in values:
            with self.subTest(value=val):
                # The JSON value uses the native number token, not a pre-normalized string.
                left = parse_evidence_text(record(val, quoted=False), format="json")
                right = parse_evidence_text(yaml_record(val), format="yaml")
                self.assertEqual(left, right)
                self.assertEqual(
                    evaluate(compiled, left).as_dict(),
                    evaluate(compiled, right).as_dict(),
                )

    def test_yaml_sexagesimal_revision_does_not_become_sixty(self) -> None:
        text = yaml_record("100").replace("revision: 1", "revision: 1:00")
        with self.assertRaises(CompileError) as caught:
            parse_evidence_text(text, format="yaml")
        self.assertEqual(caught.exception.code, "decimal_representation")

    def test_standard_decimal_integer_and_revision_still_work(self) -> None:
        rows = parse_evidence_text(yaml_record("100"), format="yaml")
        self.assertEqual(rows[0].value, Decimal(100))
        self.assertEqual(rows[0].revision, 1)


class BoundedNumericTest(unittest.TestCase):
    def test_reject_billion_digit_exponents_before_rendering(self) -> None:
        for literal in ("1e1000000000", "1e-1000000000", "0e1000000000"):
            for quoted in (False, True):
                with self.subTest(value=literal, quoted=quoted):
                    with self.assertRaises(CompileError) as caught:
                        parse_evidence_text(
                            record(literal, quoted=quoted), format="json"
                        )
                    self.assertEqual(caught.exception.code, "decimal_range")

    def test_decimal_to_text_defends_direct_decimal_objects(self) -> None:
        for literal in ("1E+100000000", "1E-100000000", "0E+100000000"):
            with self.subTest(value=literal):
                with self.assertRaises(CompileError) as caught:
                    decimal_text(Decimal(literal))
                self.assertEqual(caught.exception.code, "decimal_range")

    def test_boundary_finite_numbers_and_zero_canonicalization(self) -> None:
        self.assertEqual(len(decimal_text(Decimal("1E+255"))), 256)
        self.assertEqual(decimal_text(Decimal("-0.000")), "0")
        self.assertEqual(decimal_text(Decimal("100.000")), "100")
        with self.assertRaises(CompileError) as caught:
            decimal_text(Decimal("1E+256"))
        self.assertEqual(caught.exception.code, "decimal_range")

    def test_excessively_precise_contract_threshold_is_rejected(self) -> None:
        raw = copy.deepcopy(example_contract())
        raw["predicate"]["threshold"] = "9" * 300
        with self.assertRaises(CompileError) as caught:
            compile_contract(raw)
        self.assertIn(
            caught.exception.code, {"decimal_representation", "decimal_range"}
        )

    def test_huge_json_numeric_integer_is_rejected_without_traceback(self) -> None:
        with self.assertRaises(CompileError) as caught:
            load_document("[" + "9" * 300 + "]", format="json")
        self.assertEqual(caught.exception.code, "decimal_range")

    def test_direct_python_integer_over_limit_returns_typed_error(self) -> None:
        row = {
            "source_id": "synthetic-demo-feed",
            "field": "value",
            "observed_at": "2026-11-01T12:00:00Z",
            "value": 10**5000,
            "final": True,
            "revision": 1,
        }
        from marketspec.compiler import parse_evidence

        with self.assertRaises(CompileError) as caught:
            parse_evidence([row])
        self.assertEqual(caught.exception.code, "decimal_range")

    def test_document_over_eight_megabytes_fails_before_parsing(self) -> None:
        with self.assertRaises(CompileError) as caught:
            load_document(" " * (8 * 1024 * 1024 + 1), format="json")
        self.assertEqual(caught.exception.code, "document_too_large")


class PackagingAndCliSafetyTest(unittest.TestCase):
    def test_source_archive_declares_referenced_test_fixtures(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertIn(
            "recursive-include tests/fixtures *.json *.xml",
            (root / "MANIFEST.in").read_text(encoding="utf-8"),
        )
        self.assertTrue(list((root / "tests/fixtures").glob("*.json")))
        self.assertTrue(list((root / "tests/fixtures").glob("*.xml")))

    def test_malformed_yaml_cli_returns_error_not_rule_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary)
            contract = p / "before.json"
            invalid = p / "after.yaml"
            report = p / "report.json"
            contract.write_text(json.dumps(example_contract()), encoding="utf-8")
            invalid.write_text("value: 010\\n".replace("\\n", "\n"), encoding="utf-8")
            report.write_text("prior-run", encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "marketspec",
                        "diff",
                        str(contract),
                        str(invalid),
                        "--output",
                        str(report),
                    ],
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                rc = main()
            self.assertEqual(rc, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn(
                json.loads(stderr.getvalue())["error"]["code"],
                {"decimal_representation", "parse_error"},
            )
            self.assertEqual(report.read_text(encoding="utf-8"), "prior-run")


if __name__ == "__main__":
    unittest.main()
