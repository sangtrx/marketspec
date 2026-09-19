# MarketSpec

**Executable, deterministic event-contract specifications for prediction markets.**

MarketSpec is an experimental open-source toolkit for turning explicit event-market rules into machine-checkable contracts, deterministic evaluation inputs, and reproducible results.

It is intentionally **not** a trading bot, exchange, custody system, or oracle that invents missing facts.

## v0.1 core

The public core provides:

- a typed event-contract model with explicit market/event identity, source binding, bounded observation window + IANA timezone, sampling/aggregation, revision/finality policy, threshold/tie semantics, fallback behavior, and outcome mapping;
- YAML/JSON compilation into deterministic canonical JSON + SHA-256 content identity;
- typed fail-closed compiler errors, including rejection of naive datetimes and binary floating-point settlement values;
- deterministic evaluation of admitted typed evidence;
- a public JSON Schema at `src/marketspec/schema/marketspec.schema.json`.

A minimal contract:

```yaml
schema_version: "0.1"
market_id: example-market
event_id: example-event
predicate: {operator: above, threshold: "100.0"}
window:
  start: 2026-09-19T00:00:00Z
  end: 2026-09-20T00:00:00Z
  timezone: UTC
source: {id: official-feed, field: value}
aggregation: last
sampling: all
revision_policy: final_only
tie_behavior: no
fallback: unknown
outcomes: {yes: YES, no: NO, unknown: UNKNOWN, invalid: INVALID}
```

## CLI

```bash
python -m pip install -e .
marketspec compile contract.yaml
marketspec evaluate contract.yaml evidence.json
```

Evidence records are typed objects with `source_id`, `field`, timezone-aware `observed_at`, decimal-string/integer `value`, boolean `final`, and non-negative integer `revision`.

## Design principles

- Fail closed when settlement semantics are incomplete.
- Treat LLM output as untrusted input until typed and validated.
- Use explicit timezone and revision/finality semantics.
- Use decimal/fixed-point values for settlement thresholds.
- Preserve deterministic canonicalization and replay.
- Make missing and conflicting evidence explicit rather than silently producing YES/NO.
- Keep the core useful without a hosted ResolveOps account.

## Local verification

```bash
PYTHONPATH=src python -m marketspec.cli --version
PYTHONPATH=src python -m unittest discover -s tests -v
```

See `docs/ARCHITECTURE.md` and `docs/OSS-BOUNDARY.md`.

Internal workflow authority lives in `sangtrx/sang-workspace`; repository `main` is source truth.

## License

Apache-2.0.
