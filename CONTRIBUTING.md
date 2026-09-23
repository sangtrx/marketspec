# Contributing to MarketSpec

Thanks for helping improve MarketSpec. This repository is the complete public contribution surface: external contributors do **not** need access to Sang's private workflow data, ResolveOps internals, or Curren research.

## Local setup

MarketSpec currently targets Python 3.11+.

```bash
git clone https://github.com/sangtrx/marketspec.git
cd marketspec
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
PYTHONPATH=src python -m marketspec.cli --version
PYTHONPATH=src python -m unittest discover -s tests -v
```

On Windows, activate the virtual environment with `.venv\Scripts\activate`.

## Before opening a change

Keep changes small and independently reviewable. For behavior changes, describe the contract/evidence semantics being changed and add or update tests that demonstrate the intended deterministic result.

MarketSpec has a few non-negotiable correctness rules:

- fail closed when contract or evidence semantics are incomplete;
- use explicit timezone-aware datetimes and IANA timezone names;
- do not use binary floating point for settlement thresholds;
- never silently turn UNKNOWN, INVALID, STALE, or CONFLICT into YES/NO;
- the same admitted contract + evidence must replay to the same result;
- treat optional AI/LLM output as untrusted input until it is typed and validated.

Do not include secrets, credentials, private ResolveOps data, proprietary Curren research, or private/internal workflow exports in commits, fixtures, examples, screenshots, or issue reports.

## Tests and deterministic fixtures

Run the repository test suite before opening a pull request:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

When adding or changing fixtures:

- prefer the smallest fixture that reproduces the semantic case;
- keep core tests offline and deterministic;
- record source/provenance notes needed to understand a captured public payload;
- sanitize credentials, personal data, and unrelated fields;
- make timezone, decimal, revision/finality, freshness, and missing/conflicting evidence explicit where relevant;
- avoid silently replacing an existing golden fixture when the semantic expectation changed—explain why the expected result changed.

If a test depends on a captured external response, commit the bounded public fixture needed for replay rather than requiring a live network call during the deterministic test.

## Style and review expectations

There is no requirement to use private maintainer tooling. Follow the style already present in the touched code and keep public interfaces typed and explicit.

A review should be able to answer:

1. What behavior or documentation changed?
2. What public issue or use case motivates it?
3. What tests/fixtures demonstrate the result?
4. Is replay deterministic?
5. Does the change preserve fail-closed behavior and the public/private boundary?

Documentation-only changes should still be internally consistent with the source on the branch they describe.

## Issues and pull requests

Use the repository issue forms when they fit. Bug reports should include a minimal reproducible spec/fixture or enough evidence to reconstruct one safely. Change proposals should state the deterministic acceptance condition, not only the desired UI or prose outcome.

Pull requests should include the commands run and their results. Link a public issue when one exists.

Maintainer workflow may reference `sangtrx/sang-workspace`, but contributors are not expected to read or update that repository to participate here.

## Security reports

Do not publish vulnerability details in a normal issue. Follow [SECURITY.md](SECURITY.md) for the private reporting path and disclosure guidance.

## Community behavior

Participation is also governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
