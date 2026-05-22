# SoulArk Memory Core Claim Lifecycle Contract

Claim Lifecycle is the governance layer for long-lived facts.

In v0.1 this contract is intentionally small and is implemented through `fact_slots`.

## Why Claim Lifecycle Exists

Long-term memory becomes unreliable when old facts and new facts are both treated as current truth.

Claim Lifecycle gives Memory Core a minimal rule:

```text
For the same user_id + memory_space + topic + fact_key, only one fact_slot may be active.
```

## v0.1 States

- `active`: the current usable value for a topic/key.
- `superseded`: an older value replaced by a newer active value.

Future states are intentionally not part of the v0.1 main path:

- `needs_review`
- `stale`
- `rejected`
- richer `correction` workflows

## v0.1 Transition

When a new `active` fact slot is written for the same scope and key:

```text
previous active -> superseded
new value       -> active
```

If the incoming update has an older numeric `source_fact_id` than the current active slot, Memory Core keeps the current active slot and returns its id.

This prevents older extraction jobs or delayed background tasks from overwriting a newer fact.

## Read Rules

Default read paths only use `active` slots:

- `get_fact_slot`
- `search_fact_slots`
- normal `search`
- `export`

`superseded` slots are retained for audit/history and can be inspected with `list_fact_slot_versions`.

## Correction Boundary

v0.1 can store correction-like raw material through fields such as `is_correction`, but it does not automatically decide that a correction should replace a stable fact.

That decision belongs to an upper layer or a later Claim Runtime. Memory Core only provides the storage/lifecycle primitive.

## Non-Goals

Claim Lifecycle v0.1 does not provide:

- a public claim editing UI.
- automatic contradiction detection.
- LLM-based fact arbitration.
- multi-step approval workflows.
- enterprise audit policy.

Those can be added later without changing the active/superseded base rule.
