---
name: jianying-packaging
description: "Use when a saved Jianying timeline needs semantic emphasis, flower text, group layout, motion, transitions, overlays, or synchronized sound effects. Use after speech and subtitle content are stable; do not decide speech cuts or rewrite meaning."
---

# Jianying Packaging

Use this skill after the spoken content and current subtitles are stable or approved. It plans semantic emphasis and its visual/audio presentation on a Jianying timeline.

## Scope and authority

- Owns emphasis selection, flower text, group layout, templates, motion, transitions, overlays, and sound rationale tied to visible events.
- jianying-rough-cut owns transcript correction, speech cuts, semantic rewriting, and subtitle alignment. Return content errors there.
- jianying-editor owns draft probing, timeline reads/writes, cloning, decryption, backups, read-back, validation, and rollback. This skill's packaging CLI is read-only.
- The latest saved, user-confirmed timeline is authoritative for text, timing, segmentation, styles, layer order, visibility, and manual sound choices. Re-read it before each pass; do not apply stale locators or restore removed choices.
- Keep project names, copy, timecodes, IDs, assets, colors, and one-off style choices in external case references, not in this reusable skill.

## Emphasis selection

Read each complete sentence with its neighboring context and the video's communication goal. Select by meaning, not keyword frequency.

- The default emphasis unit is a complete sentence. Select and preserve the complete sentence as supplied in the current subtitles.
- Select a word, character, or fragment inside a sentence only when the user explicitly requests that granularity. Do not fragment sentences just to make the emphasis feel denser.
- Group related sentences into one visual event only when they share a message. For short videos, 1–3 complete sentences can form a group; two is a useful default when the timing and meaning fit.
- Keep ordinary explanations restrained; distinguish supporting facts from core takeaways. Do not promote every brand, number, or technical term automatically.
- Do not change spoken meaning in the packaging layer. Display-only edits such as line breaks or approved shortening remain tied to the complete source sentence and require review.

### Dialogue-aware selection

- Read speaker and turn roles from the approved rough-cut/subtitle handoff. Treat a host preamble, the actual question, and the guest answer as separate semantic units unless the user explicitly approves another grouping.
- Select every complete question as its own key group. Choose only 1–2 separate answer groups; do not fold answers into the question group by default.
- Mark the opening and ending with theme-bearing groups. After the required question/answer choices, compare the remaining key groups against their neighbors so their timing gaps are reasonably balanced.
- Record `group_kind`, `speaker_context`, and `sentence_count` in review artifacts. A group normally contains 1–3 complete sentences and should be labeled `句1/2` when it contains two.

For semantic categories, levels, grouping, and sound rationale, read [references/semantic-packaging.md](references/semantic-packaging.md).

## Modes and workflow

- **analysis:** read-only audit; report observed text, layout, template, motion, transition, and sound issues.
- **staging:** prepare a reversible upper-track review surface; leave the original subtitle track unchanged and visible for review, and omit final sound/effect writes.
- **final:** prepare or apply an approved packaging plan after staging, subtitle authority, and remapping gates are satisfied.

Choose analysis for review-only requests. Staging or final writes require explicit user authorization; a rough-cut approval alone does not authorize packaging writes.

1. Confirm the current draft/timeline, saved state, requested scope, and whether the user authorized execution.
2. Before staging or final packaging, require content_pass to be stable or approved and subtitle_alignment to be approved. Read the final subtitles with neighboring context. Inspect the saved timeline through jianying-editor, compare it with the latest manual reference, and preserve manual choices unless the user asks for a change.
3. If a visual style or layout choice is still open, show a comparison preview before writing. In staging, let the user review selected sentences, grouping, timing, overlap, and obstruction.
4. Group related text and graphic layers by perceptual event. Resolve layout from the approved subtitle transform and a verified reference; do not guess raw Jianying coordinates, color fields, or effect IDs.
5. Build and validate a plan with `python scripts/packaging_tool.py validate plan <plan.json>`. When sound is in scope, supply the current case's verified --catalog <case-catalog.json> and --pools <case-pools.json>; missing inputs remain unresolved and never fall back to bundled assets.
6. Apply only an approved plan through jianying-editor. Clone by default; honor an explicit request for in-place editing. Read back the result, validate it against the approved plan and source, and inspect ambiguous visual/audio results in Jianying after reopening.

When requesting a clone, preserve the source labels required by the active project's naming convention and give the copy a purpose-specific, unique name. The naming tokens and suffix format come from the active project/editor workflow; this skill does not prescribe literal sample names or a timezone.

### Stale-plan gate

A manual edit to the current saved timeline invalidates the previous plan and group report. Before staging or final execution, re-decode the source and target and compare at least the source/target hash, duration, subtitle-row count, group row ranges, visibility flags, and transform values. If any differ from the plan snapshot, rebuild the plan and review artifacts from the current saved timeline; never restore stale locators or the old selection.

## Review methods

Run these checks against the current saved timeline, not against an earlier exported SRT or plan.

1. **Selection review:** confirm group count, complete-sentence boundaries, speaker/turn labels, question groups, the 1–2 answer groups, opening/ending groups, and timing-gap balance.
2. **Text review:** compare every staged text hash with the approved subtitle reference; verify `句N/M` labels and that no semantic unit was rewritten.
3. **Same-screen review:** for each group inspect the first frame, a middle frame, and the final frame. Confirm every intended line is visible at the group end, there is no same-track overlap, and manual transforms were preserved.
4. **Covered-subtitle review:** on the source timeline, originals remain unchanged. On an explicitly approved clone, only covered originals may be hidden; verify `visible=false` by read-back and by preview.
5. **Editor review:** run `jianying-editor validate`, verify every replica, source hash preservation, backup presence, and plan/read-back equality.
6. **Preview review:** use `jianying-preview frame` or `shot` at group start/middle/end. Stop on text mismatch, unexpected layer addition/removal, collision, obstruction, or a source-timeline change.

Record the selected review times, observed layer counts, track assignments, backup path, and any unresolved speaker/listening issue in the review report.

## Motion, sound, and review gates

- Keep motion traceable to a user-approved template or verified source, and vary among reference-backed choices within the plan reuse cap. Do not invent support for raw properties from field names alone.
- Treat each perceptual motion beat as an event. Co-timed layers share one event and normally one primary sound; separate entrances or moving marks are separate events.
- Match sound to event meaning and motion. Follow the task's full/selective coverage and repetition policy; do not infer coverage from segment/audio counts. Align the first audible transient to the perceptual landing and account for measured leading silence.
- Classify music, ambience, dialogue, SFX, and unknown audio separately. Resolve unknown roles and dialogue collisions by review.
- Check animated marks and overlapping text at entry, peak, and exit; static transforms do not prove readability.
- Preserve the narration track's role and do not attach emphasis animation to it. Follow approved layer order and extension-hold behavior.

## Final review

Before reporting a package as verified, confirm the complete approved text is intact; each group fits and remains readable within the safe area; motion and templates are traceable; event-level sound coverage, audible onset, repetition, and dialogue collisions satisfy the request; and editor read-back matches the approved plan. File-level validation does not prove visual or listening quality.

Use [references/motion-audio-audit.md](references/motion-audio-audit.md) for event coverage and audio evidence; use [references/layout-templates.md](references/layout-templates.md) for relative slots and animated readability.

## Reference routing

Read only what the requested operation needs:

- Track copying, covered subtitles, or staging: [references/staging-and-covered-subtitles.md](references/staging-and-covered-subtitles.md).
- Layout or animated positioning: [references/layout-templates.md](references/layout-templates.md) and [references/property-model.md](references/property-model.md).
- Template capabilities and provenance: [references/capability-audit.md](references/capability-audit.md) and [references/flower-text-templates.md](references/flower-text-templates.md).
- Plan fields, gates, and validation behavior: [references/plan-schema.md](references/plan-schema.md).
- Sound choice, trim, and synchronization: [references/semantic-packaging.md](references/semantic-packaging.md) and [references/motion-audio-audit.md](references/motion-audio-audit.md).
- Cross-skill state or changed timeline order: [references/workflow-state.md](../jianying-rough-cut/references/workflow-state.md) and [references/timeline-comparison.md](../jianying-rough-cut/references/timeline-comparison.md).

Packaging plans and audit tools do not write Jianying drafts. All draft operations and export-target checks remain with jianying-editor.
