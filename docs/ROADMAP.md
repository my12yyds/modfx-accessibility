# Roadmap and evidence

This is a plan, not a statement of completed integrations or adoption.

## Available

- Draft manifest v1, JSON Schema generated from the validator's own vocabulary, and a dependency-free
  Python validator with stable, registered issue codes.
- Single-file, recursive batch and pack-level validation, including duplicate `mod_id` and effect id
  detection across files.
- Eight report formats: text, JSON, Markdown, SARIF 2.1.0, JUnit XML, HTML, CSV and GitHub Actions
  annotations.
- Project configuration (`modfx.config.json`), baselines with counted matching, and `--fix` for the
  repairs that cannot make a declaration less truthful.
- Analysis helpers: coverage statistics, manifest diffing and a canonical formatter.
- Typed Python model, rule registry, shell completion and an environment `doctor`.
- Conservative starter manifest generation, a Chinese hands-on tutorial, unit tests (155) and a CI
  matrix for Python 3.10–3.13.

## Next: validate the vocabulary

- Invite mod authors to describe existing player controls using the draft.
- Collect cases where categories or intensity semantics do not fit.
- Require minimal examples and compatibility notes for vocabulary changes.
- Add regression tests for reproduced bugs before changing behavior.
- Decide whether any current guidance warning should become normative, and whether the severity
  vocabulary needs a third level for informational notes.

## Later: evidence-driven integrations

- Explore loader adapters only after a willing integration partner is identified.
- Consider a pack index that aggregates several manifests with provenance, building on `pack`.
- Discuss version negotiation before changing the v1 contract.
- Revisit a machine-readable changelog for vocabulary changes so downstream tools can react.

## Maintenance and release checklist

1. Triage reproducible bugs and distinguish invalid data from tool crashes.
2. Run unit tests, example validation and package installation checks.
3. Review differences between the schema and Python semantic checks.
4. Update both introductions, integration docs and changelog.
5. Publish a release only after reviewing CI for the exact commit.

No public usage or download metrics are claimed here. Contributions, integrations and metrics should be linked to verifiable public records when available.
