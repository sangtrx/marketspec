from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from marketspec import __version__
from marketspec.compiler import CompileError, compile_text, parse_evidence_text
from marketspec.evaluator import evaluate


def _format(path: Path) -> str:
    suffix = path.suffix.lower()
    return "json" if suffix == ".json" else "yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marketspec")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    compile_cmd = sub.add_parser("compile", help="compile and canonicalize a contract")
    compile_cmd.add_argument("contract")

    evaluate_cmd = sub.add_parser("evaluate", help="evaluate typed evidence against a contract")
    evaluate_cmd.add_argument("contract")
    evaluate_cmd.add_argument("evidence")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.command:
        build_parser().print_help()
        return 0
    try:
        contract_path = Path(args.contract)
        compiled = compile_text(contract_path.read_text(), format=_format(contract_path))
        if args.command == "compile":
            print(json.dumps({
                "contract": json.loads(compiled.canonical_json),
                "contract_hash": compiled.content_hash,
            }, ensure_ascii=False, sort_keys=True))
            return 0

        evidence_path = Path(args.evidence)
        evidence = parse_evidence_text(evidence_path.read_text(), format=_format(evidence_path))
        print(json.dumps(evaluate(compiled, evidence).as_dict(), ensure_ascii=False, sort_keys=True))
        return 0
    except CompileError as exc:
        print(json.dumps({"error": exc.as_dict()}, sort_keys=True), file=sys.stderr)
        return 2
    except OSError as exc:
        print(json.dumps({"error": {"code": "io_error", "message": str(exc)}}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
