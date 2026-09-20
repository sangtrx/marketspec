## Summary

Describe the smallest user-visible or contributor-visible change.

## Related issue

Link the public issue when one exists.

## Semantics / evidence

- Contract/evidence behavior changed: yes / no
- Fixtures added or changed:
- Deterministic replay impact:
- Public/private boundary impact:

## Verification

List the exact commands run and results, for example:

```text
PYTHONPATH=src python -m unittest discover -s tests -v
```

For behavior changes, include the minimal public fixture/spec that demonstrates the expected deterministic result.

## Checklist

- [ ] I kept the change bounded and independently reviewable.
- [ ] Tests/docs cover the changed behavior.
- [ ] Same admitted contract + evidence still replays deterministically, or I documented why semantics intentionally changed.
- [ ] I did not add secrets, credentials, private ResolveOps data, proprietary Curren research, or private workflow exports.
- [ ] I preserved fail-closed behavior for incomplete/invalid/stale/conflicting evidence where relevant.
- [ ] Security-sensitive details are not disclosed publicly; I used SECURITY.md when needed.
