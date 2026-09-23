---
name: jianying-packaging
description: "Use for 剪映智能包装 after spoken content and subtitle alignment are stable: choose semantic emphasis and realize it with flower text, upper-track text, templates, motion, transitions, overlays, and sound. Produce a reversible packaging plan or execute an approved plan through jianying-editor. Do not decide speech cuts or rewrite semantic content."
---

# Jianying-Intelligent-Packaging

This is the presentation-intelligence layer for an approved, content-stable 剪映 timeline. It turns meaning into restrained visual and audio emphasis—flower text, upper-track text, templates, motion, transitions, overlays, and synchronized sound—while preserving the user's current manual corrections. It produces a reversible staging/packaging plan and delegates project I/O to `jianying-editor`.

For user-specific learned packaging conventions, consult the applicable project-level reference when the request concerns a saved manual style, layout, emphasis grouping, animation, or sound. Keep those project-specific references outside this reusable skill.

## Positioning

- **Entry gate:** content editing and subtitle alignment must be stable or approved, and the current Jianying page/draft must be saved before comparison or execution.
- **Owns:** semantic emphasis, packaging categories and levels, visual presets, motion cues, template/asset selection, covered-subtitle presentation policy, and sound rationale tied to the actual animation or transition event.
- **Produces:** a reviewable upper-track staging result and a validated packaging plan; execution changes are applied only to a clone unless the user explicitly authorizes in-place work.
- **Handoff:** `jianying-editor` owns probing, decryption, timeline resolution, backups, atomic write-back, validation, read-back, and rollback.
- **Does not own:** transcription, content cuts, filler or pause decisions, semantic rewriting, Q&A restructuring, draft recovery, or unsupported raw-property experimentation.
- **Manual-reference precedence:** the current saved, user-confirmed timeline is authoritative for wording, timing, segmentation, style, visibility, layer order, and sound choices. Older plans, templates, ASR output, and automatic selections are evidence only and must not silently restore a removed choice.
- **Rule scope:** reusable guidance in this skill must remain project-agnostic. Project names, concrete copy, sentence lists, timecodes, timeline or track IDs, and one-off brand/highlight decisions belong in project records, not in this skill.

“Intelligent” means selecting emphasis from the surrounding meaning and communication goal, not decorating every subtitle or inferring effects from keyword frequency alone.

## Operating modes

- `analysis`: read-only packaging audit. Analyze flower-text layers, templates, motion, transitions, relative layout, sound choices, and discrepancies. Do not clone a timeline, write a draft, add sound, or execute a template.
- `staging`: create only the approved reversible upper-track review surface. Preserve source subtitles and do not add final templates or sound effects.
- `final`: produce or execute an approved packaging plan after final-subtitle authority, staging, remapping, and safety gates are satisfied.

If the user asks to analyze or not modify, use `analysis`. A packaging report may contain project-specific observations, but reusable references, registries, and tests must remain generic.

## Boundaries

- Use `jianying-rough-cut` or another content-analysis workflow to decide cuts, fillers, repetition, speaker roles, or Q&A structure. This skill does not change spoken content.
- Require a stable/approved content pass and an approved subtitle-alignment plan before formal packaging. If packaging reveals a semantic error, return it to `jianying-rough-cut`.
- Track the shared workflow states when coordinating a multi-skill run. The handoff table is the document named `workflow-state` inside the sibling skill `jianying-rough-cut` (open that skill’s references folder after it is installed). Do not treat a missing local path as a defect in this skill.
- This skill assumes `jianying-rough-cut` and `jianying-editor` are installed as sibling skills by name.
- Use `jianying-editor` for project probing, timeline resolution, decryption, replica handling, backups, atomic write-back, validation, and rollback. Do not create a second project I/O implementation here.
- Treat raw Jianying fields as version-dependent. Position, color, and animation parameters must be derived from the user-approved reference draft's emphasis-track measured values and applied group-by-group. Do not invent or extrapolate from abstract rules when a reference is available.
- Do not claim an object/property operation is supported merely because a field name exists. Consult [references/capability-audit.md](references/capability-audit.md) for evidence status.
- Read [references/timeline-comparison.md](../jianying-rough-cut/references/timeline-comparison.md) when a source and target order differ; never reuse old effect timecodes without a verified semantic remap.

## Selection and layer rules

- Select emphasis by semantic event and communication role, not by keyword frequency alone. Structural cues such as section labels, process markers, or contrast framing may be valid emphasis when they belong to the approved spoken context.
- For two phrases that form one semantic event, the first phrase may remain visible through the end of the second phrase, and the second phrase may occupy a higher text layer. Derive both endpoints from the current saved segments; do not hardcode timecodes, merge spoken units, or rewrite their meaning.
- Preserve the user's observed layer order and group relationships. Do not assume a fixed number of text tracks or a fixed `track_render_index`; resolve the current timeline and use relative, reviewable layout where possible.
- Keep brands, models, numbers, and technical terms accurate in the underlying subtitles, but do not promote every protected term to flower text. Highlight selection remains an explicit, user-confirmed packaging decision.
- Default each flower-text material to one whole-line color. Do not split a single line into per-word or per-character color ranges unless the approved reference draft or an explicit user instruction does so; per-word coloring is treated as an error state.
- The narration track must not carry any animation slot. Empty or populated, an animation slot on narration is a residual error to remove. This rule is track-role-based and does not apply to emphasis-track tail stubs described in the extension-hold pattern (see Planning model).

## Required workflow

1. Confirm the explicit draft path, source timeline, packaging goal, and whether the request is review-only or execution. Ask for/save the current Jianying page before comparing files so unsaved manual edits are not lost.
2. Load `jianying-editor` and run `probe`, `inspect`, and `validate` on the source timeline. Resolve hybrid-layout conflicts explicitly.
3. Compare the current source with the latest user-confirmed manual reference. Preserve its timing, wording, segmentation, styles, layer order, visibility choices, overlay media, and sound choices unless the user requests a change. At every analysis, staging, final, or rework pass, re-read the current saved timeline from scratch; do not reuse a decoded snapshot, segment index, or locator cache from a prior pass. Between passes the user commonly re-groups tracks, changes segment timing, or edits wording, and stale locators will target the wrong rows or silently overwrite manual corrections.
4. Confirm `subtitle_alignment=approved` and read the finalized subtitles with at least the previous and next semantic unit. Identify emphasis by meaning, not keyword frequency. Use [references/semantic-packaging.md](references/semantic-packaging.md).
5. In `analysis` mode, stop before cloning and report the observed template, motion, transition, relative-layout, sound, and text discrepancies. In `staging` or `final` mode, clone a packaging working timeline and copy candidate sentence/word/character text to an upper review track. Keep the original subtitle track visible while the user reviews emphasis, wording, timing, segmentation, overlap, and obstruction. Read [references/staging-and-covered-subtitles.md](references/staging-and-covered-subtitles.md).
6. After staging review, group related text layers into one packaging event. Assign a semantic category, emphasis level, visual preset, motion cue, and optional sound rationale.
7. Inventory candidate templates and reusable assets from the current draft, template timelines, subdrafts, or local material indexes. Record exact source and target timeline/track/segment/material IDs; never guess effect IDs. Every motion preset must cite the reference source it came from, and a motion that cannot be traced to that source is fabricated and forbidden. Check font health and same-group fallback before accepting a flower-text preset.
8. Produce a packaging plan and validate it with `python scripts/packaging_tool.py validate plan <plan.json>`. Use the same CLI for layout, sound-catalog, generic-content, preflight, snapshot, diff, resolve, layers, motion-check, audio-audit, sound-check, and verify operations. Follow [references/plan-schema.md](references/plan-schema.md) and the packaging regression tests.
9. Unless the user has explicitly authorized execution, stop after the staging or final plan and request review. Approval of content cutting does not imply approval of packaging writes.
10. For execution, clone the source timeline and apply the smallest approved changes to the clone. Follow the execution rules below.
11. Validate in memory, write through `jianying-editor`, decrypt/read back every confirmed replica, validate again, and compare the result against both the approved plan and the source timeline.
12. Visually inspect ambiguous style, coordinate, layer, animation, text-fit, transition, effect, color, position, rotation, and background results in Jianying after the project is reopened. File-level values alone do not prove the UI appearance.

## Tool layer

`scripts/packaging_tool.py` is the read-only packaging CLI. Its importable functions live under `scripts/packaging_tools/`; they normalize observations, compare a saved manual reference, discover dynamic layers, audit motion reuse and audio roles, resolve subtitle/text hashes and relative layouts, inspect asset/sound evidence, emit external-case `learning_report` records, and verify editor read-back reports. It never calls `clone` or `apply` and never writes a Jianying draft. Use `--format text` only for a human-readable summary; JSON is the default output.

Every command returns a machine-readable report envelope with `data` plus `errors`, `input_errors`, and `warnings`. The next command may consume the complete previous report directly; it unwraps `data` automatically and also accepts raw data JSON. Exit codes are `0` for usable reports including review warnings, `1` for validation/safety/evidence blocks, and `2` for JSON, path, argument, or output-file errors. Schema 1.2 uses `group.visual`; `visuals` and `visual_operations` are read-only compatibility aliases and conflicting aliases stop resolution. The tool layer is fail-closed for missing/duplicate locators, order changes, hash mismatches, unresolved anchors, layout collisions, sound evidence, and unexpected read-back changes.

## Planning model

Default strategies below yield to the user-approved reference draft's measured values and to any explicit user direction whenever they conflict.

Use three independent decisions for every group:

- `category`: what the text means, such as question, parameter, brand, technical term, conclusion, warning, contrast, CTA, or ordinary explanation.
- `level`: how strongly it should be emphasized. Use 1 for restrained support, 2 for important information, and 3 only for the few core takeaways.
- `motion`: what visibly happens, such as pop, reveal, typing, sweep, impact, mechanical open, or no motion.

For position-sensitive rows, prefer a non-displacing intro; a displacement-based intro shifts the landing point and conflicts with manually set positions.

The visual preset follows category and level. The sound follows the actual motion cue plus spoken meaning; it does not follow text-layer count.

Default each material to a white text base and reserve the single accent color exclusively for level-3 core sentences; source the exact accent only from the reference draft or explicit user direction.

Motion reuse is audited within playback-local adjacent content regions, not as a whole-film duplicate count. Preserve an explicit `content_region_id` (or compatible `semantic_region`) when available; a shared motif is exempt only inside that same region. Within one packaging, motion must vary semantically across groups; the only exception is when the reference draft establishes a single consistent intro.

Every plan group must carry its semantic `context`, `category`, `level`, and `motion`. For an animated group, record the resolved motion event (`start_us`, `peak_us`, and `end_us`) so an audio anchor can be audited. Every executable visual or audio operation must identify its target; copied templates and assets must identify their source. The plan validator is the gate for these requirements.

Within a multi-line emphasis group, all member lines must share the same on-screen start; verify co-timing after resolving each group's segment references. When only some lines animate in and others hold static, the group visually fragments into separate events rather than one composition.

In schema 1.2, every final visual group also carries `semantic_unit_refs`, `subtitle_anchor`, `remap_status`, and a `layout` object. The layout is group-level, uses a runtime `X0/Y0` anchor, and resolves arbitrary slot relationships through relative offsets. Do not assign independent absolute coordinates to each text layer.

Schema 1.2 also carries an `execution.context_contract`. It is the context handoff used by `jianying-editor` until a runtime consumer exists: resolve the final-subtitle `X0/Y0`, calculate each group atomically, select one catalog-backed sound, require read-back, and stop on every declared safety condition. Do not describe a context-only handoff as automated editor support.

The extension-hold pattern is intentional: a hold spans two segments where the head carries the intro animation and the tail carries an empty animation stub. Do not flag the tail stub as an error on emphasis tracks. The narration-track animation-slot ban remains absolute.

## Template and text execution rules

- Prefer cloning a complete template segment and its referenced material closure. Generate new IDs and replace exact references throughout the copied closure.
- Inherit template properties by default. Override only approved fields such as text, timing, position, or one explicit style variable.
- Distinguish absolute assignment from relative adjustment. Represent them as `{mode: absolute, value: ...}` and `{mode: relative, delta: ...}`.
- When replacing text, synchronize every representation that the source material actually uses, especially `content`, `base_content`, `recognize_text`, and every style range. A visible style may be split between top-level material fields and nested `content.styles`.
- Derive start/end points from the current saved subtitle or animation event, not rounded planning decimals. Keep each group on separate non-overlapping tracks where required.
- For text that covers a subtitle, preserve the original on the staging/source timeline. `enable=false` is not a reliable hide operation; only disable after read-back proves the current version honors it, or delete on the cloned target after explicit approval and rollback preparation. Never mutate the source to achieve coverage.
- Treat display-only shortening, line breaks, punctuation, emphasis range, and cover relations as `light_content_ops`. Do not delete, reorder, or semantically rewrite complete spoken units here; return those decisions to `jianying-rough-cut`.
- Treat layer order as part of the template. For the established question template, place the question-mark track below the group's text tracks and start the mark with the second phrase; for a one-phrase question, start it with that phrase. For the auxiliary question-mark layer, default to white color, a semi-transparent global alpha, an enlarged scale, and a non-displacing intro; take the specific values from the reference draft.
- Use a confirmed prototype to convert UI coordinates to stored normalized coordinates. Do not hardcode canvas height or assume that the UI number equals the raw JSON value.
- Prefer `relative_template` layout with named slots, `relative_to`, `inherit_transform_from`, safe-zone constraints, and a `manual_review` fallback. Base templates include centered, stacked, side-pair, overlay/replace, attached-mark, and composite layouts; extensions are data-only compositions. `legacy_absolute` requires explicit visual verification and must not be silently promoted to final apply.
- Derive `X0` and `Y0` from the current final subtitle reference at runtime. Static continuation text inherits the transform of its source slot. Validate text bounds, collisions, and overflow after resolving the whole group. For co-timed rows, derive the minimum inter-row spacing from the reference draft's measured values; never guess or reuse a fixed number.
- In schema 1.2, every layout slot declares `ref_type`: subtitle-unit refs must belong to the current semantic group, while auxiliary marks must be declared in `auxiliary_text_refs`. Parent templates resolve before child overrides; cyclic inheritance is invalid.
- In schema 1.2, every final text operation must bind `text_ref` and a SHA-256 UTF-8 `text_hash` to the approved `source.final_subtitle_units` manifest. If the actual flower-text text or hash differs, mark `text_mismatch` and stop final/apply.

Read [references/property-model.md](references/property-model.md) before changing raw properties or creating a reusable preset. Use [references/flower-text-templates.md](references/flower-text-templates.md) only for the generic template contract. User-saved flower-text composites and template provenance must be supplied as an external project case reference; they are not bundled in this reusable Skill.

For reusable relative geometry, read [references/layout-templates.md](references/layout-templates.md) and [references/layout-template-registry.json](references/layout-template-registry.json). For sound metadata and alternatives, read [references/sound-preset-catalog.json](references/sound-preset-catalog.json) and [references/motion-sound-pools.json](references/motion-sound-pools.json). Catalogs contain generic metadata only; observed project assets belong in external case records.

## Sound execution rules

- At most one primary sound per semantic animation group unless the approved design explicitly requires a layer.
- Align to the perceptual landing point (`animation_peak` or `transition_peak` when that is where the motion lands); do not auto-align every sound to segment start. Fail closed when duration, mask, or dialogue collision is unresolved.
- Select motion family → sound family → reuse cap (default 3) → semantic special slot. The canonical table and selection detail live in [references/semantic-packaging.md](references/semantic-packaging.md#sound-choice). Do not infer a sound from a cache md5. Preserve manual replacements/deletions and record rationale.
- Select one verified candidate from `references/motion-sound-pools.json`; a usable motion family has at least three unique candidate presets. Keep the pool as alternatives, never simultaneous playback. Use `references/sound-preset-catalog.json` to classify `single_hit`, `decay`, `multi_hit`, `loop`, `ambience`, or `unknown` and to honor leading-silence metadata.
- Keep audio-audit events with an unknown role separate from SFX and route them to review; do not silently count them as effects.
- Default trim policy: `single_hit`/`decay` use the text span; multi-hit/typing sounds use the motion span. Skip known leading silence unless preservation is explicitly justified. Do not stretch or loop without catalog evidence. Record motion type, spoken function, visual landing, selection basis, reuse check, and dialogue-collision check.
- `text_span` must use the matching text and target ranges; `motion_span` must use the parsed motion-event range. A known leading silence requires an explicit source range. Inline candidate pools are for review only; final/apply must resolve a verified preset from the formal catalog and pool, including when a final plan is still in review mode.

## Landing a schema-1.2 plan onto a clone

The plan-application entry point in `jianying-editor` does not consume packaging plans. Landing an approved schema-1.2 packaging plan requires a project-local script that calls the editor primitives directly; do not build a second project I/O implementation around them.

- Clone with `clone_timeline`: segment, track, and material UUIDs are preserved, so every locator in the plan remains valid on the clone without remapping.
- Decode the clone, apply only the approved group changes, then write through the transactional `_write_content` and validate the read-back.
- Color: flower-text color must be written inside the material `content` JSON string — parse it, set `styles[].fill.content.solid.color` with 0–1 RGB values, and re-serialize the string. Writing only the top-level `text_color` field does not render and is an invalid write.
- In-animations: harvest the full set of in-animations from the approved reference draft, not a few favorites; clone each `sticker_animation` material verbatim (including its local cache references) under a new UUID and attach it to the target segment's `extra_material_refs`. Harvesting only a small subset produces repetitive motion and rework.
- Motion distribution: the first and second sentences within a group use different intros, adjacent groups use different intros, and a single preset is subject to a reuse cap.
- Verification: match applied changes by `material_id`, never by text — text matching collides with same-worded narration lines on lower tracks.
- Rework cleanup: before re-applying, delete the animation materials previously added by the script from `material_animations` and remove their references from the target segments' `extra_material_refs`; leftover references are residual empty animation slots.

## Safe execution implementation

Create project-specific mutation code outside this skill. It may import reusable pure helpers from the approved plan, but project reads/writes must use the canonical `jianying-editor` implementation.

Before a write:

- recommend closing Jianying and its tray/background process before a write; if it remains open, first ensure Jianying has saved and released the draft and treat the runtime warning as a review point;
- clone the source timeline unless the user explicitly requested in-place changes; an apply plan may bypass this only with an explicit authorization note and `execution.allow_in_place: true`;
- before a re-application, clear the animation materials added by the previous run and their `extra_material_refs` references (see "Landing a schema-1.2 plan onto a clone");
- keep `execution.preserve_manual_edits: true` unless the user explicitly authorizes overwriting them, recorded by `execution.allow_manual_overwrite: true` and an authorization note;
- fail closed when a template, material closure, target segment, or coordinate conversion is ambiguous;
- fail closed when the alignment precondition, staging review, font health, sound path, or supported capability evidence is missing;
- fail closed when the schema 1.2 context contract is missing, a layout reference is undeclared, a sound range is inconsistent, or a formal sound catalog/pool cannot be resolved;
- preserve unknown fields and untouched tracks.
- require a schema 1.2 final-subtitle reference, verified/not-required remap, clone/source-preservation settings, and `pre_write_backup=required`; these are execution gates, not editor implementation details.

After a write, report the source and target timeline IDs/names, backup location, changed groups with reasons, files written, validation/read-back result, visual checks still needed, and rollback path.

## Review checklist

- Every emphasized phrase still means the same thing as the approved subtitle context.
- No manual timing, wording, layer, style, overlay, or sound choice changed without an explicit plan item.
- Text has no missing characters; style ranges cover the full replacement text; `content` and `base_content` agree where both exist.
- Text fits the approved line-count and per-line limit without unwanted wrapping.
- Preset source, target locators, and overrides are traceable.
- Motion variety holds: first and second sentences in a group use different intros, adjacent groups differ, and no single preset exceeds its reuse cap.
- Layer order and group timing reproduce the intended composition.
- Each sound has a motion/content rationale, is synchronized to the perceptual event, avoids unnecessary repetition, and does not collide with dialogue or another sound.
- Source timeline remains intact; target replicas agree; final `jianying-editor validate` is successful.
- Packaging staging is reversible, covered subtitle policy is explicit, and no semantic content decision has been silently made in the packaging layer.
