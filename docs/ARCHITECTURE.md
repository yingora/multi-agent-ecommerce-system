# Architecture and behavior

The application exposes a fixed recommendation pipeline through a direct supervisor and a compiled LangGraph graph. Both execute the same asynchronous stage methods in `python/orchestrator/supervisor.py`.

1. Validate request bounds, clear request-owned outputs, generate a request ID and assign the ranking strategy using a shared hash experiment engine.
2. Run profile generation and mock product recall concurrently. Each task returns an agent result; the stage creates a new result dictionary.
3. Pass the recalled products to both ranking and inventory. Ranking uses assigned rules or the configured model. Inventory evaluates stock fields and returns available IDs, alerts and suggested limits.
4. Intersect ranking with positively available, positive-stock canonical candidates. Drop duplicates and unknown IDs. Failed inventory means no availability. Failed ranking may reuse recalled products only through this filter.
5. Generate copy for final products, validate product IDs, mask forbidden words and discard unexpected copy metadata. Return a typed response and record all five agent calls.

Graph initialization resets pre-existing outputs; stages return explicit deltas rather than copies of whole branch snapshots. Nested result dictionaries are recreated. Request state is not persisted, and graph invocation is not a checkpoint/resume interface.

The BaseAgent wrapper applies an overall asynchronous deadline to all attempts and backoff. Generic failures are sanitized and surfaced via `success=false`; inventory failure is handled conservatively. Caller cancellation is not swallowed. SDK retries are disabled for configured live model clients. Cooperative async cancellation cannot interrupt arbitrary blocking code.

Offline models produce fixed synthetic profile fields, parse candidate IDs from the rank prompt and return generic demo copy. The offline mode is a test/demo fixture, not a trained recommender. Live clients are constructed only with explicit mode and key configuration; provider behavior has not been verified.

Experiment mechanics and metrics live in process memory. Hash assignment affects ranking. Thompson Sampling and copy-style assignments remain experimental; outcome writes do not validate exposure or event uniqueness. FeatureStore methods support injected Redis-like clients, but the application does not create or inject one. Milvus and live inventory hooks remain placeholders.

See the README for endpoints/configuration and `VALIDATION.md` for the actual checks performed.
