---
name: jianying-packaging
description: "Use when a saved Jianying timeline needs semantic emphasis, flower text, group layout, motion, transitions, overlays, or synchronized sound effects. Read-only audits can run at any state; packaging plans require stable or approved content and approved subtitle alignment. Do not decide speech cuts or rewrite meaning."
---

# Jianying Packaging

Use this skill to audit a saved timeline or plan semantic emphasis and its visual/audio presentation. Read-only audits may run at any workflow state; packaging plans require a stable or approved content pass and approved subtitle alignment.

## Scope and authority

- Owns emphasis selection, flower text, group layout, templates, motion, transitions, overlays, and sound rationale tied to visible events.
- jianying-rough-cut owns transcript correction, speech cuts, semantic rewriting, and subtitle alignment. Return content errors there.
- jianying-editor owns draft decoding, encryption, replica discovery, transactional backups, low-level writes, read-back, validation, and rollback. This skill owns the schema 1.2 plan-to-draft adapter and invokes those existing transaction APIs; do not route packaging plans through `jianying-editor apply-plan`, which only applies `keep_blocks`.
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
- Select complete questions and answers according to the requested scope and emphasis density. When the brief calls for question-and-answer framing, keep selected questions and answers as separate key groups; do not automatically promote every question or impose a fixed answer-group count.
- Use opening or ending theme groups when they serve the video's message. Review spacing between selected groups without adding emphasis solely to meet a fixed cadence.
- Record `group_kind`, `speaker_context`, and `sentence_count` in review artifacts. A group normally contains 1–3 complete sentences and should be labeled `句1/2` when it contains two.

For semantic categories, levels, grouping, and sound rationale, read [references/semantic-packaging.md](references/semantic-packaging.md).

## Modes and workflow

- **analysis:** read-only audit; report observed text, layout, template, motion, transition, and sound issues.
- **staging:** prepare a reversible upper-track review surface; leave the original subtitle track unchanged and visible for review, and omit final sound/effect writes.
- **final:** prepare or apply an approved packaging plan after staging, subtitle authority, and remapping gates are satisfied.

Choose analysis for review-only requests; it is read-only and may run at any workflow state. Staging and final writes require authorization for that specific phase and target. An explicit request to perform the write supplies that authorization while its scope and target remain unchanged; do not ask for it again. Approval of a rough-cut plan or packaging plan alone does not authorize a new write.

1. Confirm the current draft/timeline, saved state, requested scope, and applicable authorization. If the requested operation is unclear, resolve that before preparing an executable plan.
2. To prepare a packaging plan, require `content_pass` to be `stable` or `approved` and `subtitle_alignment` to be `approved`. Before creating or updating a staging timeline, require both states to be `approved`. Final application additionally requires approved staging, an approved final-subtitle reference, and verified or not-required remapping. Read the final subtitles with neighboring context. Inspect the saved timeline through jianying-editor when the request requires draft evidence, compare it with the latest manual reference, and preserve manual choices unless the user asks for a change.
3. If a visual style or layout choice is still open, show a comparison preview before writing. In staging, let the user review selected sentences, grouping, timing, overlap, and obstruction.
4. Group related text and graphic layers by perceptual event. Resolve layout from the approved subtitle transform and a verified reference; do not guess raw Jianying coordinates, color fields, or effect IDs.
5. Build and validate a plan with `python scripts/packaging_tool.py validate plan <plan.json>`. When sound is in scope, supply the current case's verified `--catalog <case-catalog.json>` and `--pools <case-pools.json>`; missing inputs remain unresolved and never fall back to bundled assets.
6. Run `apply` without `--apply` first. Copy the reported `data.source_timeline_hash` into `review_report.source_timeline_hash`; `--apply` blocks if it is missing or differs from the current source. For a layout or animation change, open the reported HTML preview, review its measured text bounds, safe zone, position, track, alpha, and duration, then record `review_report.visual_preview_status: "approved"` and the exact `visual_preview_sha256` in the plan. `--apply` blocks if that approval is missing or its hash no longer matches the current candidate. The HTML is a geometry/timing preview, not proof that Jianying retains or renders an effect. For animation plans, pass `--animation-cache-root` when cache discovery is ambiguous; include same-version capability evidence with `--animation-capabilities` and identify the running version with `--animation-version` when it cannot be detected. For sound, pass the same `--catalog` and `--pools` used during validation. If current timeline audio roles do not identify dialogue, supply `--existing-audio <dialogue-intervals.json>`; unresolved dialogue collision evidence blocks sound apply. The adapter supports schema 1.2, clones by default, uses the existing `JianyingProject` transaction API, and blocks unsupported prototypes/field mappings before writing. It copies current-draft media/template closures; external media must be staged first. Requested motion must have a non-empty motion payload in the prototype. Read back the result, validate it against the approved plan and source, and inspect ambiguous visual/audio results in Jianying after reopening.

`stable` can be used to prepare a review plan. Any staging or final apply
requires `source.content_pass: approved` and
`source.subtitle_alignment.status: approved`; final also requires approved
staging and verified/not-required remapping. The CLI enforces these status
gates. Only the Agent can confirm that the current conversation authorized the
write; `execution.mode=apply` and the `--apply` flag do not create that
authorization.

```powershell
python scripts/packaging_tool.py apply `
  --draft "<draft-path>" `
  --timeline "<source-timeline>" `
  --plan "<schema-1.2-plan.json>" `
  --catalog "<case-catalog.json>" `
  --pools "<case-pools.json>" `
  --existing-audio "<dialogue-intervals.json>" `
  --apply
```

Final/apply layout writes require numeric `layout.constraints.safe_zone` bounds
in normalized canvas coordinates and `project_profile.canvas_width`/
`canvas_height`. The adapter measures the current local font file from the text
material and blocks automatic layout if it cannot get reliable glyph metrics.
Relative layout changes require preview approval; position and alpha changes
are previewed as well. `global_alpha` is written only when the current text
segment prototype already carries that field. Hiding remains a separate
`visible` property. Auxiliary text must target an existing unique topmost text
track and must not overlap another segment on that track; apply never creates
that track automatically.

Source replica checks use `ReplicaManifest` roles: drift in an associated
`writable-backup` is reported as a warning, while primary/template drift and
missing, unreadable, or unassociated candidates block. The post-write check
still requires all transaction-managed replicas to match.

`--existing-audio` may contain a list of explicit intervals, for example
`[{"id":"voice-1","kind":"dialogue","start_us":1200000,"end_us":3400000}]`.
The adapter also derives dialogue intervals from recognized audio material or
track-role metadata in the current timeline; unknown roles are never treated
as proof that dialogue is absent.

## Phase handoffs and next-step suggestions

At each phase exit, report the result, one recommended next step, and any
pending approval or evidence gate. Recommendations describe what may happen
next; they do not authorize or automatically perform another write.

| Phase result | Next-step suggestion |
|---|---|
| Read-only analysis is complete | Deliver the observed issues and stop. Start plan preparation only if requested. |
| Plan validates, but staging was not requested | Deliver the plan and stop without changing a draft. |
| Plan validates and staging was requested | Check the stricter staging state and authorization gates; if either is missing, name it and stop. Otherwise create the default clone and review surface. |
| Staging is saved as `reviewing` | Tell the user which copy to open and what to review; wait for their feedback. |
| User edits staging or the saved snapshot changed | Re-decode the current source and target, refresh the report/plan, and return to staging review. Do not reuse stale locators. |
| Staging is approved | Apply the final package only when final was requested and its gates pass; otherwise deliver the approved staging state and stop. |
| Final apply and editor read-back are complete | Reopen Jianying and perform the visual/audio review before reporting the package as verified. |
| Semantic issue or visual/audio failure is found | Return semantic issues to rough-cut; revise packaging issues and repeat the affected review. |

When requesting a clone, preserve the source labels required by the active project's naming convention and give the copy a purpose-specific, unique name. The naming tokens and suffix format come from the active project/editor workflow; this skill does not prescribe literal sample names or a timezone.

### Stale-plan gate

A manual edit to the current saved timeline invalidates the previous plan and group report. Before staging or final execution, re-decode the source and target and compare at least the source/target hash, duration, subtitle-row count, group row ranges, visibility flags, and transform values. Apply plans must carry the latest dry-run `data.source_timeline_hash` as `review_report.source_timeline_hash`; the adapter blocks missing or mismatched values before transformation or cloning. If any state differs from the plan snapshot, rebuild the plan and review artifacts from the current saved timeline; never restore stale locators or the old selection.

## Review methods

Run these checks against the current saved timeline, not against an earlier exported SRT or plan.

1. **Selection review:** confirm group count, complete-sentence boundaries, speaker/turn labels, selected question and answer groups against the requested scope and emphasis density, opening/ending choices, and timing-gap balance.
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
- State gates and write authorization: always read [references/workflow-state.md](../jianying-rough-cut/references/workflow-state.md) before staging or final execution.
- Changed timeline order: read [references/timeline-comparison.md](../jianying-rough-cut/references/timeline-comparison.md) and verify semantic remapping before reusing earlier timing.

Read-only analysis commands do not write drafts. Schema 1.2 writes go through this Skill's `apply` adapter and the existing jianying-editor transaction API; all encryption, backup, replica, and read-back primitives remain in jianying-editor.
