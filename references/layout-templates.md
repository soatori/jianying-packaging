# Relative layout templates

The layout registry is a reusable geometry vocabulary, not a collection of project-specific positions. A template defines a local coordinate frame and named slots. The schema 2.0 packaging adapter resolves the frame from current visible subtitles and applies relative transforms only when the target segment has the required confirmed transform fields. Reopening Jianying is still required to verify rendered bounds and readability.

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

The packaging validator checks slot IDs, references, inheritance, cycles, numeric offsets, fallback policy, and legacy visual verification. Final layouts also require numeric `safe_zone` bounds in normalized canvas coordinates plus current canvas dimensions. Prepare measures every line with the font file and size in the text material, converts measured glyph bounds to the same normalized coordinate space, and fits the planned group inside the safe zone. If font metrics are unavailable or the measured group cannot fit, preparation blocks. A symbolic safe-zone name is review-only.

The adapter leaves existing manual transforms alone unless the plan supplies a layout change or explicit transform override. `layout.pattern: "diagonal_stagger"` may encode per-line diagonal offsets; it keeps rotation at zero. Prepare fits positions by measured widths and emits a deterministic HTML preview. Review the preview and store its reported SHA-256 in the plan before `commit`; a changed source, plan, or candidate requires a new prepare and preview approval. Commit reuses the prepared geometry. The preview describes geometry and timing intent and cannot prove that Jianying retains the effect after reopening.

An `auxiliary_mark` or other declared auxiliary text must target an existing unique topmost text track. A missing track, ambiguous render order, or overlap with an existing segment on that track blocks the write; the adapter never creates the overlay track. Reopening Jianying is still required to verify clipping, opacity, layer order, and animation persistence.


## Animated auxiliary marks and text readability

Static slot geometry does not prove that a mark remains readable while it
animates. For `auxiliary_mark` slots, badges, and decorative symbols, inspect
the rendered group at animation entry, perceptual peak, and exit. Account for
effective scale, rotation, stroke, shadow, glow, opacity, and safe-zone bounds
in each sampled state.

An attached or intentional-overlap relation describes layout intent; it does
not waive readability review. Confirm that the mark does not obscure text
glyphs or essential picture content and that contrast remains adequate while
both elements are visible. If animated bounds or rendered states cannot be
resolved from available evidence, use `manual_review` rather than inferring a
pass from base transforms alone.
