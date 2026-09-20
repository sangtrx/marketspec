# Security Policy

MarketSpec is experimental software for machine-checkable event-contract semantics. Security reports that could affect contract correctness, deterministic replay, evidence integrity, source handling, or users of the library are welcome.

## Reporting a vulnerability

**Do not publish exploit details, sensitive payloads, credentials, or a working proof of concept in a normal GitHub issue.**

Preferred private path:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability** and submit the report through GitHub Private Vulnerability Reporting.

If GitHub does not show that private reporting action for this repository, open a public issue titled **Security contact request** containing no vulnerability details. Include only enough information to ask a maintainer for a private channel.

A useful private report includes, when available:

- affected MarketSpec version or exact commit;
- concise impact and affected component;
- minimal reproduction steps;
- a minimized/sanitized contract, evidence fixture, or payload;
- whether the issue is deterministic on replay;
- any relevant environment details.

Do not include secrets, private ResolveOps data, proprietary Curren research, or unrelated personal data.

## Disclosure and response expectations

Please allow maintainers to investigate before publishing technical exploit details. Maintainers may coordinate a fix and disclosure with the reporter when appropriate.

MarketSpec currently provides **no security-response SLA, bounty, embargo duration, or guaranteed support window**. The absence of a response deadline is not a statement about severity.

Before a stable support policy exists, reports should target the current default branch or latest tagged release unless the report explains why an older revision remains materially relevant.

## Project boundary

This policy is the contributor-facing disclosure path. The deeper threat/correctness model and release security gate are maintained separately from this document.

MarketSpec is not a substitute for independent legal, financial, oracle, or settlement review.
