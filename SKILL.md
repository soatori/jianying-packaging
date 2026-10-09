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
