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
- Explicit pre-1.0 compatibility and exact-SHA release policy.
- Package discoverability metadata and project links.

At release time, move the relevant entries into a dated `## [X.Y.Z] - YYYY-MM-DD` section. The release notes and tag must identify the exact independently verified source SHA described in `docs/RELEASING.md`.
