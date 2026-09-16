---
name: jianying-packaging
description: Use when packaging or polishing an already content-stable Jianying Pro / 剪映 timeline — flower text (花字), upper-track emphasis (上轨强调), templates, animation, transitions, or sound effects (加音效/卡点音效). Requires approved content pass and subtitle alignment. Do NOT use for rough-cut content decisions, transcription, or draft decryption/version recovery; use jianying-rough-cut and jianying-editor for those.
---

# Jianying Packaging

Turn an approved, content-stable Jianying timeline into a packaged copy. Decide what deserves emphasis and how to realize it with text, template styling, animation, overlay media, and animation-synchronized sound. Preserve the user's current manual corrections.

## Boundaries

- Use `jianying-rough-cut` or another content-analysis workflow to decide cuts, fillers, repetition, speaker roles, or Q&A structure. This skill does not change spoken content.
- Require a stable/approved content pass and an approved subtitle-alignment plan before formal packaging. If packaging reveals a semantic error, return it to `jianying-rough-cut`.
- Track the shared workflow states in [the rough-cut workflow reference](../jianying-rough-cut/references/workflow-state.md) when coordinating a multi-skill run.
- Use `jianying-editor` for project probing, timeline resolution, decryption, replica handling, backups, atomic write-back, validation, and rollback. Do not create a second project I/O implementation here.
- Treat raw Jianying fields as version-dependent. Prefer a user-confirmed timeline segment or template as the style source.
- Do not claim an object/property operation is supported merely because a field name exists. Consult [references/capability-audit.md](references/capability-audit.md) for evidence status.

## Required workflow

1. Confirm the explicit draft path, source timeline, packaging goal, and whether the request is review-only or execution. Ask for/save the current Jianying page before comparing files so unsaved manual edits are not lost.
2. Load `jianying-editor` and run `probe`, `inspect`, and `validate` on the source timeline. Resolve hybrid-layout conflicts explicitly.
3. Compare the current source with the latest user-confirmed manual reference. Preserve its timing, wording, segmentation, styles, layer order, visibility choices, overlay media, and sound choices unless the user requests a change.
4. Confirm `subtitle_alignment=approved` and read the finalized subtitles with at least the previous and next semantic unit. Identify emphasis by meaning, not keyword frequency. Use [references/semantic-packaging.md](references/semantic-packaging.md).
5. Clone a packaging working timeline and copy candidate sentence/word/character text to an upper review track. Keep the original subtitle track visible while the user reviews emphasis, wording, timing, segmentation, overlap, and obstruction. Read [references/staging-and-covered-subtitles.md](references/staging-and-covered-subtitles.md).
6. After staging review, group related text layers into one packaging event. Assign a semantic category, emphasis level, visual preset, motion cue, and optional sound rationale.
7. Inventory candidate templates and reusable assets from the current draft, template timelines, subdrafts, or local material indexes. Record exact source and target timeline/track/segment/material IDs; never guess effect IDs. Check font health and same-group fallback before accepting a flower-text preset.
8. Produce a packaging plan and validate it with `scripts/validate_packaging_plan.py`. Follow [references/plan-schema.md](references/plan-schema.md). When changing the validator, run `scripts/test_validate_packaging_plan.py` as well.
9. Unless the user has explicitly authorized execution, stop after the staging or final plan and request review. Approval of content cutting does not imply approval of packaging writes.
10. For execution, clone the source timeline and apply the smallest approved changes to the clone. Follow the execution rules below.
11. Validate in memory, write through `jianying-editor`, decrypt/read back every confirmed replica, validate again, and compare the result against both the approved plan and the source timeline.
12. Visually inspect ambiguous style, coordinate, layer, animation, text-fit, transition, effect, color, position, rotation, and background results in Jianying after the project is reopened. File-level values alone do not prove the UI appearance.

## Planning model

Use three independent decisions for every group:

- `category`: what the text means, such as question, parameter, brand, technical term, conclusion, warning, contrast, CTA, or ordinary explanation.
- `level`: how strongly it should be emphasized. Use 1 for restrained support, 2 for important information, and 3 only for the few core takeaways.
- `motion`: what visibly happens, such as pop, reveal, typing, sweep, impact, mechanical open, or no motion.

The visual preset follows category and level. The sound follows the actual motion cue plus spoken meaning; it does not follow text-layer count.

Every plan group must carry its semantic `context`, `category`, `level`, and `motion`. For an animated group, record the resolved motion event (`start_us`, `peak_us`, and `end_us`) so an audio anchor can be audited. Every executable visual or audio operation must identify its target; copied templates and assets must identify their source. The plan validator is the gate for these requirements.

## Template and text execution rules

- Prefer cloning a complete template segment and its referenced material closure. Generate new IDs and replace exact references throughout the copied closure.
- Inherit template properties by default. Override only approved fields such as text, timing, position, or one explicit style variable.
- Distinguish absolute assignment from relative adjustment. Represent them as `{mode: absolute, value: ...}` and `{mode: relative, delta: ...}`.
- When replacing text, synchronize every representation that the source material actually uses, especially `content`, `base_content`, `recognize_text`, and every style range. A visible style may be split between top-level material fields and nested `content.styles`.
- Derive start/end points from the current saved subtitle or animation event, not rounded planning decimals. Keep each group on separate non-overlapping tracks where required.
- For text that covers a subtitle, preserve the original on the staging/source timeline. `enable=false` is not a reliable hide operation; only disable after read-back proves the current version honors it, or delete on the cloned target after explicit approval and rollback preparation. Never mutate the source to achieve coverage.
- Treat display-only shortening, line breaks, punctuation, emphasis range, and cover relations as `light_content_ops`. Do not delete, reorder, or semantically rewrite complete spoken units here; return those decisions to `jianying-rough-cut`.
- Treat layer order as part of the template. For the established question template, place the question-mark track below the group's text tracks and start the mark with the second phrase; for a one-phrase question, start it with that phrase.
- Use a confirmed prototype to convert UI coordinates to stored normalized coordinates. Do not hardcode canvas height or assume that the UI number equals the raw JSON value.

Read [references/property-model.md](references/property-model.md) before changing raw properties or creating a reusable preset. For the user's saved flower-text composites, also read [references/flower-text-templates.md](references/flower-text-templates.md) and use the machine-readable [references/flower-text-templates.json](references/flower-text-templates.json) for exact source locators, layer geometry, relative positions, and text-fit constraints.

## Sound execution rules

- At most one primary sound per semantic animation group unless the approved design explicitly requires a layer.
- Align to the perceptual landing point (`animation_peak` or `transition_peak` when that is where the motion lands); do not auto-align every sound to segment start. Fail closed when duration, mask, or dialogue collision is unresolved.
- Select motion family → sound family → reuse cap (default 3) → semantic special slot. The canonical table and selection detail live in [references/semantic-packaging.md](references/semantic-packaging.md#sound-choice). Do not infer a sound from a cache md5. Preserve manual replacements/deletions and record rationale.

## Safe execution implementation

Create project-specific mutation code outside this skill. It may import reusable pure helpers from the approved plan, but project reads/writes must use the canonical `jianying-editor` implementation.

Before a write:

- ensure Jianying has saved and released the draft;
- clone the source timeline unless the user explicitly requested in-place changes; an apply plan may bypass this only with an explicit authorization note and `execution.allow_in_place: true`;
- keep `execution.preserve_manual_edits: true` unless the user explicitly authorizes overwriting them, recorded by `execution.allow_manual_overwrite: true` and an authorization note;
- fail closed when a template, material closure, target segment, or coordinate conversion is ambiguous;
- fail closed when the alignment precondition, staging review, font health, sound path, or supported capability evidence is missing;
- preserve unknown fields and untouched tracks.

After a write, report the source and target timeline IDs/names, backup location, changed groups with reasons, files written, validation/read-back result, visual checks still needed, and rollback path.

## Review checklist

- Every emphasized phrase still means the same thing as the approved subtitle context.
- No manual timing, wording, layer, style, overlay, or sound choice changed without an explicit plan item.
- Text has no missing characters; style ranges cover the full replacement text; `content` and `base_content` agree where both exist.
- Text fits the approved line-count and per-line limit without unwanted wrapping.
- Preset source, target locators, and overrides are traceable.
- Layer order and group timing reproduce the intended composition.
- Each sound has a motion/content rationale, is synchronized to the perceptual event, avoids unnecessary repetition, and does not collide with dialogue or another sound.
- Source timeline remains intact; target replicas agree; final `jianying-editor validate` is successful.
- Packaging staging is reversible, covered subtitle policy is explicit, and no semantic content decision has been silently made in the packaging layer.
