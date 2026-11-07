"""An agent-facing preflight guard that never places or recommends trades.

Usage from a checkout with MarketSpec installed:
    python examples/agent_preflight.py
"""

from __future__ import annotations

import json
from pathlib import Path

from marketspec import compile_text, diff_contracts, parse_evidence_text

ROOT = Path(__file__).resolve().parent


def main() -> int:
    before = compile_text(
        (ROOT / "rule-before.json").read_text(encoding="utf-8"), format="json"
    )
    after = compile_text(
        (ROOT / "rule-after.json").read_text(encoding="utf-8"), format="json"
    )
    evidence = parse_evidence_text(
        (ROOT / "rule-replay-evidence.json").read_text(encoding="utf-8"),
        format="json",
    )
    report = diff_contracts(before, after, evidence=evidence)
    print(
        json.dumps(
            {
                "safe_to_auto_approve": not report["changed"],
                "changed_paths": [row["path"] for row in report["changes"]],
                "fixture_classification": report["replay"]["classification"],
                "before_outcome": report["replay"]["before"]["outcome"],
                "after_outcome": report["replay"]["after"]["outcome"],
                "operator_review_required": report["changed"],
            },
            sort_keys=True,
        )
    )
    # A changed contract always requires review. Same fixture outcome does
    # not override typed policy drift.
    return 1 if report["changed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
