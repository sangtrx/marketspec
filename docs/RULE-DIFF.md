# Contract revision diff — CI for typed settlement rules

MarketSpec compares **two already-typed contracts** identifying the same
market and event. It reports each changed canonical settlement field and
returns a nonzero exit code for changes.

## Two-minute demo — no API key or market access

~~~bash
python -m pip install -e .
marketspec diff examples/rule-before.json examples/rule-after.json
echo "exit=$?"   # 1: settlement-relevant change
marketspec diff examples/rule-before.json examples/rule-before.json
echo "exit=$?"   # 0: no change
~~~

The sample data is **synthetic**, not official Kalshi/Polymarket rules.
A pass does not independently establish that the input is a venue's binding
contract.

## Output

One deterministic JSON line:

- report_version, market_id, event_id
- before_contract_hash and after_contract_hash (canonical SHA-256)
- changed and settlement_relevant
- changes: path-ordered array of {path, area, before, after} with
  decision_boundary, source_binding, observation_window,
  observation_policy, finality_policy and outcome_policy impact categories

All v0.1 compiled fields can influence settlement semantics; there are no
cosmetic-only fields. Canonically equal decimal strings and equivalent
time offsets are considered unchanged.

## CI integration

Check in both a reviewed baseline and a candidate typed contract:

~~~bash
set +e
marketspec diff baseline.json proposed.json > rule-diff.json
status=$?
set -e
case "$status" in
  0) echo "No typed rule changes" ;;
  1) echo "Review settlement-relevant changes in rule-diff.json"; exit 1 ;;
  2) echo "Invalid contract, identity mismatch or I/O failure"; exit 2 ;;
  *) echo "Unexpected failure"; exit "$status" ;;
esac
~~~

Exit codes: 0 unchanged, 1 changed, 2 invalid/error. A different market_id
or event_id is a **different contract**, not a revision; comparison fails.

## Limits and safety

This is an offline, deterministic comparison of **typed** contracts,
not a natural-language rule parser, financial-risk score, payout oracle or
legal interpretation. It does not fetch live venue rules or market data,
prove the identity/authenticity of a source, place orders or handle funds.
An incorrectly transcribed contract can still pass. Retain authentic source
snapshots and obtain independent review before financial use.
