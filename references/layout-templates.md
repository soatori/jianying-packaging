# Relative layout templates

The layout registry is a reusable geometry vocabulary, not a collection of project-specific positions. A template defines a local coordinate frame and named slots. The schema 2.0 packaging adapter resolves the frame from current visible subtitles and applies relative transforms only when the target segment has the required confirmed transform fields. Reopening Jianying is still required to verify rendered bounds and readability.

## Coordinate frame

- `X0` is the runtime horizontal reference of the ordinary final subtitle near the semantic group.
- `Y0` is the runtime original subtitle baseline.
- Slot offsets are relative deltas in the confirmed project coordinate space.
- A slot may be relative to the group origin or another slot.
- A group may contain any number of slots; two-slot examples are not a limit.

Do not hardcode a canvas height or copy an absolute transform from another timeline. If a legacy absolute template is unavoidable, mark it `legacy_absolute`, require a visual verification record, and use `manual_review` as the fallback.

### Normalization and measured-width conventions

Conventions observed on the current build (verify per project, they are not
layout math):

- `clip.transform` / `material.transform` components are normalized against
  **half** the canvas: `±1.0` spans half the width and half the height, so
  `y_px = y_norm × (canvas_height / 2)`. On 1080×1920, `y = 0.6296` sits about
  604 px from center, i.e. ~353 px from the top. Reading `y` as a fraction of the
  full height places every line in the wrong band.
- Never treat a font-size unit as a pixel width. CJK advance differs per font:
  the engineering 点宋体 (`HelloFont_ID_JianSong_95.ttf`, resource id
  `7080096967543493150`) advances ≈1 em — about 80 px at size 13 — so a size-13,
  12-character line is ~958 px on a 1080-wide canvas and still fits. An earlier
  assumption of ~7.26 px per size unit is systematically too wide and produced
  needless re-lining; measure the actual file instead of reusing any constant.
- With `line_spacing: 0.25` the line pitch is 1.25 em, so a two-line box is
  ≈174 px tall for the font above; box height must be consistent with the same
  em, not guessed.
- Clamp horizontal placement as `|x_norm| + measured_half_width_px / (canvas_width / 2) ≤ 0.78`;
  when a wide line (a scaled number row, for instance) breaks the clamp, shrink
  the offset or split the line — do not let it hang off-screen.
- A single line measured above ~95% of canvas width can be auto-wrapped by
  JianYing, which silently destroys the geometry. Re-measure after any scale
  change, because scaling widens the half-width used in the clamp.
- Previews must draw each frame at the canvas's real pixel dimensions using the
  actual local TTF (PIL or equivalent). A preview built on estimated sizes is not
  evidence; users catch font-size errors in the preview and reasonably ask
  whether the same error will appear in JianYing.

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

## Timeline tracks and simultaneous subtitle lines

A layout slot controls on-screen geometry; a Jianying text-track ID controls the timeline lane and render order. For an approved pair that should appear together, keep both exact strings and hashes. Keep the first segment's start and extend its duration through the second segment's end; preserve the second segment's original start and duration. Set the group range from the first start to the second end, then set the second visual's per-item `start_us` and `duration_us` explicitly so it does not inherit the wider group range. The resulting overlap means the second segment must use a distinct upper text track. Give each text segment its own layout slot so the two lines remain readable. The plan's `same_screen` metadata records this intent; it does not change segment timing or assign tracks by itself.

The packaging adapter can create a target text track from a verified text-track prototype for subtitle copies. Use explicit track IDs and confirm the resulting IDs and render order on read-back. For a final clone, extend the first row with `modify_segment`; relocate the second with an exact-text copy to the upper track and hide its covered original row. This changes timeline placement and duration only; it does not alter subtitle text. Auxiliary text remains restricted to an existing unique topmost text track. Preserve the source timeline.

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

## Video overlay slots

A second video track (picture-in-picture, B-roll, cutaway) is a layout object and
competes with the subtitles for the same screen. Treat it as a slot, not as an
arbitrary placed clip.

| Slot | Position | Typical use | Subtitle interaction |
| --- | --- | --- | --- |
| `corner_pip` | one corner, ≤ 0.35 of canvas width | product close-up while the speaker keeps talking | must not overlap the caption band |
| `full_replace` | covers the frame | cutaway where the speaker is off-screen | captions stay on top, re-check contrast |
| `split` | half frame, speaker on the other half | side-by-side comparison | captions move to the free half or drop to the lower band |
| `insert_band` | horizontal strip | detail shot above or below the caption band | keep a clear gutter, never share the band |

Rules:

1. **Subtitles win the safe zone.** If an overlay would cover the caption band, the
   overlay moves or shrinks — never the text. Priority: caption > overlay > picture.
2. Declare the overlay's rectangle in normalized canvas coordinates and include it
   in the collision check; an overlay that silently overlaps a caption is a layout
   defect, not a style choice.
3. Overlap budget: an overlay may cover at most 60% of the frame and must leave the
   caption band free. Beyond that it is a `full_replace`, which needs the captions
   re-checked against the new background.
4. Entry and exit of an overlay are events: they get their own sound anchor
   (`entry_start`), and they are counted separately from per-row text animations.
5. Transition effects between the main track and an overlay (`transitions`) are
   **not writable** through schema 2.0. Plan the cut; do not plan the transition.

This section defines slots and constraints only. Writing an overlay is an editor
driver operation (`add_overlay` / `clone_asset`) that needs a same-version
prototype, a preview, and a read-back.
