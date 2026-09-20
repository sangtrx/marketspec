"""Safe reference adapters for two materially different official source classes."""

from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
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


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_shape(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        rows = [f"{path}:object"]
        for key in sorted(value):
            rows.extend(_json_shape(value[key], f"{path}.{key}"))
        return rows
    if isinstance(value, list):
        rows = [f"{path}:array"]
        if value:
            rows.extend(_json_shape(value[0], f"{path}[]"))
        return rows
    if value is None:
        kind = "null"
    elif isinstance(value, bool):
        kind = "bool"
    elif isinstance(value, (int, float)):
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
    for child in list(element):
        rows.extend(_xml_shape(child, current))
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


def _require_official(provenance: str, prefix: str, identity: SourceIdentity) -> AdapterResult | None:
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

    def parse(self, raw: bytes, *, retrieved_at: datetime, provenance: str) -> AdapterResult:
        rejected = _require_official(provenance, self.OFFICIAL_PREFIX, self.identity)
        if rejected is not None:
            return rejected
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as exc:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message=f"invalid ECB XML: {exc}",
            )

        dated_cube = next(
            (
                element
                for element in root.iter()
                if _local_name(element.tag) == "Cube" and "time" in element.attrib
            ),
            None,
        )
        if dated_cube is None:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message="ECB XML has no dated Cube element",
            )
        quote = next(
            (
                child
                for child in dated_cube
                if _local_name(child.tag) == "Cube" and child.attrib.get("currency") == self.currency
            ),
            None,
        )
        if quote is None or "rate" not in quote.attrib:
            return _failure(
                self.identity,
                kind=FailureKind.PARSE,
                provenance=provenance,
                message=f"ECB XML has no rate for {self.currency}",
            )
        try:
            published_date = datetime.strptime(dated_cube.attrib["time"], "%Y-%m-%d").date()
            published_at = datetime.combine(published_date, time.min, tzinfo=timezone.utc)
            value = Decimal(quote.attrib["rate"])
        except (ValueError, InvalidOperation) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message=f"ECB date/rate is invalid: {exc}",
            )

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
                schema_fingerprint=_xml_schema_fingerprint(root),
                raw_evidence_sha256=_sha256(raw),
            )
        )


class NwsLatestTemperatureJsonAdapter:
    """Normalize one NWS station observation temperature from official api.weather.gov JSON."""

    OFFICIAL_PREFIX = "https://api.weather.gov/"
    identity = SourceIdentity(
        provider="NOAA National Weather Service",
        dataset="Station latest observation temperature",
        source_version="api.weather.gov observation JSON",
    )

    def parse(self, raw: bytes, *, retrieved_at: datetime, provenance: str) -> AdapterResult:
        rejected = _require_official(provenance, self.OFFICIAL_PREFIX, self.identity)
        if rejected is not None:
            return rejected
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, JSONDecodeError) as exc:
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
        try:
            observed_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                raise ValueError("timestamp is naive")
            value = Decimal(str(raw_value))
        except (ValueError, InvalidOperation) as exc:
            return _failure(
                self.identity,
                kind=FailureKind.SEMANTIC,
                provenance=provenance,
                message=f"NWS timestamp/temperature is invalid: {exc}",
            )

        return AdapterResult(
            observation=SourceObservation(
                identity=self.identity,
                retrieved_at=retrieved_at,
                observed_at=observed_at,
                published_at=observed_at,
                value=value,
                unit=str(unit),
                provenance=provenance,
                finality=Finality.FINAL,
                revision_id=str(timestamp),
                revision_pending=False,
                schema_fingerprint=_json_schema_fingerprint(document),
                raw_evidence_sha256=_sha256(raw),
            )
        )
