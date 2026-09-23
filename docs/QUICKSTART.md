# 5-minute quickstart

This path uses only the public repository and the local deterministic core. It does not require ResolveOps, a network source, or private maintainer workflow data.

## 1. Install

```bash
git clone https://github.com/sangtrx/marketspec.git
cd marketspec
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
marketspec --version
```

Expected version on the current v0.1 line:

```text
marketspec 0.1.0
```

On Windows, activate with `.venv\Scripts\activate`.

## 2. Create a contract

The example intentionally reuses the versioned `strict-equality` conformance case.

```bash
cat > contract.yaml <<'YAML'
schema_version: "0.1"
market_id: golden
event_id: strict-equality
predicate:
  operator: above
  threshold: "100.00"
window:
  start: 2026-09-19T00:00:00Z
  end: 2026-09-20T00:00:00Z
  timezone: UTC
source:
  id: official-feed
  field: value
aggregation: last
sampling: all
revision_policy: final_only
tie_behavior: no
fallback: unknown
outcomes:
  yes: YES
  no: NO
  unknown: UNKNOWN
  invalid: INVALID
YAML
```

Compile it:

```bash
marketspec compile contract.yaml
```

The stable content identity for this exact contract is:

```text
contract_hash = addf0f042625d8078349f94eda9e90c3cc329354bac256daf69b191dc9204eed
```

## 3. Add typed evidence

```bash
cat > evidence.json <<'JSON'
[
  {
    "source_id": "official-feed",
    "field": "value",
    "observed_at": "2026-09-19T12:00:00Z",
    "value": "100.000",
    "final": true,
    "revision": 1
  }
]
JSON
```

Evaluate:

```bash
marketspec evaluate contract.yaml evidence.json
```

For this strict `above` predicate, equality follows `tie_behavior: no`, so the deterministic result is:

```text
status = no
outcome = NO
observed_value = 100
reason = threshold_tie
evidence_hash = ce892f19bc276aec6cbe6da56d209ff6a6f29ab8086fe8e59b1e76351f6b287f
result_hash = 7af7d2c5b5272b440102da43feebea2efed837c4a3f0b5895a016ca7b473dac5
```

## 4. Reproduce the bundled corpus

```bash
marketspec conformance
```

A successful run exits 0. The corpus at `src/marketspec/conformance/v0.1/golden.json` pins the expected contract/evidence/result identities for the documented cases.

Next: read [EXAMPLES.md](EXAMPLES.md) for revision, conflict, missing-evidence, and source-adapter cases, then [ARCHITECTURE.md](ARCHITECTURE.md) for the semantics behind them.
