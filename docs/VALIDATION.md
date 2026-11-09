# Release validation

Date: 9 November 2026. Baseline: `faf0fd8309c550426f3b2cce057dd4566e209e09`, followed by the documented Python workflow adaptation.

## Executed checks

| Check | Result |
|---|---|
| Frozen offline environment sync from `python/uv.lock` | Passed using Python 3.12.14 and a separate temporary environment |
| `pytest -q -p no:cacheprovider python/tests` | **36 passed in 5.18 seconds**, no failures, skips or expected failures |
| Ruff configured correctness rules | Passed |
| Installed dependency consistency (`uv pip check`) | Passed; 59 installed packages compatible |
| Default Docker Compose configuration | Valid, exit 0 |
| Compose `storage` profile configuration | Valid, exit 0 |
| Python AST / project TOML / local documentation links | Passed |
| Parsed Compose security assertions | Passed: API loopback/offline defaults, no storage host ports, no hardcoded root password |
| Source packaging and credential-pattern review | Passed within the limits in `SECURITY.md` |
| Original local source copies | File content hashes unchanged after release preparation |

Tests execute real compiled LangGraph stages and in-process FastAPI requests, with deterministic offline models and mocked dependencies. They cover all five upstream A/B tests plus inventory failure/empty/partial availability, candidate consistency, duplicate/unknown IDs, stale graph inputs, concurrent request isolation, strategy application, deadlines, retries and cancellation, output validation, API contracts/metrics, experiment validation and seeded/stubbed Thompson Sampling mechanics. Two release-specific tests check removal of raw model analysis and unexpected copy metadata.

The test environment and package cache were kept outside the public folder. Bytecode and pytest cache creation were disabled during validation. No existing development environment or original source copy was modified.

## Reproduce

From the repository root, after the initial dependency sync:

```bash
uv sync --project python --frozen
uv run --project python --frozen --offline pytest -q python/tests
uv run --project python --frozen --offline ruff check python
uv pip check --python python/.venv/bin/python
docker compose config --quiet
docker compose --profile storage config --quiet
```

Ruff is configured for syntax/name correctness rules, not exhaustive style or type checking. The lockfile makes Python dependency resolution reproducible, but image tags are not digest-pinned.

## Not executed or established

No Docker image build/startup, real provider or storage integration, network-bound API smoke test, load/latency benchmark, recommendation-quality study, vulnerability scan or legal clearance assessment was performed. Configuration validation is not proof of a working container deployment. No recommendation uplift, compliance rate, production availability or production-readiness claim follows from these tests.

Redis integration, Milvus retrieval, live inventory, durable experiments, authenticated outcomes and graph checkpointing remain unimplemented or unwired as described in the README. The unresolved upstream formal license notice is documented in `LICENSE_STATUS.md`.
