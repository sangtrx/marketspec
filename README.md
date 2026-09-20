# MarketSpec

**Executable, deterministic event-contract specifications for prediction markets.**

MarketSpec is an experimental open-source toolkit for turning explicit event-market rules into machine-checkable contracts, deterministic evaluation inputs, and reproducible conformance tests.

It is intentionally **not** a trading bot, exchange, custody system, or oracle that invents missing facts.

## Design principles

- Fail closed when settlement semantics are incomplete.
- Treat LLM output as untrusted input until typed and validated.
- Use explicit timezone and revision/finality semantics.
- Use decimal/fixed-point values for settlement thresholds.
- Preserve deterministic canonicalization and replay.
- Make missing, stale, conflicting, and revised evidence first-class states.
- Keep the core useful without a hosted ResolveOps account.

## Status

Early bootstrap. Compiler/runtime work is tracked in `sangtrx/sang-workspace#727`; conformance is tracked in `#728`.

## Local verification

```bash
PYTHONPATH=src python -m marketspec.cli --version
PYTHONPATH=src python -m unittest discover -s tests -v
```

See `docs/ARCHITECTURE.md` and `docs/OSS-BOUNDARY.md`.

## Contributing and security

Start with [CONTRIBUTING.md](CONTRIBUTING.md). External contributors only need this public repository; private maintainer workflow data is not required. Community behavior is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and security reports should follow [SECURITY.md](SECURITY.md).

Internal maintainer workflow authority lives in `sangtrx/sang-workspace`; repository `main` is source truth.

## License

Apache-2.0.
