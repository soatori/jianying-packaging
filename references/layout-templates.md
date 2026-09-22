# Relative layout templates

The layout registry is a reusable geometry vocabulary, not a collection of project-specific positions. A template defines a local coordinate frame and named slots. `jianying-editor` resolves the frame from the current final subtitle reference and converts it to the current Jianying version's stored transform.

## Coordinate frame

- `X0` is the runtime horizontal reference of the ordinary final subtitle near the semantic group.
- `Y0` is the runtime original subtitle baseline.
- Slot offsets are relative deltas in the confirmed project coordinate space.
- A slot may be relative to the group origin or another slot.
- A group may contain any number of slots; two-slot examples are not a limit.

Do not hardcode a canvas height or copy an absolute transform from another timeline. If a legacy absolute template is unavoidable, mark it `legacy_absolute`, require a visual verification record, and use `manual_review` as the fallback.

## Slot contract

Each slot contains:

- a unique `id`;
- `ref_type`: `subtitle_unit` or `auxiliary_mark`;
- a `text_ref`; subtitle-unit references must be declared by the current semantic group, while auxiliary marks must be declared separately by the group;
- `offset.dx` and `offset.dy`;
- optional `relative_to`;
- optional `inherit_transform_from`;
- optional scale, rotation, alignment, and relation labels.

Continuation segments inherit the transform of their source slot. They are not independently positioned from a stale timestamp.

## Base templates

The initial registry provides:

- `center_single`: one main slot at the runtime origin;
- `center_stack`: multiple slots sharing the X axis with relative Y offsets;
- `side_pair`: two slots with independently configurable horizontal and vertical offsets;
- `overlay_replace`: slots intentionally sharing an anchor for replacement/overlay;
- `attached_mark`: a main slot with a subordinate mark attached relative to it;
- `composite_basic`: a composable stack plus attached mark.

Extensions use `extends` and add or override slots and constraints. Examples include multi-level stacks, left-main/right-note, three-part information groups, asymmetric emphasis, and fan-like arrangements. The registry is data-driven; adding a valid extension does not require changing validator code.

Inheritance is resolved from the root parent toward the child. Parent slots are available to child relations; a child slot with the same ID replaces the parent slot, and a new child slot is appended. Parent cycles and self-extension are invalid.

## Validation and execution

The packaging validator checks slot IDs, references, inheritance, cycles, numeric offsets, fallback policy, and legacy visual verification. Runtime execution additionally checks text bounds, safe zones, collision policy, layer order, final subtitle text, and rendered transform fields after read-back.
