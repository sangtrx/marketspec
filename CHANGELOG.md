# Changelog

All notable user-visible changes to MarketSpec are recorded here.

MarketSpec has not yet made a public tagged/package release. Until the first release is cut, changes remain under **Unreleased**.

## [Unreleased]

### Added

- Offline canonical contract revision diff and CI-friendly settlement-change gate (`marketspec diff`).
- Optional before/after settlement replay with the *same evidence*, classification and source receipts.
- Read-only agent preflight and portable shell integration demos with a public report JSON Schema.
- Distribution metadata `marketspec-oss` to avoid an unrelated package's existing PyPI name.
- Synthetic before/after rule examples and deterministic diff regression coverage.
- Initial v0.1 typed contract/compiler/evaluator work.
- Fail-closed parsing of ambiguous YAML numeric forms, bounded decimal magnitude and document size, and cross-format evidence parity tests.
- Bounded UTF-8 CLI file reads across compile, evaluate and diff to prevent unbounded input allocation.
- Fail-closed source health for future-dated or impossible timestamps and nonfinite measurements; reference NWS numeric JSON is parsed as exact decimals.
- Reject ambiguous ECB XML duplicate dated/selected quote records, duplicate NWS JSON keys, and missing or invalid NWS temperature units.
- Bound reference source payloads to 8 MiB and report nested JSON/XML parser/schema errors without uncaught recursion tracebacks.
- Keep source observations within the core 256-digit decimal range; invalid ECB/NWS numeric data produces a typed semantic failure.
- Include referenced test fixtures in the source distribution for fully reproducible offline tests.
- Explicit pre-1.0 compatibility and exact-SHA release policy.
- Package discoverability metadata and project links.

At release time, move the relevant entries into a dated `## [X.Y.Z] - YYYY-MM-DD` section. The release notes and tag must identify the exact independently verified source SHA described in `docs/RELEASING.md`.
