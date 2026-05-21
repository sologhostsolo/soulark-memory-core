# SoulArk Memory Core Evidence Contract

Evidence is the main contract between Memory Core and upper layers.

Memory Core does not only return an answer-like string. It returns records that can be traced, inspected, deleted, exported, or challenged by the caller.

## Evidence Fields

Every evidence item should keep these fields stable:

- `content`: quoted memory content or fact text.
- `record_time`: source timestamp when available.
- `date_text`: date portion used for display or date recall.
- `kind`: evidence source kind, such as `timeline_event`, `bio_fact`, `fact_slot`, or `distillation_material`.
- `source_type`: upstream source type, such as `manual`, `demo`, `raw_message`, or `memory_core`.
- `answer_kind`: semantic kind when available.
- `info_weight`: confidence-like weight clamped from `0.0` to `1.0`.
- `source_id`: upstream id or internal source reference.
- `memory_space`: logical memory namespace.

Extra fields are allowed, but upper layers should not require them unless documented.

## Normalized Recall Status

`memory_core.normalizer.normalize_memory_evidence(...)` maps raw tool results into a product-layer friendly contract:

- `found`: evidence exists and the maximum `info_weight` is at least `0.65`.
- `weak`: evidence or rendered text exists, but confidence is below the found threshold.
- `not_found`: there is no usable evidence, or the result explicitly reports a miss.

Stable normalized fields:

- `tool`
- `status`
- `source`
- `route`
- `answer_kind`
- `time`
- `date`
- `snippet`
- `raw_count`
- `confidence`
- `required_slot`
- `evidence_kind`
- `miss_reason`
- `date_scope`
- `daily_recall`
- `evidence`
- `rendered_reply`

## Evidence Usage Rules

Upper layers should treat evidence as source material, not as finished conversation copy.

Recommended usage:

- Use evidence to decide whether the assistant can answer confidently.
- Show source time and confidence when the user asks for factual recall.
- Ask a clarifying question when status is `not_found` or `weak`.
- Do not promote assistant guesses, summaries, or weak old records into current facts without user confirmation.

## Non-Goals

Memory Core does not decide:

- final assistant tone.
- whether to comfort the user.
- whether to write a correction.
- whether a project direction changed.
- whether a fact should become part of Stable Profile.

Those decisions belong to the product layer or a future Claim Lifecycle layer.
