"""Public deterministic core for executable event-contract specifications."""

from marketspec.compiler import (
    CompileError,
    compile_contract,
    compile_text,
    parse_evidence,
    parse_evidence_text,
)
from marketspec.evaluator import evaluate

__version__ = "0.1.0"

__all__ = [
    "CompileError",
    "__version__",
    "compile_contract",
    "compile_text",
    "evaluate",
    "parse_evidence",
    "parse_evidence_text",
]
