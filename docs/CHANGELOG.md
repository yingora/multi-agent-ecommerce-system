# Adaptation change log

Baseline: upstream `faf0fd8309c550426f3b2cce057dd4566e209e09`. Original implementation credit is retained in `PROVENANCE.md`.

## Python workflow improvements

- Share one recalled candidate set between ranking and inventory, fail closed on missing/failed availability, and reject unchecked or duplicate IDs.
- Reuse stage methods for direct supervisor and LangGraph, create explicit non-mutating state updates, reset stale outputs and isolate request state.
- Apply hash experiment configuration to distinct rule-based/model ranking behavior; share the engine and honor enabled/bucket settings. Keep Thompson Sampling/copy-style helpers explicitly experimental.
- Enforce agent deadlines across retries/backoff; preserve caller cancellation and sanitize failures. Add request bounds, model shape/ID validation and consistent domain-result serialization.
- Collect all five stage metrics on both API paths; return explicit errors for missing graph and invalid experiment outcomes.
- Default to deterministic offline models, require explicit live mode and a private key, and disable SDK retry duplication.
- Add deterministic socket-blocked regression tests while retaining all five original A/B tests.
- Establish Python 3.12.14, an active dependency manifest, exact uv lock and hash-pinned runtime export.
- Restrict development API binding/CORS, remove fixed storage passwords and unnecessary host ports, make unused storage helpers optional, and use a non-root image with explicit source copies and a build-context allow-list.

## Public-file release preparation

- Curate a Python-only release with the complete application, tests, configuration, container files and focused English documentation. Exclude Git history, private environment files, environments, caches and local audit artifacts.
- Replace the main presentation with an accurate architecture/features/limitations README. Preserve upstream attribution without unsupported performance claims.
- Replace the old broad runtime requirements entry point with a reference to the hash-pinned export.
- Stop returning raw profile analysis/model copy responses in result data. Restrict copy objects to validated `product_id` and `copy` fields, and add two privacy regression tests.
- Document the upstream permission statement and missing formal license without assigning new terms.

No original upstream implementation is reattributed. These are local adaptations; no remote publication is performed by this release preparation.
