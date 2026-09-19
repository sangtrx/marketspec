from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from typing import Iterable

from marketspec.compiler import canonical_json, decimal_text, iso_utc
from marketspec.models import (
    Aggregation,
    CompiledContract,
    EvaluationResult,
    Evidence,
    Fallback,
    Operator,
    RevisionPolicy,
    Sampling,
    TieBehavior,
)


def _evidence_dict(item: Evidence) -> dict[str, object]:
    return {
        "field": item.field,
        "final": item.final,
        "observed_at": iso_utc(item.observed_at),
        "revision": item.revision,
        "source_id": item.source_id,
        "value": decimal_text(item.value),
    }


def _hash_evidence(evidence: Iterable[Evidence]) -> str:
    normalized = sorted(
        (_evidence_dict(item) for item in evidence),
        key=lambda item: (
            str(item["source_id"]), str(item["field"]), str(item["observed_at"]),
            int(item["revision"]), str(item["value"]), bool(item["final"]),
        ),
    )
    return sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def _result(
    compiled: CompiledContract,
    evidence_hash: str,
    status: str,
    observed_value: Decimal | None,
    reason: str,
) -> EvaluationResult:
    outcome = compiled.contract.outcomes.for_status(status)
    value_text = None if observed_value is None else decimal_text(observed_value)
    payload = {
        "contract_hash": compiled.content_hash,
        "evidence_hash": evidence_hash,
        "observed_value": value_text,
        "outcome": outcome,
        "reason": reason,
        "status": status,
    }
    result_hash = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return EvaluationResult(
        contract_hash=compiled.content_hash,
        evidence_hash=evidence_hash,
        status=status,
        outcome=outcome,
        observed_value=value_text,
        reason=reason,
        result_hash=result_hash,
    )


def _aggregate(values: list[Evidence], aggregation: Aggregation) -> Decimal:
    if aggregation is Aggregation.LAST:
        return max(values, key=lambda item: (item.observed_at, item.revision)).value
    decimals = [item.value for item in values]
    if aggregation is Aggregation.MIN:
        return min(decimals)
    if aggregation is Aggregation.MAX:
        return max(decimals)
    if aggregation is Aggregation.MEAN:
        return sum(decimals, Decimal(0)) / Decimal(len(decimals))
    raise AssertionError(f"unsupported aggregation: {aggregation}")


def evaluate(compiled: CompiledContract, evidence: Iterable[Evidence]) -> EvaluationResult:
    supplied = tuple(evidence)
    evidence_hash = _hash_evidence(supplied)
    contract = compiled.contract

    admitted = [
        item for item in supplied
        if item.source_id == contract.source.source_id
        and item.field == contract.source.field
        and contract.window.start <= item.observed_at <= contract.window.end
        and (contract.revision_policy is not RevisionPolicy.FINAL_ONLY or item.final)
    ]

    latest_by_observation: dict[object, Evidence] = {}
    for item in sorted(admitted, key=lambda value: (value.observed_at, value.revision)):
        key = item.observed_at
        previous = latest_by_observation.get(key)
        if previous is not None and previous.revision == item.revision and (
            previous.value != item.value or previous.final != item.final
        ):
            return _result(compiled, evidence_hash, "invalid", None, "conflicting_evidence")
        if previous is None or item.revision >= previous.revision:
            latest_by_observation[key] = item

    admitted = sorted(latest_by_observation.values(), key=lambda item: (item.observed_at, item.revision))
    if contract.sampling is Sampling.LATEST and admitted:
        admitted = [admitted[-1]]

    if not admitted:
        status = "unknown" if contract.fallback is Fallback.UNKNOWN else "invalid"
        return _result(compiled, evidence_hash, status, None, "insufficient_evidence")

    observed = _aggregate(admitted, contract.aggregation)
    threshold = contract.predicate.threshold
    if observed == threshold:
        if contract.tie_behavior is TieBehavior.INSUFFICIENT:
            status = "unknown" if contract.fallback is Fallback.UNKNOWN else "invalid"
            return _result(compiled, evidence_hash, status, observed, "threshold_tie")
        status = "yes" if contract.tie_behavior is TieBehavior.YES else "no"
        return _result(compiled, evidence_hash, status, observed, "threshold_tie")

    if contract.predicate.operator is Operator.ABOVE:
        status = "yes" if observed > threshold else "no"
    else:
        status = "yes" if observed < threshold else "no"
    return _result(compiled, evidence_hash, status, observed, "predicate_evaluated")
