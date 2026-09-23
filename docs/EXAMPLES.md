# Reproducible examples

The canonical examples below are not a second source of settlement semantics. They point to cases already pinned in `src/marketspec/conformance/v0.1/golden.json`, so the public docs and the executable conformance corpus share one source of expected hashes.

Run all of them offline with:

```bash
marketspec conformance
```

## 1. Strict equality: explicit tie policy

Golden case: `strict-equality`.

- Rule: `above 100.00`
- Evidence: final value `100.000`
- Tie policy: `no`
- Result: `NO`, reason `threshold_tie`
- Contract hash: `addf0f042625d8078349f94eda9e90c3cc329354bac256daf69b191dc9204eed`
- Evidence hash: `ce892f19bc276aec6cbe6da56d209ff6a6f29ab8086fe8e59b1e76351f6b287f`
- Result hash: `7af7d2c5b5272b440102da43feebea2efed837c4a3f0b5895a016ca7b473dac5`

This demonstrates that equality is never guessed from the operator name: it is part of the explicit contract.

## 2. Out-of-order revisions: select the admitted revision deterministically

Golden case: `revisions-out-of-order`.

The evidence list contains revision 2 before revision 1 and repeats revision 2. With `revision_policy: latest`, MarketSpec deterministically selects the highest revision for the timestamp.

- Result: `YES`, observed value `101`
- Contract hash: `f20fb5a709b6ba53d1d113137a3e4ccb91f4ee4f6c9f10ce9254447fe512b6f9`
- Evidence hash: `ffbad26c464e3e4af52bcaa6abf99a7c3ef028518afa23f6f5fc3a43c1abe473`
- Result hash: `d821cea66c93589eb19b279f5bf434922d17cc60ec419b2cf70b671726f30968`

This demonstrates revision semantics without depending on input ordering.

## 3. Conflicting evidence: fail closed

Golden case: `conflicting-evidence`.

Two final records have the same source, field, timestamp, and revision but different values. MarketSpec does not choose one.

- Result: `INVALID`
- Reason: `conflicting_evidence`
- Contract hash: `d4f2ba496e2fc8b1d50e76c928ebd8bac69299594b93d58e588952b73a1ef83c`
- Evidence hash: `e685d4ee781c1200d04d0427bc20b2bb80af0f205eb12a9d5f3dec79ac9b6140`
- Result hash: `25c5e8ceba2554fb10c64f54a3c6dff8bbad734eae3a4cfdea05d3e6f3273109`

This is a core fail-closed behavior: conflict never silently becomes YES or NO.

## 4. Missing evidence: preserve uncertainty

Golden case: `missing-evidence`.

With no admitted evidence, MarketSpec returns `UNKNOWN` with reason `insufficient_evidence`.

- Contract hash: `2700ddcc2d36b48ab157b45e972a6b69b61dee8fe3d88b00bba9fc86a9ac7a2d`
- Evidence hash: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- Result hash: `3b18924c0a93c3271f296a6e5a355c917e23d1ab8d79abd61ecaaa5bf4672396`

## 5. Public source-adapter fixture

The reference adapter example at `examples/source_health.py` parses the committed ECB fixture at `tests/fixtures/ecb_eurofxref_2026-09-18.xml` without a live network call:

```bash
python examples/source_health.py
```

The adapter layer normalizes public source payloads and reports source health; it does not invent evidence or override the contract evaluator.

## More edge cases

The same corpus also covers decimal canonicalization, observation-window exclusion, DST-fold boundaries, impossible windows, and unsupported schema versions. Read `CONFORMANCE.md` before adding a new golden case: published corpus versions are intended to remain immutable.
