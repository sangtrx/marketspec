"""Safe reference adapters for two materially different official source classes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from json import JSONDecodeError
from typing import Any
from xml.etree import ElementTree

from marketspec.sources.core import (
    AdapterResult,
    FailureKind,
    Finality,
    SourceFailure,
    SourceIdentity,
    SourceObservation,
)

MAX_SOURCE_PAYLOAD_BYTES = 8 * 1024 * 1024


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reject_nonfinite_json_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON number {token!r}")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _json_shape(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        rows = [f"{path}:object"]
        for key in sorted(value):
            rows.extend(_json_shape(value[key], f"{path}.{key}"))
        return rows
    if isinstance(value, list):
        rows = [f"{path}:array"]
        shapes = {tuple(_json_shape(item, f"{path}[]")) for item in value}
        for shape in sorted(shapes):
            rows.extend(shape)
        return rows
    if value is None:
        kind = "null"
    elif isinstance(value, bool):
        kind = "bool"
    elif isinstance(value, (int, float, Decimal)):
        kind = "number"
    elif isinstance(value, str):
        kind = "string"
    else:
        kind = type(value).__name__
    return [f"{path}:{kind}"]


def _json_schema_fingerprint(document: Any) -> str:
    canonical = "\n".join(_json_shape(document)).encode("utf-8")
    return _sha256(canonical)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_shape(element: ElementTree.Element, path: str = "") -> list[str]:
    name = _local_name(element.tag)
    current = f"{path}/{name}" if path else f"/{name}"
    rows = [f"{current}@{','.join(sorted(element.attrib))}"]
    shapes = {tuple(_xml_shape(child, current)) for child in list(element)}
    for shape in sorted(shapes):
        rows.extend(shape)
    return rows


def _xml_schema_fingerprint(root: ElementTree.Element) -> str:
    canonical = "\n".join(_xml_shape(root)).encode("utf-8")
    return _sha256(canonical)


def _failure(
    identity: SourceIdentity,
    *,
    kind: FailureKind,
    provenance: str,
    message: str,
) -> AdapterResult:
    return AdapterResult(
        failure=SourceFailure(
            identity=identity,
            kind=kind,
            provenance=provenance,
            message=message,
        )
    )


def _require_official(
    provenance: str, prefix: str, identity: SourceIdentity
) -> AdapterResult | None:
    if provenance.startswith(prefix):
        return None
    return _failure(
        identity,
        kind=FailureKind.SEMANTIC,
        provenance=provenance,
        message=f"provenance is not an allowed official source: expected prefix {prefix}",
    )


class EcbReferenceRateXmlAdapter:
    """Normalize one ECB EUR reference-rate quote from the official daily XML feed."""

    OFFICIAL_PREFIX = "https://www.ecb.europa.eu/"
    identity = SourceIdentity(
        provider="European Central Bank",
        dataset="Euro foreign exchange reference rates",
        source_version="eurofxref-daily.xml",
    )

    def __init__(self, currency: str = "USD") -> None:
        normalized = currency.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter code")
        self.currency = normalized

    def parse(
        self, raw: bytes, *, retrieved_at: datetime, provenance: str
    ) -> AdapterResult:
        rejected = _require_official(provenance, self.OFFICIAL_PREFIX, self.identity)
        if rejected is not None:
            return rejected
        if len(raw) > MAX_SOURCE_PAYLOAD_BYTES:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message="source payload exceeds 8 MiB",
            )
        try:
            root = ElementTree.fromstring(raw)
        except (ElementTree.ParseError, RecursionError) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message=f"invalid ECB XML: {exc}",
            )

        dated_cubes = [
            element
            for element in root.iter()
            if _local_name(element.tag) == "Cube" and "time" in element.attrib
        ]
        if len(dated_cubes) != 1:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message="ECB XML must contain exactly one dated Cube element",
            )
        dated_cube = dated_cubes[0]
        quotes = [
            child
            for child in dated_cube
            if _local_name(child.tag) == "Cube"
            and child.attrib.get("currency") == self.currency
        ]
        if len(quotes) != 1 or "rate" not in quotes[0].attrib:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message=f"ECB XML must contain exactly one rate for {self.currency}",
            )
        quote = quotes[0]
        try:
            published_date = date.fromisoformat(dated_cube.attrib["time"])
            published_at = datetime.combine(published_date, time.min, tzinfo=UTC)
            value = Decimal(quote.attrib["rate"])
            if not value.is_finite():
                raise ValueError("non-finite ECB rate")
            if value <= 0:
                raise ValueError("ECB reference rate must be positive")
        except (ValueError, InvalidOperation) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message=f"ECB date/rate is invalid: {exc}",
            )

        try:
            schema_fingerprint = _xml_schema_fingerprint(root)
        except RecursionError:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message="ECB XML nesting exceeds supported limit",
            )

        try:
            return AdapterResult(
                observation=SourceObservation(
                    identity=self.identity,
                    retrieved_at=retrieved_at,
                    observed_at=published_at,
                    published_at=published_at,
                    value=value,
                    unit=f"{self.currency}/EUR",
                    provenance=provenance,
                    finality=Finality.FINAL,
                    revision_id=dated_cube.attrib["time"],
                    revision_pending=False,
                    schema_fingerprint=schema_fingerprint,
                    raw_evidence_sha256=_sha256(raw),
                )
            )
        except (TypeError, ValueError) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message=f"invalid ECB observation: {exc}",
            )


class NwsLatestTemperatureJsonAdapter:
    """Normalize one NWS station observation temperature from official api.weather.gov JSON."""

    OFFICIAL_PREFIX = "https://api.weather.gov/"
    identity = SourceIdentity(
        provider="NOAA National Weather Service",
        dataset="Station latest observation temperature",
        source_version="api.weather.gov observation JSON",
    )

    def parse(
        self, raw: bytes, *, retrieved_at: datetime, provenance: str
    ) -> AdapterResult:
        rejected = _require_official(provenance, self.OFFICIAL_PREFIX, self.identity)
        if rejected is not None:
            return rejected
        if len(raw) > MAX_SOURCE_PAYLOAD_BYTES:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message="source payload exceeds 8 MiB",
            )
        try:
            document = json.loads(
                raw.decode("utf-8"),
                parse_float=Decimal,
                parse_constant=_reject_nonfinite_json_constant,
                object_pairs_hook=_unique_json_object,
            )
        except (UnicodeDecodeError, JSONDecodeError, ValueError, RecursionError) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message=f"invalid NWS JSON: {exc}",
            )
        try:
            properties = document["properties"]
            timestamp = properties["timestamp"]
            temperature = properties["temperature"]
            raw_value = temperature["value"]
            unit = temperature["unitCode"]
        except (KeyError, TypeError) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message=f"NWS JSON is missing required observation fields: {exc}",
            )
        if raw_value is None:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message="NWS temperature value is null",
            )
        if not isinstance(unit, str) or not unit.strip():
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message="NWS temperature unitCode must be a non-empty string",
            )
        if unit != "wmoUnit:degC":
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message="NWS temperature unitCode must be wmoUnit:degC (no conversion)",
            )
        try:
            observed_at = datetime.fromisoformat(str(timestamp))
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                raise ValueError("timestamp is naive")
            value = Decimal(str(raw_value))
            if not value.is_finite():
                raise ValueError("non-finite NWS temperature")
        except (ValueError, InvalidOperation) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message=f"NWS timestamp/temperature is invalid: {exc}",
            )

        try:
            schema_fingerprint = _json_schema_fingerprint(document)
        except RecursionError:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message="NWS JSON nesting exceeds supported limit",
            )

        try:
            return AdapterResult(
                observation=SourceObservation(
                    identity=self.identity,
                    retrieved_at=retrieved_at,
                    observed_at=observed_at,
                    published_at=observed_at,
                    value=value,
                    unit=unit,
                    provenance=provenance,
                    finality=Finality.FINAL,
                    revision_id=str(timestamp),
                    revision_pending=False,
                    schema_fingerprint=schema_fingerprint,
                    raw_evidence_sha256=_sha256(raw),
                )
            )
        except (TypeError, ValueError) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message=f"invalid NWS observation: {exc}",
            )
