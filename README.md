# MarketSpec

**Catch prediction-market settlement-rule changes before they silently change outcomes.**

MarketSpec is an open-source, offline Python toolkit for trading systems,
market makers, developers and AI agents that rely on event-market contracts.
It compiles typed rules, compares revisions, and replays identical evidence
to show whether a settlement decision changes.

**Why it matters:** a changed threshold, price source, cutoff time or tie
policy may change an outcome even when the market's headline looks identical.

No exchange account, API key, bot execution or hosted service is required.
Contracts and examples in this repository are synthetic or explicitly sourced;
MarketSpec does not invent an official rule from a market headline.

## Try the rule-change demo

From a clone of this repository (Python 3.11+):

~~~bash
python -m pip install -e .
marketspec diff examples/rule-before.json examples/rule-after.json \
  --evidence examples/rule-replay-evidence.json
# exit 1: changed rules; demonstration replay changes YES to NO
~~~

The JSON report contains both contract hashes, changed field paths and a
replay receipt showing the before/after status and supplied evidence hash.
Use [the 2-minute guide](docs/RULE-DIFF.md) for plain JSON, CI integration
and a read-only [AI-agent preflight example](examples/agent_preflight.py).

MarketSpec is not a trading bot, broker, custody system or authoritative
settlement oracle.

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

## Rule revision gate — before deploying a changed market contract

Detect settlement-relevant changes in **typed** market contracts before they
reach a trading agent or market operator. The diff runs offline:

~~~bash
marketspec diff examples/rule-before.json examples/rule-after.json
# exit 1: threshold and official-source-field declaration changed
~~~

The tool reports canonical hashes, exact changed paths and optional
before/after outcome replay; it exits 0 for unchanged contracts, 1 for
settlement-relevant changes, and 2 for invalid input. Examples are
synthetic, not verified live venue rules. See
[the rule diff guide](docs/RULE-DIFF.md).

## CLI

```bash
python -m pip install -e .
marketspec compile contract.yaml
marketspec evaluate contract.yaml evidence.json
marketspec conformance
```

For a fresh clone, follow the [5-minute quickstart](docs/QUICKSTART.md). The [worked examples](docs/EXAMPLES.md) reuse the versioned conformance corpus so expected hashes and fail-closed outcomes stay reproducible.

The conformance command runs the bundled, versioned offline golden corpus. See `CONFORMANCE.md`; the JSON corpus is directly reusable by third-party implementations without ResolveOps.

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
PYTHONPATH=src python -m marketspec.cli conformance
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the contract/evidence model and current limitations, and `docs/OSS-BOUNDARY.md` for the public/private boundary.

## Versioning and releases

MarketSpec is pre-1.0. Compatibility expectations, changelog rules, exact-SHA release gates, and tag provenance are documented in `docs/RELEASING.md`. User-visible changes are recorded in `CHANGELOG.md`.

The intended distribution name is `marketspec-oss` (the name `marketspec`
on PyPI belongs to an unrelated publisher). The import and CLI remain
`marketspec`. **No PyPI upload is claimed** until a public package release
is independently verified.

## Contributing and security

Start with [CONTRIBUTING.md](CONTRIBUTING.md). External contributors only need this public repository; private maintainer workflow data is not required. Community behavior is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and security reports should follow [SECURITY.md](SECURITY.md).

## Support and maintainers

Please open feature requests, reproducible bugs and integration questions in
[this repository's Issues](https://github.com/sangtrx/marketspec/issues).
See [CONTRIBUTING.md](CONTRIBUTING.md) for local tests and fixture conventions.
No private workspace or hosted service is required.

## License

Apache-2.0.
