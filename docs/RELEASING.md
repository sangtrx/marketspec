# Releasing MarketSpec

**DO NOT OVERENGINEER.** MarketSpec releases are intentionally manual and exact-SHA driven until there is a demonstrated need for more automation.

## Version policy

MarketSpec uses package versions in `MAJOR.MINOR.PATCH` form.

While the project is `0.x`:

- a `0.MINOR.0` release may make incompatible changes to documented Python APIs, CLI behavior, or contract/schema semantics;
- a `0.MINOR.PATCH` release must preserve the documented public behavior of that minor line; an intentional incompatibility requires a minor bump;
- the package version and `marketspec.__version__` must match exactly.

Contract documents carry their own `schema_version`. Package `0.1.x` is expected to continue accepting the documented `schema_version: "0.1"` language. An incompatible contract-language change requires a new schema version and at least a package minor-version bump. Do not silently reinterpret an existing schema version.

The CLI follows the package version. Patch releases must not intentionally rename existing commands or change required arguments for already documented workflows.

## Changelog policy

Keep unreleased user-visible changes under `CHANGELOG.md#Unreleased`. When cutting a release, move the included entries into a dated `[X.Y.Z]` section. Do not create a release section merely because a candidate exists.

Release notes must name the exact source SHA that passed all release gates. A branch name, PR number, diff, or later merge commit is not a substitute for that SHA.

## Release checklist

1. Reread the owning GitHub Issue in `sangtrx/sang-workspace` and current repository source. GitHub Issues are workflow authority; repository source is code truth.
2. Confirm the intended package version, `marketspec.__version__`, changelog entry, license metadata, project URLs, and install metadata all describe the same release.
3. Make all release-prep source changes first, then freeze exactly one candidate SHA. Any later source mutation invalidates code-sensitive receipts and requires a new candidate SHA.
4. On that exact candidate SHA, require all three independent gates:
   - fresh read-only ChatGPT Web review;
   - Alibaba OpenCodeReview read-only packet/review;
   - BigLinux deterministic verification using the accepted MarketSpec profile.
5. Do not use GitHub Actions, the active writer as its own reviewer, or receipts from another SHA as substitutes.
6. Integrate only after every required exact-SHA gate passes. Integration must not be treated as evidence that a different SHA was reviewed.
7. Create the public tag as `vX.Y.Z` pointing to the exact verified candidate SHA, after that SHA is reachable from the integrated history. Record and verify the tag target SHA explicitly.
8. Build/publish only from that tagged source. Package publication is a separate action from tagging; do not claim PyPI availability until the upload has actually succeeded and is independently observable.
9. Record the release/tag SHA and publication evidence in the owning GitHub Issue before marking the release work done.

For a first public release, the minimum provenance record is: version, tag, exact verified source SHA, the three exact-SHA gate receipts, and package-publication evidence if publication occurred.
