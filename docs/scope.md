# SoulArk Memory Core v0.1 Scope

This document is the product and engineering boundary for Memory Core v0.1.

Memory Core is the long-term memory runtime. It is not the companion product, not a workflow platform, and not an agent orchestration layer.

## In Scope

v0.1 keeps one narrow loop stable:

```text
write -> search / date_recall / daily_recall -> evidence -> delete / export
```

Allowed capabilities:

- `write`: persist memory records from an upstream product or agent.
- `search`: retrieve memory records by keyword or text query.
- `date_recall`: retrieve evidence for one target date.
- `daily_recall`: retrieve grouped evidence for one target date.
- `delete`: delete records by id with caller-side filters.
- `export`: export records for user-controlled backup or inspection.
- `evidence`: return traceable evidence for recall results.
- SQLite persistence for local/self-hosted deployment.
- HTTP API for integration from Personal, Work Memory, or other agents.

## Out Of Scope

These belong above Memory Core:

- Chat UX.
- Persona, tone, companionship, or emotional rendering.
- Stable Profile composition.
- Recent State composition.
- Project State prompting.
- PolicyGuard or safety orchestration.
- Ambient / Surprise rendering.
- Workflow builder, executor, skills runtime, or automation.
- Feishu, desktop, web, or other channel connectors.
- Enterprise auth, tenancy, audit, billing, and deployment operations.

## Ownership Boundary

Memory Core may store and return facts, events, and evidence.

Memory Core must not decide how an assistant should sound, when to comfort the user, whether to run business workflow steps, or how to merge memory into an answer. Those are product-layer responsibilities.

## Stability Rule

Any v0.1 change must answer:

```text
Does this improve write, recall, evidence, delete, or export?
```

If not, it should not enter the Memory Core main path.
