# Roadmap and evidence

This is a plan, not a statement of completed integrations or adoption.

## Available

- Draft manifest v1 and JSON Schema.
- Dependency-free Python validator with stable issue codes.
- Single-file and recursive batch validation; text and JSON reports.
- Optional strict warning policy, unit tests, CI configuration and bilingual introduction.

## Next: validate the vocabulary

- Invite mod authors to describe existing player controls using the draft.
- Collect cases where categories or intensity semantics do not fit.
- Require minimal examples and compatibility notes for vocabulary changes.
- Add regression tests for reproduced bugs before changing behavior.

## Later: evidence-driven integrations

- Explore loader adapters only after a willing integration partner is identified.
- Consider pack-level summaries of actual declarations, with clear provenance.
- Discuss version negotiation before changing the v1 contract.

## Maintenance and release checklist

1. Triage reproducible bugs and distinguish invalid data from tool crashes.
2. Run unit tests, example validation and package installation checks.
3. Review differences between the schema and Python semantic checks.
4. Update both introductions, integration docs and changelog.
5. Publish a release only after reviewing CI for the exact commit.

No public usage or download metrics are claimed here. Contributions, integrations and metrics should be linked to verifiable public records when available.
