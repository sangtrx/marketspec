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

1. Contract model.
2. Compiler and validation.
3. Deterministic evaluator.
4. Conformance corpus and property/fuzz invariants.
5. Public adapter interfaces/reference fixtures.

Production watchers and operational history belong to private ResolveOps.

## Non-negotiable semantics

- UTC internally; market-facing zones are explicit IANA zones.
- No naive datetimes.
- No binary floating point for settlement thresholds.
- UNKNOWN / INVALID / STALE / CONFLICT never silently become YES/NO.
- Same canonical contract + evidence must replay to the same result.
- AI parsing is optional untrusted input, never settlement authority.
