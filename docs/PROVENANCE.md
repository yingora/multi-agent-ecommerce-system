# Source provenance

Upstream repository: [bcefghj/multi-agent-ecommerce-system](https://github.com/bcefghj/multi-agent-ecommerce-system).

Audited baseline commit: `faf0fd8309c550426f3b2cce057dd4566e209e09`.

The agents, application structure, initial supervisor/graph, mock catalog, experiment helpers, FeatureStore, metrics helper and five original A/B tests originate from that repository. Original authorship is not claimed by this adaptation. Upstream prompts and catalog examples are retained, including Chinese content.

The Python adaptation adds safer candidate/stock handling, non-mutating state updates, explicit strategy selection, enforced asynchronous deadlines, synthetic offline defaults, validation and tests, dependency locks and development container hardening. Release preparation additionally removes raw model-response payloads and unexpected copy metadata. See `CHANGELOG.md` for scope.

Only the Python application and relevant documentation are included in this public-file preparation. Unrelated research and interview/résumé templates are not part of its presentation. No unsupported business or performance metrics are carried into the README.

The upstream MIT permission section is preserved as a short quoted excerpt in `LICENSE_STATUS.md`. No license text or copyright holder has been invented. The original local source copies and historical audits were preserved outside this release folder and are not upload artifacts.
