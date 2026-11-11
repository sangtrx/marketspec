from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from marketspec.models import (
    Aggregation,
    CompiledContract,
    EventContract,
    Evidence,
    Fallback,
    ObservationWindow,
    Operator,
    OutcomeMapping,
    Predicate,
    RevisionPolicy,
    Sampling,
    SourceBinding,
    TieBehavior,
)


class CompileError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} at {path}: {message}")

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class _DecimalLoader(yaml.SafeLoader):
    pass


# Keep inputs bounded before decimal->fixed-point expansion or exact-mean arithmetic.
_MAX_DECIMAL_DIGITS = 256
_MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
_DECIMAL_LITERAL_RE = re.compile(
    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$"
)
_INTEGER_LITERAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)$")


def _bounded_decimal(value: Decimal, path: str) -> Decimal:
    if not value.is_finite():
        raise CompileError("invalid_decimal", path, "decimal must be finite")
    representation = value.as_tuple()
    digits, exponent = representation.digits, representation.exponent
    if (
        len(digits) > _MAX_DECIMAL_DIGITS
        or abs(exponent) > _MAX_DECIMAL_DIGITS
        or len(digits) + max(exponent, 0) > _MAX_DECIMAL_DIGITS
    ):
        raise CompileError("decimal_range", path, "decimal exceeds supported 256-digit range")
    return value


def _parse_decimal_literal(raw: str, path: str) -> Decimal:
    if len(raw) > _MAX_DECIMAL_DIGITS or not _DECIMAL_LITERAL_RE.fullmatch(raw):
        raise CompileError("decimal_representation", path, "expected a bounded base-10 decimal")
    try:
        return _bounded_decimal(Decimal(raw), path)
    except InvalidOperation as exc:
        raise CompileError("invalid_decimal", path, "invalid decimal") from exc


# PyYAML defaults to YAML 1.1 booleans, where yes/no become True/False.
# MarketSpec follows YAML 1.2-style booleans so outcome names remain strings.
_DecimalLoader.yaml_implicit_resolvers = {
    key: list(value) for key, value in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for key, resolvers in list(_DecimalLoader.yaml_implicit_resolvers.items()):
    _DecimalLoader.yaml_implicit_resolvers[key] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
_DecimalLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _yaml_decimal(loader: yaml.SafeLoader, node: yaml.Node) -> Decimal:
    return _parse_decimal_literal(loader.construct_scalar(node), "$")


def _yaml_integer(loader: yaml.SafeLoader, node: yaml.Node) -> int:
    raw = loader.construct_scalar(node)
    if len(raw) > _MAX_DECIMAL_DIGITS or not _INTEGER_LITERAL_RE.fullmatch(raw):
        raise CompileError(
            "decimal_representation",
            "$",
            "YAML integers must be unambiguous base-10 (no octal, hex, or sexagesimal)",
        )
    return int(raw, 10)


def _yaml_timestamp(loader: yaml.SafeLoader, node: yaml.Node) -> str:
    return loader.construct_scalar(node)


_DecimalLoader.add_constructor("tag:yaml.org,2002:float", _yaml_decimal)
_DecimalLoader.add_constructor("tag:yaml.org,2002:int", _yaml_integer)
_DecimalLoader.add_constructor("tag:yaml.org,2002:timestamp", _yaml_timestamp)


def _reject_constant(raw: str) -> None:
    raise CompileError("invalid_number", "$", f"non-finite number {raw!r} is not allowed")


def _json_integer(raw: str) -> int:
    if len(raw) > _MAX_DECIMAL_DIGITS:
        raise CompileError("decimal_range", "$", "integer exceeds supported limit")
    return int(raw, 10)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CompileError("duplicate_key", "$", f"duplicate object key {key!r}")
        result[key] = value
    return result


def _yaml_unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise CompileError("type_error", "$", "YAML mapping keys must be hashable") from exc
        if duplicate:
            raise CompileError("duplicate_key", "$", f"duplicate mapping key {key!r}")
        result[key] = loader.construct_object(value_node, deep=False)
    return result


_DecimalLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _yaml_unique_mapping,
)


def load_document(text: str, *, format: str | None = None) -> Any:
    if len(text.encode("utf-8")) > _MAX_DOCUMENT_BYTES:
        raise CompileError("document_too_large", "$", "document exceeds 8 MiB")
    fmt = (format or ("json" if text.lstrip().startswith(("{", "[")) else "yaml")).lower()
    try:
        if fmt == "json":
            return json.loads(
                text,
                parse_float=lambda raw: _parse_decimal_literal(raw, "$"),
                parse_int=_json_integer,
                parse_constant=_reject_constant,
                object_pairs_hook=_unique_json_object,
            )
        if fmt in {"yaml", "yml"}:
            return yaml.load(text, Loader=_DecimalLoader)
    except CompileError:
        raise
    except (json.JSONDecodeError, yaml.YAMLError, ValueError, RecursionError) as exc:
        raise CompileError("parse_error", "$", str(exc)) from exc
    raise CompileError("format_error", "$", f"unsupported format {fmt!r}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompileError("type_error", path, "expected an object")
    return value


def _shape(value: dict[str, Any], path: str, required: set[str]) -> None:
    if any(not isinstance(key, str) for key in value):
        raise CompileError("type_error", path, "object keys must be strings")
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        raise CompileError("missing_field", path, f"missing required field(s): {', '.join(missing)}")
    if extra:
        raise CompileError("unknown_field", path, f"unknown field(s): {', '.join(extra)}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompileError("type_error", path, "expected a non-empty string")
    return value.strip()


def _enum(enum_type: type, value: Any, path: str):
    raw = _string(value, path)
    try:
        return enum_type(raw)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise CompileError("enum_error", path, f"expected one of: {allowed}") from exc


def _decimal(value: Any, path: str) -> Decimal:
    if isinstance(value, float):
        raise CompileError("binary_float", path, "binary floating-point settlement values are not allowed")
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise CompileError("type_error", path, "expected a decimal string or integer")
    if isinstance(value, str):
        return _parse_decimal_literal(value, path)
    if isinstance(value, int) and (
        value.bit_length() > _MAX_DECIMAL_DIGITS * 4
        or len(str(value)) > _MAX_DECIMAL_DIGITS
    ):
        raise CompileError("decimal_range", path, "decimal exceeds supported limit")
    return _bounded_decimal(Decimal(value), path)

_CONTRACT_DECIMAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")


def _contract_decimal(value: Any, path: str) -> Decimal:
    if isinstance(value, float):
        raise CompileError("binary_float", path, "binary floating-point settlement values are not allowed")
    if not isinstance(value, str) or _CONTRACT_DECIMAL_RE.fullmatch(value) is None:
        raise CompileError(
            "decimal_representation",
            path,
            "expected a decimal string such as '100' or '100.5'",
        )
    return _parse_decimal_literal(value, path)


def _datetime(value: Any, path: str) -> datetime:
    raw = _string(value, path)
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        result = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise CompileError("invalid_datetime", path, "expected ISO-8601 datetime") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CompileError("naive_datetime", path, "datetime must include a UTC offset")
    try:
        return result.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise CompileError("invalid_datetime", path, "datetime out of supported range") from exc


def _timezone(value: Any, path: str) -> str:
    name = _string(value, path)
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise CompileError("invalid_timezone", path, "expected an IANA timezone name") from exc
    return name


def _decimal_text(value: Decimal) -> str:
    _bounded_decimal(value, "$.decimal")
    if value.is_zero():
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"0", "-0"} else text


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_contract_dict(contract: EventContract) -> dict[str, Any]:
    return {
        "aggregation": contract.aggregation.value,
        "event_id": contract.event_id,
        "fallback": contract.fallback.value,
        "market_id": contract.market_id,
        "outcomes": {
            "invalid": contract.outcomes.invalid,
            "no": contract.outcomes.no,
            "unknown": contract.outcomes.unknown,
            "yes": contract.outcomes.yes,
        },
        "predicate": {
            "operator": contract.predicate.operator.value,
            "threshold": _decimal_text(contract.predicate.threshold),
        },
        "revision_policy": contract.revision_policy.value,
        "sampling": contract.sampling.value,
        "schema_version": contract.schema_version,
        "source": {
            "field": contract.source.field,
            "id": contract.source.source_id,
        },
        "tie_behavior": contract.tie_behavior.value,
        "window": {
            "end": _iso(contract.window.end),
            "start": _iso(contract.window.start),
            "timezone": contract.window.timezone,
        },
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_contract(raw: Any) -> CompiledContract:
    root = _mapping(raw, "$")
    required = {
        "schema_version", "market_id", "event_id", "predicate", "window", "source",
        "aggregation", "sampling", "revision_policy", "tie_behavior", "fallback", "outcomes",
    }
    _shape(root, "$", required)
    version = _string(root["schema_version"], "$.schema_version")
    if version != "0.1":
        raise CompileError("schema_version", "$.schema_version", "only schema_version '0.1' is supported")

    predicate_raw = _mapping(root["predicate"], "$.predicate")
    _shape(predicate_raw, "$.predicate", {"operator", "threshold"})
    predicate = Predicate(
        operator=_enum(Operator, predicate_raw["operator"], "$.predicate.operator"),
        threshold=_contract_decimal(predicate_raw["threshold"], "$.predicate.threshold"),
    )

    window_raw = _mapping(root["window"], "$.window")
    _shape(window_raw, "$.window", {"start", "end", "timezone"})
    start = _datetime(window_raw["start"], "$.window.start")
    end = _datetime(window_raw["end"], "$.window.end")
    if start >= end:
        raise CompileError("invalid_window", "$.window", "start must be before end")
    window = ObservationWindow(start=start, end=end, timezone=_timezone(window_raw["timezone"], "$.window.timezone"))

    source_raw = _mapping(root["source"], "$.source")
    _shape(source_raw, "$.source", {"id", "field"})
    source = SourceBinding(
        source_id=_string(source_raw["id"], "$.source.id"),
        field=_string(source_raw["field"], "$.source.field"),
    )

    outcomes_raw = _mapping(root["outcomes"], "$.outcomes")
    _shape(outcomes_raw, "$.outcomes", {"yes", "no", "unknown", "invalid"})
    outcomes = OutcomeMapping(
        yes=_string(outcomes_raw["yes"], "$.outcomes.yes"),
        no=_string(outcomes_raw["no"], "$.outcomes.no"),
        unknown=_string(outcomes_raw["unknown"], "$.outcomes.unknown"),
        invalid=_string(outcomes_raw["invalid"], "$.outcomes.invalid"),
    )

    contract = EventContract(
        schema_version=version,
        market_id=_string(root["market_id"], "$.market_id"),
        event_id=_string(root["event_id"], "$.event_id"),
        predicate=predicate,
        window=window,
        source=source,
        aggregation=_enum(Aggregation, root["aggregation"], "$.aggregation"),
        sampling=_enum(Sampling, root["sampling"], "$.sampling"),
        revision_policy=_enum(RevisionPolicy, root["revision_policy"], "$.revision_policy"),
        tie_behavior=_enum(TieBehavior, root["tie_behavior"], "$.tie_behavior"),
        fallback=_enum(Fallback, root["fallback"], "$.fallback"),
        outcomes=outcomes,
    )
    canonical = canonical_json(canonical_contract_dict(contract))
    return CompiledContract(contract=contract, canonical_json=canonical, content_hash=content_hash(canonical))


def compile_text(text: str, *, format: str | None = None) -> CompiledContract:
    return compile_contract(load_document(text, format=format))


def parse_evidence(raw: Any) -> tuple[Evidence, ...]:
    values = raw.get("evidence") if isinstance(raw, dict) and set(raw) == {"evidence"} else raw
    if not isinstance(values, list):
        raise CompileError("type_error", "$.evidence", "expected a list of evidence records")
    records: list[Evidence] = []
    required = {"source_id", "field", "observed_at", "value", "final", "revision"}
    for index, item in enumerate(values):
        path = f"$.evidence[{index}]"
        record = _mapping(item, path)
        _shape(record, path, required)
        final = record["final"]
        revision = record["revision"]
        if not isinstance(final, bool):
            raise CompileError("type_error", f"{path}.final", "expected boolean")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise CompileError("type_error", f"{path}.revision", "expected non-negative integer")
        records.append(Evidence(
            source_id=_string(record["source_id"], f"{path}.source_id"),
            field=_string(record["field"], f"{path}.field"),
            observed_at=_datetime(record["observed_at"], f"{path}.observed_at"),
            value=_decimal(record["value"], f"{path}.value"),
            final=final,
            revision=revision,
        ))
    return tuple(records)


def parse_evidence_text(text: str, *, format: str | None = None) -> tuple[Evidence, ...]:
    return parse_evidence(load_document(text, format=format))


def decimal_text(value: Decimal) -> str:
    return _decimal_text(value)


def iso_utc(value: datetime) -> str:
    return _iso(value)
