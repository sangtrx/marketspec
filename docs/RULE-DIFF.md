# Detect settlement rule changes before an agent relies on them

MarketSpec is an offline, deterministic contract compiler and evaluator for
prediction-market settlement rules. This guide focuses on one practical task:
**comparing two reviewed, typed contracts and replaying identical evidence
through both versions**.

You don't need an exchange account, API credentials or a hosted service.

## Two-minute runnable example

From a fresh checkout:

~~~bash
python -m pip install -e .
marketspec diff examples/rule-before.json examples/rule-after.json
# exit 1: threshold and source binding changed
marketspec diff examples/rule-before.json examples/rule-after.json \
  --evidence examples/rule-replay-evidence.json \
  --output /tmp/marketspec-impact.json
# exit 1: change detected; JSON saved to /tmp/marketspec-impact.json
marketspec diff examples/rule-before.json examples/rule-before.json
# exit 0: same canonical contract
~~~

Every example here uses **synthetic** contracts and observations, not an actual
Polymarket or Kalshi market rule. The input contract author remains responsible
for checking the venue's authoritative rule text.

The combined change in the synthetic example updates the threshold from 100
to 101 and the declared source field from `last_value` to
`official_final_value`. With the included observations, the baseline
evaluates YES and the candidate evaluates NO. This comparison demonstrates
the **combined effect**; it does not causally attribute the outcome flip
to either individual change.

## Machine-readable contract change report

Without replay data:

- `report_version`: `"1"`
- `market_id` and `event_id`: both inputs must identify the same contract
- `before_contract_hash` and `after_contract_hash`: SHA-256 of canonical JSON
- `changed` and `settlement_relevant`: any v0.1 compiled change requires review
- `changes`: sorted path-level changes with before/after values and impact area

With `--evidence`, `replay` additionally includes:

- `evidence_hash`, identical in both evaluations
- exact `before` and `after` evaluator receipts (status, outcome, observed
  value, reason and content hashes)
- `status_changed` and `outcome_changed`
- `classification`:
  - `outcome_flip`: both evaluations are decisive but the logical result
    changes from YES to NO or NO to YES
  - `outcome_label_changed`: both are the same logical result, but the
    output mapping/label changed (for example YES to SETTLED_YES)
  - `same_outcome_on_fixture`: both decisive, same outcome and details
  - `resolution_detail_changed`: both decisive, same outcome but reason or
    observed value changed
  - `inconclusive`: one or both evaluations are UNKNOWN/INVALID, including
    a decisive YES/NO becoming INVALID or cases where the candidate source
    lacks admissible evidence. Always inspect `status_changed` and both
    receipts; an inconclusive classification is never an approval.

A single fixture with the same outcome is **not evidence that a rule change is
safe** across all possible observations. `changed=true` remains the policy
review gate regardless of the replay classification.

The report schema is packaged at
`marketspec/schema/rule-diff-report.v1.schema.json` and accessible via:

~~~python
from importlib import resources

schema = (
    resources.files("marketspec")
    .joinpath("schema/rule-diff-report.v1.schema.json")
    .read_text(encoding="utf-8")
)
~~~

## Exit codes and portable CI

- **0** — compiled contracts canonically equal
- **1** — compiled rules changed and require review
- **2** — malformed contract/evidence, different market/event identity, or I/O error

All normal reports are JSON; errors go to stderr as structured JSON.
With `--output`, an existing regular report file is replaced atomically;
a failed replacement leaves the previous report intact. Existing report
permissions are preserved on POSIX; new reports are private to the owner by
default. **Do not use any existing report when the CLI exits 2:** the report
may come from an earlier run. Input aliases are rejected, and output symlinks
and special files are not supported. These guards do not authenticate the
contract or the destination directory, so choose a trusted output directory.

To create an artifact using any local runner, Jenkins, GitLab CI or a pre-merge script:

~~~bash
MARKETSPEC_REPORT=rule-diff.json sh scripts/check-contract-revision.sh \
  examples/rule-before.json examples/rule-after.json \
  examples/rule-replay-evidence.json
~~~

This project deliberately does **not use GitHub Actions**. The shell
wrapper merely preserves exit codes and writes a JSON artifact; it does not
submit trades or change contract state.

## Agent integration (Python)

~~~python
from marketspec import compile_text, diff_contracts, parse_evidence_text

before = compile_text(before_yaml, format="yaml")
after = compile_text(after_yaml, format="yaml")
evidence = parse_evidence_text(evidence_json, format="json")

report = diff_contracts(before, after, evidence)
requires_review = report["changed"]
if requires_review:
    # Your application must obtain human approval before relying on a
    # revised market contract. Do not auto-approve on one matching fixture.
    pass
~~~

A fully runnable, read-only example lives in
[`examples/agent_preflight.py`](../examples/agent_preflight.py).

## Boundaries

The checker compares **typed contract versions**; it does not interpret legal
terms, ingest market prose, pull authenticated venue APIs, determine trading
profitability or establish official source authenticity. Hashes prove stable
serialization of supplied inputs, not who authored the contract. The offline
evaluator cannot prove the exchange will settle identically. Keep verifiable
rule-source snapshots and perform separate independent review for decisions
that have financial consequences.
