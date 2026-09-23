# Architecture

```text
explicit contract document
        |
        v
schema + typed AST
        |
        v
compiler / validation
        |
        v
canonical serialization + content identity
        |
        v
deterministic evaluator <--- admitted typed evidence
        |
        v
typed result + reproducible receipt inputs
```

## Layering

1. **Contract model** — names the market/event, observation window, source field, predicate, aggregation, revision/finality policy, tie behavior, fallback, and outcome mapping.
2. **Compiler and validation** — parses YAML/JSON into typed values and rejects ambiguous or unsupported input before evaluation.
3. **Canonical identity** — normalizes semantically equivalent supported values and derives a SHA-256 content identity.
4. **Deterministic evaluator** — admits only evidence matching the contract boundary, applies revision/finality and aggregation rules, then returns a typed result.
5. **Conformance corpus** — pins representative contract/evidence/result hashes plus fail-closed compile errors.
6. **Public source adapters** — normalize bounded public payloads and expose source-health state; they are not settlement authority.

Production watchers and operational history belong to private ResolveOps.

## Contract concepts

### Observation window and timezone

The window is bounded by timezone-aware datetimes and names an IANA timezone. Naive datetimes are rejected. Evidence outside the window is not admitted; boundary behavior is exercised in the conformance corpus, including a DST-fold case.

### Predicate, threshold, and tie behavior

v0.1 predicates use decimal-string thresholds rather than binary floating point. Equality behavior is explicit through `tie_behavior`; callers should not infer inclusive/exclusive semantics from prose.

### Revision and finality

Evidence carries `final` and non-negative `revision` fields. `final_only` and `latest` policies make revision handling part of the contract rather than an implicit property of arrival order. Conflicting values at the same admitted identity fail closed.

### Aggregation and sampling

The contract chooses its aggregation and sampling semantics. Evaluator output is a function of the canonical contract plus admitted typed evidence, not network timing or an LLM interpretation.

### Result states

YES/NO are not the only possible results. Missing evidence can remain `UNKNOWN`; contradictory evidence can become `INVALID`. These states are deliberate and must not be silently coerced into a binary settlement outcome.

## Reproducibility

For a fixed supported implementation, the same canonical contract and admitted evidence produce the same contract, evidence, and result identities. The bundled offline corpus is the public regression surface:

```bash
marketspec conformance
```

See [QUICKSTART.md](QUICKSTART.md) and [EXAMPLES.md](EXAMPLES.md) for concrete hashes pinned by that corpus.

## Current limitations

- MarketSpec v0.1 is pre-1.0 and accepts the documented `schema_version: "0.1"`; unsupported forward schema versions fail closed.
- The core evaluates already typed evidence. It does not prove that a real-world publisher is truthful, available, or legally authoritative.
- Public reference adapters cover bounded source-normalization examples, not every venue/source or production retry policy.
- Source freshness beyond the contract observation window belongs to the source-health/watch layer rather than being guessed by the evaluator.
- Network retrieval, durable watch ownership, alerts, secrets, hosted history, and production operations are outside the public deterministic core.
- Optional AI/LLM parsing is untrusted input until converted into validated typed data; it is never settlement authority.
- Public package availability must be verified separately; repository source alone does not imply a published package.

## Non-negotiable semantics

- UTC internally; market-facing zones are explicit IANA zones.
- No naive datetimes.
- No binary floating point for settlement thresholds.
- UNKNOWN / INVALID / STALE / CONFLICT never silently become YES/NO.
- Same canonical contract + evidence must replay to the same result.
- AI parsing is optional untrusted input, never settlement authority.
