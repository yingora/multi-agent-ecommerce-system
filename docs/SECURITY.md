# Security and privacy review

Scope: the curated Python release files and development configuration. This is a local source/configuration review, not a penetration test, certification or dependency vulnerability audit.

## Reviewed controls

- **Credentials:** the only environment example is `python/.env.example`, with a blank provider key. No private `.env`, provider credential, PEM/private key, database file or credential export is included. The placeholder comparison in the model factory and synthetic strings in error-sanitization tests are not real credentials.
- **External calls:** offline mode constructs synthetic model objects, not provider clients. The default API path does not initialize storage clients. Live mode requires explicit opt-in and rejects missing/placeholder keys; upstream provider URL/model defaults remain unverified. Operator-enabled framework tracing is an external integration too; do not enable it or use real personal data for an offline demo.
- **Logs and results:** application logging records startup/model metadata, agent names, status/timing and exception types rather than raw exception text, prompts or keys. Raw provider profile/copy payloads have been removed from result data. Copy responses retain only validated `product_id` and `copy` fields. Privacy tests verify that unrelated raw metadata does not leak. Parsed profiles, request/user IDs and generated copy are still returned to the caller; generated text is not a comprehensive personal-data redaction system. Server access logging can include request paths/query parameters.
- **Docker build context:** `python/.dockerignore` starts by excluding all files, then allows only application modules and the runtime lock export. Docker COPY instructions explicitly select those files. Examples, `.env`, local keys, tests, caches and virtual environments are not copied by these rules. Never put secrets into application source itself. No actual build was performed.
- **Runtime configuration:** the image declares a non-root user and no reload. Compose binds only the API to loopback, drops API capabilities and sets `no-new-privileges`. The optional storage helpers have no host ports; MySQL generates its root password at initialization rather than using a checked-in password. Such generated credentials may appear in database startup logs; do not share those logs. Storage remains development-only and unverified.
- **Failure handling:** inventory fails closed; request item counts are bounded; agent exceptions are sanitized; asynchronous deadlines include retries/backoff. Deadlines rely on cooperative cancellation.
- **Upload hygiene:** the release excludes Git metadata, environments, caches, private configuration and local machine paths. `.gitignore` excludes common secrets and local artifacts. Ignore rules do not remove files already uploaded; review future additions before sharing them.

## Review results and limits

Filename/content scans for private paths, common token/private-key patterns, credential defaults and excluded artifacts found no actual secret in the intended public files. All remaining credential-like strings were reviewed as blank configuration, placeholder validation, generated-password configuration or synthetic test data. This does not guarantee discovery of every encoded or unknown-format secret.

The API has no authentication, rate limiting or production TLS configuration. Outcome recording has no authenticated event attribution or deduplication. In-memory metrics are unbounded; dependency vulnerability/third-party license review and image digest pinning remain outstanding. Do not expose the service publicly or use real user data without further work.

No paid API, external tracing service, database, container or deployment was run during release validation. Tests block socket connections and use in-process HTTP clients. Optional external integrations and production hardening remain outside the verified scope.
