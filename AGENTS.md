# Agent instructions

- GitHub Issues in `sangtrx/sang-workspace` are the only durable workflow/checkpoint authority.
- This repository's current `main` is source truth.
- Parent project: `sangtrx/sang-workspace#725`.
- Bootstrap authority: `#726`; compiler/runtime: `#727`; conformance: `#728`; launch: `#735`.
- **DO NOT OVERENGINEER.**
- Before source mutation, claim/continue the single 28-minute writer generation with `owner=web` and a bounded exact-Issue scope.
- One active writer per overlapping source scope.
- No GitHub Actions.
- Do not copy proprietary Curren alpha, private datasets, credentials, or private ResolveOps operational history into this public repository.
- LLM assistance may propose structure or edge cases; deterministic typed code remains final authority.
- Fail closed on ambiguous settlement semantics.
