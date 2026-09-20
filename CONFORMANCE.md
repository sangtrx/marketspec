# MarketSpec conformance corpus

MarketSpec v0.1 ships a versioned, offline conformance corpus at `src/marketspec/conformance/v0.1/golden.json`.

Run it with:

```bash
marketspec conformance
```

A third-party implementation can consume the JSON corpus directly. No ResolveOps service, network access, or hosted state is required.

The v0.1 corpus pins expected typed outcomes plus contract, evidence, and result SHA-256 identities for representative evaluation cases. It covers strict equality and inclusive equality via explicit tie policy, decimal-scale normalization, missing/out-of-window evidence, DST-fold boundaries and inclusive window endpoints, duplicate/out-of-order revisions, conflicting evidence, impossible windows, and fail-closed unsupported schema versions.

Property/fuzz tests use a frozen seed and assert invariants rather than guessed examples: decimal scale preserves contract identity, threshold ordering is stable across generated values, and evidence ordering does not change hashes or outcomes.

Golden corpus files are immutable within a published corpus version. Semantic changes require a new version directory; regressions discovered during development should be captured as a new named case in the next unpublished corpus version before release.

Current v0.1 limits are explicit: source freshness beyond the contract observation window belongs to the settlement-source health model, and no forward schema compatibility is promised beyond exact `0.1` acceptance. Unsupported versions fail closed.

**DO NOT OVERENGINEER.**
