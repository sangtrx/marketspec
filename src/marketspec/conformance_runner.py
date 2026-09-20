from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from marketspec.compiler import CompileError, compile_contract, parse_evidence
from marketspec.evaluator import evaluate


def _load(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        text = resources.files("marketspec").joinpath("conformance/v0.1/golden.json").read_text(encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict) or value.get("schema_version") != "0.1" or not isinstance(value.get("cases"), list):
        raise ValueError("invalid MarketSpec conformance corpus")
    return value


def run_corpus(path: Path | None = None) -> dict[str, Any]:
    corpus = _load(path)
    failures: list[dict[str, str]] = []
    passed = 0

    for case in corpus["cases"]:
        name = str(case.get("name", "<unnamed>"))
        kind = case.get("kind")
        try:
            if kind == "evaluation":
                compiled = compile_contract(case["contract"])
                result = evaluate(compiled, parse_evidence(case["evidence"])).as_dict()
                if result != case["expected"]:
                    failures.append({"name": name, "reason": "evaluation_mismatch"})
                    continue
            elif kind == "compile_error":
                expected = case["expected_error"]
                try:
                    compile_contract(case["contract"])
                except CompileError as exc:
                    if exc.code != expected["code"] or exc.path != expected["path"]:
                        failures.append({"name": name, "reason": "compile_error_mismatch"})
                        continue
                else:
                    failures.append({"name": name, "reason": "expected_compile_error"})
                    continue
            else:
                failures.append({"name": name, "reason": "unknown_case_kind"})
                continue
        except (CompileError, KeyError, TypeError, ValueError) as exc:
            failures.append({"name": name, "reason": f"runner_error:{type(exc).__name__}"})
            continue
        passed += 1

    return {
        "schema_version": corpus["schema_version"],
        "cases": len(corpus["cases"]),
        "passed": passed,
        "failed": len(failures),
        "failures": failures,
    }
