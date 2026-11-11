"""Deterministic, offline comparison of compiled settlement contracts.

Only already-typed contracts are compared. This deliberately does not parse
natural-language market rules or assert that supplied terms are official.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from marketspec.evaluator import evaluate
from marketspec.models import CompiledContract, Evidence


class ContractComparisonError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


_IMPACT_AREAS = {
    "predicate": "decision_boundary",
    "source": "source_binding",
    "window": "observation_window",
    "aggregation": "observation_policy",
    "sampling": "observation_policy",
    "revision_policy": "finality_policy",
    "tie_behavior": "outcome_policy",
    "fallback": "outcome_policy",
    "outcomes": "outcome_policy",
}


def _diff_values(
    before: Any, after: Any, path: str, changes: list[dict[str, Any]]
) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}/{key}"
            if key not in before:
                changes.append(
                    {
                        "path": child,
                        "area": _area(child),
                        "before": None,
                        "after": after[key],
                    }
                )
            elif key not in after:
                changes.append(
                    {
                        "path": child,
                        "area": _area(child),
                        "before": before[key],
                        "after": None,
                    }
                )
            else:
                _diff_values(before[key], after[key], child, changes)
        return
    if before != after or type(before) is not type(after):
        changes.append(
            {"path": path, "area": _area(path), "before": before, "after": after}
        )


def _area(path: str) -> str:
    group = path.split("/", 2)[1]
    return _IMPACT_AREAS.get(group, "contract_semantics")


def diff_contracts(
    before: CompiledContract,
    after: CompiledContract,
    evidence: Iterable[Evidence] | None = None,
) -> dict[str, Any]:
    """Compare two versions of one contract, optionally replaying shared evidence.

    Input must already be typed, validated and attributable to a reviewed
    source; this function does not verify the authenticity of venue rules.
    A changed contract is always review-relevant, even if a fixture's
    evaluated outcome happens to be the same.
    """
    if before.contract.market_id != after.contract.market_id:
        raise ContractComparisonError(
            "contract_identity_mismatch",
            "market_id differs; these are different market contracts",
        )
    if before.contract.event_id != after.contract.event_id:
        raise ContractComparisonError(
            "contract_identity_mismatch",
            "event_id differs; these are different event contracts",
        )

    before_value = json.loads(before.canonical_json)
    after_value = json.loads(after.canonical_json)
    changes: list[dict[str, Any]] = []
    _diff_values(before_value, after_value, "", changes)
    changed = before.content_hash != after.content_hash
    if changed != bool(changes):
        raise ContractComparisonError(
            "comparison_invariant", "canonical hashes and path diff disagree"
        )
    report: dict[str, Any] = {
        "report_version": "1",
        "market_id": before.contract.market_id,
        "event_id": before.contract.event_id,
        "before_contract_hash": before.content_hash,
        "after_contract_hash": after.content_hash,
        "changed": changed,
        "settlement_relevant": changed,
        "changes": changes,
    }
    if evidence is not None:
        # Snapshot generators once: replay must use *exactly the same*
        # evidence on both versions, not consume an iterator twice.
        supplied = tuple(evidence)
        baseline_result = evaluate(before, supplied)
        candidate_result = evaluate(after, supplied)
        if baseline_result.evidence_hash != candidate_result.evidence_hash:
            raise ContractComparisonError(
                "replay_invariant", "replay evidence differs between contract versions"
            )

        before_decisive = baseline_result.status in {"yes", "no"}
        after_decisive = candidate_result.status in {"yes", "no"}
        outcome_changed = baseline_result.outcome != candidate_result.outcome
        if not before_decisive or not after_decisive:
            classification = "inconclusive"
        elif baseline_result.status != candidate_result.status:
            classification = "outcome_flip"
        elif outcome_changed:
            classification = "outcome_label_changed"
        elif (
            baseline_result.observed_value != candidate_result.observed_value
            or baseline_result.reason != candidate_result.reason
        ):
            classification = "resolution_detail_changed"
        else:
            classification = "same_outcome_on_fixture"

        report["replay"] = {
            "classification": classification,
            "evidence_hash": baseline_result.evidence_hash,
            "status_changed": baseline_result.status != candidate_result.status,
            "outcome_changed": outcome_changed,
            "before": baseline_result.as_dict(),
            "after": candidate_result.as_dict(),
        }

    return report
