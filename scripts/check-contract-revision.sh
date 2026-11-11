#!/bin/sh
# Portable CI gate: local, GitLab, Jenkins, build servers; no GitHub Actions.
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 BEFORE.yaml AFTER.yaml [EVIDENCE.json]" >&2
  exit 2
fi

report="${MARKETSPEC_REPORT:-rule-diff.json}"
if [ "$#" -eq 3 ]; then
  if marketspec diff "$1" "$2" --evidence "$3" --output "$report"; then
    rc=0
  else
    rc=$?
  fi
else
  if marketspec diff "$1" "$2" --output "$report"; then
    rc=0
  else
    rc=$?
  fi
fi

case "$rc" in
  0)
    echo "MarketSpec: no changes to compiled settlement semantics; report=$report"
    exit 0
    ;;
  1)
    echo "MarketSpec: settlement rules changed; operator review required; report=$report" >&2
    exit 1
    ;;
  2)
    echo "MarketSpec: invalid contract, mismatched identity, or I/O failure; any existing report may be stale" >&2
    exit 2
    ;;
  *)
    echo "MarketSpec: unexpected failure (exit $rc)" >&2
    exit "$rc"
    ;;
esac
