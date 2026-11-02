---
name: jianying-packaging
description: "Use when a saved Jianying timeline needs semantic emphasis, flower text, group layout, motion, transitions, overlays, or synchronized sound effects. Read-only audits can run at any state; packaging plans require stable or approved content and approved subtitle alignment. Do not decide speech cuts or rewrite meaning."
---

# Jianying Packaging

Use this skill to audit a saved timeline or plan semantic emphasis and its visual/audio presentation. Read-only audits may run at any workflow state; packaging plans require a stable or approved content pass and approved subtitle alignment.

## Scope and authority

- Owns emphasis selection, flower text, group layout, templates, motion, transitions, overlays, and sound rationale tied to visible events.
- jianying-rough-cut owns transcript correction, speech cuts, semantic rewriting, and subtitle alignment. Return content errors there.
- jianying-editor owns draft decoding, encryption, replica discovery, transactional backups, low-level writes, read-back, validation, and rollback. This skill owns the schema 2.0 prepare/commit adapter and invokes those existing transaction APIs; do not route packaging plans through `jianying-editor apply-plan`, which only applies `keep_blocks`.
- Packaging an existing draft uses the CLI/JSON-plan workflow: validate a schema 2.0 plan and use `prepare`/`commit`; do not create a one-off Python driver for an operation represented by the plan schema.
- “Represented by schema 2.0” means the exact property and material kind have a verified adapter mapping. Direct overrides remain limited to the fields in [references/plan-schema.md](references/plan-schema.md); position/scale also require both segment and material transform prototypes. Text animation requires a `text` material and same-version capability evidence. A native `subtitle` material is not coerced to `text` and remains unsupported by this animation adapter until a same-version save/read-back and visual review verify it. For an unsupported operation, use a project-local driver through the editor transaction API only when its prototype and mapping are verified; otherwise keep the operation blocked. A style property simply absent from the whitelist (color, font size, transform, entry animation on a native `subtitle` copy) belongs to this driver route by definition, so "do not create a one-off Python driver" does not forbid it; never relabel a `subtitle` material as `text` to force the plan adapter, and never hand-roll `draft_content.json` writes outside the transaction API.
- The latest saved, user-confirmed timeline is authoritative for text, timing, segmentation, styles, layer order, visibility, and manual sound choices. Take one snapshot at the start of each analysis/plan pass and reuse it for that pass. Refresh only after a manual edit or detected source/target fingerprint change; never apply stale locators or restore removed choices.
- Keep project names, copy, timecodes, IDs, assets, colors, and one-off style choices in external case references, not in this reusable skill. A case reference is the project's own on-disk instructions file (its `AGENTS.md`, or the preview/design cards beside it); it holds material inventory (asset index, reference batches, source volumes), the approved style ladder for that client, and per-project exceptions. Load it at task start when the request points at that project, and never promote its values back into this skill.

## Emphasis selection

Before selecting anything, run the vertical subtitle format preflight in
[references/semantic-packaging.md](references/semantic-packaging.md#subtitle-format-profile-preflight-before-emphasis-selection)
against the current saved subtitles. Emphasis units are counted on correctly
broken lines; a violating line is a rough-cut review item, not an emphasis
candidate, and packaging does not re-break it.

Read each complete sentence with its neighboring context and the video's communication goal. Select by meaning, not keyword frequency.

- The default emphasis unit is a complete sentence. Select and preserve the complete sentence as supplied in the current subtitles.
- Select a word, character, or fragment inside a sentence only when the user explicitly requests that granularity. Do not fragment sentences just to make the emphasis feel denser.
- Group related sentences into one visual event only when they share a message. For short videos, 1–3 complete sentences can form a group; two is a useful default when the timing and meaning fit.
- Keep ordinary explanations restrained; distinguish supporting facts from core takeaways. Do not promote every brand, number, or technical term automatically.
- Do not change spoken meaning in the packaging layer. Display-only edits such as line breaks or approved shortening remain tied to the complete source sentence and require review.

### Dialogue-aware selection

- Read speaker and turn roles from the approved rough-cut/subtitle handoff. Treat a host preamble, the actual question, and the guest answer as separate semantic units unless the user explicitly approves another grouping.
- Select complete questions and answers according to the requested emphasis mode (`restraint` default, `qa_framing`, or `dense_coverage`). Under `qa_framing` keep selected questions and answers as separate key groups; the number of answer groups follows the material, never a fixed quota. Under `restraint` do not promote a unit because its sentence happens to be a question — the promotion reason must always be semantic. Modes share one rule: no unit is promoted for its sentence pattern alone.
- Use opening or ending theme groups when they serve the video's message. Review spacing between selected groups without adding emphasis solely to meet a fixed cadence.
- Record `group_kind`, `speaker_context`, and `sentence_count` in review artifacts. A group normally contains 1–3 complete sentences and should be labeled `句1/2` when it contains two.

For semantic categories, levels, grouping, and sound rationale, read [references/semantic-packaging.md](references/semantic-packaging.md).

## Layer support matrix

Not every layer in a finished video is writable through schema 2.0. Know which
route an operation takes before promising it:

| Layer | Route | Status |
| --- | --- | --- |
| Emphasis text, flower text, layout, same-screen retrack | schema 2.0 plan + `prepare`/`commit` | supported |
| Entry animation on plain text | plan `animation: {resource_id, duration_us}` + same-version capability evidence | supported; batch it with `expand-plan` |
| Sound effects tied to motion | plan `group.audio` + case catalog/pools | supported |
| Background music bed | plan `music[]` + fade/volume bands | supported (validate with `layer-audit`) |
| Overlay / B-roll (second video track) | editor `add_overlay` / `clone_asset` driver | driver route, needs a same-version prototype |
| Transitions, colour effects (`materials.effects`) | driver route only | **read-only audit today**; a plan field for these does not exist |

`layer-audit` reads music, transitions, overlays, effects and text from a
snapshot and reports mix/width violations. It never writes.

## Modes and workflow

- **analysis:** read-only audit; report observed text, layout, template, motion, transition, and sound issues.
- **staging:** prepare a reversible upper-track candidate; leave the original subtitle track unchanged and visible for review, and omit final sound/effect writes.
- **final:** prepare the approved visual/audio candidate after staging, subtitle authority, and remapping gates are satisfied.

Choose analysis by default; it is read-only and may run at any workflow state. Only an explicit packaging write request may enter `prepare`; prepare persists a candidate but does not write a draft. `commit` requires explicit approval of that candidate for the same plan and target. Do not ask again for an already authorized operation while its scope and target remain unchanged. Approval of a rough-cut plan or packaging plan alone does not authorize a draft write.

1. Confirm the current draft/timeline, saved state, requested scope, and authorization. If the requested operation is unclear, keep the work read-only.
2. To prepare a packaging plan, require `content_pass` to be `stable` or `approved` and `subtitle_alignment` to be `approved`. Before staging commit, require both states to be `approved`. Final also requires approved staging, an approved final-subtitle reference, and verified or not-required remapping. Read the final subtitles with neighboring context. Inspect the saved timeline through jianying-editor when the request requires draft evidence, compare it with the latest manual reference, and preserve manual choices unless the user asks for a change.
3. If a visual style or layout choice is still open, show a comparison preview. Let the user review selected sentences, grouping, timing, overlap, and obstruction before commit.
4. Group related text and graphic layers by perceptual event. Resolve layout from the approved subtitle transform and a verified reference; do not guess raw Jianying coordinates, color fields, or effect IDs.
5. Build a schema 2.0 plan. Use `validate plan` while iterating or when the user requests validation only. For a write-ready candidate, `prepare` performs the final plan and current-source validation; do not run `validate plan` again on the same unchanged plan immediately before `prepare`. When sound is in scope, supply the current case's verified `--catalog <case-catalog.json>` and `--pools <case-pools.json>`; missing inputs remain unresolved and never fall back to bundled assets.
6. Run `prepare` once with `--prepared temp/prepared.json`, `--format text`, and `--out temp/prepare-report.json`. This validates the plan and source snapshot, persists the candidate, hashes, changes, and preview under the skill's `temp/`, and does not write a draft. Keep the compact terminal summary in context, then read the saved report to obtain `prepared_artifact_hash` and the report and prepared-artifact paths for later review. For layout or animation changes, open the reported HTML preview and review its text bounds, safe zone, position, track, alpha, and duration. Record `review_report.visual_preview_status: "approved"` and the exact `visual_preview_sha256` in the plan. For animation plans, pass `--animation-cache-root` when cache discovery is ambiguous; include same-version capability evidence with `--animation-capabilities` and identify the running version with `--animation-version` when it cannot be detected. For sound, pass the current case `--catalog` and `--pools`; if current audio roles do not identify dialogue, supply `--existing-audio <dialogue-intervals.json>`.
When a sound or animation evidence gate blocks `prepare`, use its `input_errors` to identify the missing file/field, required JSON shape, and rerun command. Correct that input once; do not repeat `prepare` with unchanged evidence or fall back to bundled case assets.
7. Run `commit` only after the user approves that exact prepared-artifact hash and the required gates. Pass the hash from the prepare report as `--approved-prepared-hash`; do not reopen the artifact to recover the hash or rerun `prepare` while the plan and source snapshot remain unchanged. Commit reads and checks the approved artifact, plan, preview, and source snapshot before the clone-first transaction; it does not rebuild the candidate. Use `--format text --out temp/commit-report.json` to retain the full result while keeping the terminal summary concise. The HTML preview is geometry/timing evidence, not proof that Jianying retains or renders an effect. Reopen the result and complete visual/audio review. **A staging commit is not delivered until covered originals are resolved in the same pass**: with a standing user "复制即替换" instruction, disable the covered originals on the clone immediately (backup + read-back, report the disabled IDs); otherwise surface the pending decision explicitly. Never hand back a doubled staging view with no stated decision — see `references/staging-and-covered-subtitles.md` step 6b.

For a read-only evidence pass, capture the current timeline once with
`python <EDITOR_ROOT>\scripts\jianying_project.py inspect <draft> --timeline active --analysis-out <workspace>\temp\jianying-analysis.json`,
then run the five requested checks in one command:

```powershell
python scripts/packaging_tool.py audit-bundle --observation "<workspace>\temp\jianying-analysis.json" --format text --out "<workspace>\temp\packaging-audit.json"
```

The full JSON file contains each check and the source fingerprint; stdout is a
short summary. Reuse the report while the fingerprint is unchanged. An
unavailable evidence category blocks its check and must not be read as zero
events. For legacy observation files, the individual `snapshot`, `inventory`,
`layers`, `motion-check`, and `audio-audit` commands remain available and can
be batched in one shell invocation.

Keep each evidence, plan/review, and write/read-back round near a soft budget
of 50 tool calls. Save the current phase, source fingerprint, artifact paths,
and pending gates before continuing; do not rerun checks for unchanged inputs.
Use workspace `temp/` for case evidence and intermediate reports, and `outputs/`
for user-facing deliverables. `--prepared` remains in the packaging tool's
protected temp root for the transaction. A local project folder that the host's
present whitelist does not cover (an `AGENTS.md` working directory, a preview-card
directory, the draft volume itself) is not a delivery surface: copy the review
files into the conversation's `outputs/` before presenting them, or the user gets
an inert path instead of a card.

Sound is its own round: place SFX only after the layout/animation preview has been
approved and committed. Mixing audio with a geometry change in one write makes a
"the sound repeats" complaint impossible to separate from a position change, and
the audio plan has its own evidence gates (beat membership, reuse cap, measured
leading silence).

### Preview deliverable gate

Preview form and timing follow the workflow stage; never mix them.

- Rough-cut, transcript, speech-cut, and subtitle stages deliver text only — an
  SRT file or a line-by-line list. Do not generate a picture preview at these
  stages; a preview there is noise, not evidence.
- Only packaging-stage decisions get a picture preview, and the form depends on
  which decision is under review:
  - *Which sentences are key sentences* (selection, grouping, level, coverage):
    deliver the **emphasis-selection preview** — one self-contained dark HTML
    page listing every current subtitle row in time order, each carrying its
    group id, level, main-vs-reserve state, and profile/fragment/text-edit flags,
    so the reviewer can audit coverage and what was dropped rather than only the
    picks. This is a review list, not an animation. See
    `references/semantic-packaging.md` "Emphasis selection preview".
  - *How an approved group looks on screen* (flower text, position, angle):
    build it as one screen per group — a black-background frame card or a
    single-canvas HTML page — navigable by group number. Do not add a play bar
    or scrubber, and do not composite the reference clip behind the text; the
    reviewer is judging title layout, not motion.
- Every packaging write is preview-gated, including a "non-destructive" style-only
  pass that only changes color, font size, scale, or entry animation. Show the
  preview and take the user's approval before `prepare`/`commit`; never write
  first and backfill the preview afterward. This user-facing review card is
  separate from the tool-generated geometry HTML in step 6, which is commit
  evidence rather than the review deliverable.

### Simultaneous subtitle track handling

When two approved key sentences must remain visible together, keep both subtitle strings and text hashes exactly as approved. Let A be the earlier subtitle segment and B the later one. Keep A's start and extend its timeline duration through B's end; keep B's original start and duration. This changes segment timing, not text. On a final clone, extend A with `modify_segment` and an absolute `overrides.duration_us`; in a staging copy, use the exact-text copies' per-visual `start_us`/`duration_us`. Never use `modify_text` or shorten either sentence.

Because A now occupies its track through B's end, place B on a distinct upper text track for the overlapping interval. Preserve B's original target range and exact text/hash by setting its per-visual `start_us` and `duration_us` explicitly; do not let it inherit the wider group range. The adapter can create a text track from a verified text-track prototype for subtitle copies; for a final clone, realize the move by copying B to the upper track and disabling the covered original B row. Auxiliary text still follows the existing-topmost-track rule.

Set the group's range from A's start through B's end and mark it with `same_screen.enabled: true`, `extend_to_group_end: true`, and `overlap_policy: "separate_upper_tracks"`. A timeline track selects a lane and render order, not on-screen position; map the two exact text segments to separate approved layout slots so they remain readable together. Staging copies the exact subtitles and leaves source rows visible. In the approved final clone, hide only original rows fully covered by their exact-text copies. Never hide or alter source-timeline rows. Read back A's extended duration, B's preserved range, both track IDs, text hashes, and render order; if any mapping is ambiguous, stop for review.

`stable` can be used to prepare a review plan. Any staging or final commit
requires `source.content_pass: approved` and
`source.subtitle_alignment.status: approved`; final also requires approved
staging and verified/not-required remapping. The CLI enforces these status
gates. Only the Agent can confirm that the current conversation authorized the
write; `execution.mode=apply` does not create that authorization.

```powershell
python scripts/packaging_tool.py prepare `
  --draft "<draft-path>" `
  --timeline "<source-timeline>" `
  --plan "<schema-2.0-plan.json>" `
  --prepared "temp/prepared.json" `
  --catalog "<case-catalog.json>" `
  --pools "<case-pools.json>" `
  --existing-audio "<dialogue-intervals.json>"
```

After preview approval, commit the same unchanged plan and prepared artifact:

```powershell
python scripts/packaging_tool.py commit `
  --draft "<draft-path>" `
  --timeline "<source-timeline>" `
  --plan "<schema-2.0-plan.json>" `
  --prepared "temp/prepared.json" `
  --approved-prepared-hash "<exact-hash-approved-by-user>"
```

Final layout commits require numeric `layout.constraints.safe_zone` bounds
in normalized canvas coordinates and `project_profile.canvas_width`/
`canvas_height`. The adapter measures the current local font file from the text
material and blocks automatic layout if it cannot get reliable glyph metrics.
Relative layout changes require preview approval; position and alpha changes
are previewed as well. `global_alpha` is written only when the current text
segment prototype already carries that field. Hiding remains a separate
`visible` property. Auxiliary text must target an existing unique topmost text
track and must not overlap another segment on that track; commit never creates
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

## Phase and clone state

Use the shared `jianying-rough-cut/references/workflow-state.md` phase table for
approval gates and handoffs. Clone names must follow the active editor
workflow's naming convention; this reusable skill does not prescribe literal
project labels or suffixes.

When requesting a clone, preserve the source labels required by the active project's naming convention and give the copy a purpose-specific, unique name. The naming tokens and suffix format come from the active project/editor workflow; this skill does not prescribe literal sample names or a timezone.

### Stale-plan gate

A manual edit to the current saved timeline invalidates the previous plan and group report. Before staging or final execution, re-decode the source and target and compare at least the source/target hash, duration, subtitle-row count, group row ranges, visibility flags, and transform values. If any differ from the plan snapshot, rebuild the plan and review artifacts from the current saved timeline; never restore stale locators or the old selection.

## Review methods

Run these checks against the current saved timeline, not against an earlier exported SRT or plan.

1. **Selection review:** confirm group count, complete-sentence boundaries, speaker/turn labels, selected question and answer groups against the requested scope and emphasis density, opening/ending choices, and timing-gap balance. Present this as the emphasis-selection preview HTML (all rows, coverage, drop/reserve, flags) described in `references/semantic-packaging.md`.
2. **Text review:** compare every staged text hash with the approved subtitle reference; verify `句N/M` labels and that no semantic unit was rewritten.
3. **Same-screen review:** for each group inspect the first frame, the overlap start, a middle frame, and the final frame. Confirm A lasts through B's end, B keeps its approved start/duration on a distinct upper timeline track, both exact subtitle lines use separate layout slots, no text bounds collide, and manual transforms were preserved.
4. **Covered-subtitle review:** on the source timeline, originals remain unchanged. On an explicitly approved clone, only covered originals may be hidden; verify `visible=false` by read-back and by preview.
5. **Editor review:** run `jianying-editor validate`, verify every replica, source hash preservation, backup presence, and plan/read-back equality.
6. **Preview review:** use `jianying-preview frame` or `shot` at group start/middle/end. Stop on text mismatch, unexpected layer addition/removal, collision, obstruction, or a source-timeline change.

Record the selected review times, observed layer counts, source-to-target track assignments, target intervals, backup path, and any unresolved speaker/listening issue in the review report.

## Motion, sound, and review gates

- Keep motion traceable to a user-approved template or verified source, and vary among reference-backed choices within the plan reuse cap. Do not invent support for raw properties from field names alone. Reuse caps by role: `uniform_entry` (one resource, same duration, first row of each group) has **no count limit** but must use a single resource id across the whole plan; `emphasis` is capped at **2 uses per resource per region**, with no adjacent repeat and no A-B-A run.
- Treat each perceptual motion beat as an event. Co-timed layers share one event and normally one primary sound; separate entrances or moving marks are separate events.
- Match sound to event meaning and motion. Follow the task's full/selective coverage and repetition policy; do not infer coverage from segment/audio counts. Pick the anchor policy per event, not globally: a per-row entrance anchors on the animation **start** (a 200–400 ms fade has no independent perceptual landing), a one-shot transition anchors on its **midpoint**, a scale/impact hit anchors on the **peak**, and an overlay entering the frame anchors on the layer start. Record `anchor_policy` and `anchor_basis` for every audio event. Account for measured leading silence either way.
- Sound reuse default is **2 uses per preset** (`sound_selection.reuse_cap` defaults to 2 in both the validator and the sound check), with no repeat on the adjacent beat and none two beats away. Raising it requires a recorded reason per event.
- Background music is its own layer: place it through `music[]`, keep it inside the mix bands, and always fade it in and out. Dialogue is never ducked for music on an interview.
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
- Template capabilities and provenance: [references/capability-audit.md](references/capability-audit.md) and [references/flower-text-templates.md](references/flower-text-templates.md). A valid capability file shape is at [references/animation-capabilities.example.json](references/animation-capabilities.example.json); `validate capabilities` checks it and `animation-inventory` proposes candidates.
- Discovering animatable assets or sound candidates on this machine: `animation-inventory` and `catalog-harvest` (bounded to explicitly supplied reference drafts).
- Plan fields, gates, and validation behavior: [references/plan-schema.md](references/plan-schema.md).
- Sound choice, trim, and synchronization: [references/semantic-packaging.md](references/semantic-packaging.md) and [references/motion-audio-audit.md](references/motion-audio-audit.md).
- State gates and write authorization: always read [references/workflow-state.md](../jianying-rough-cut/references/workflow-state.md) before staging or final execution.
- Changed timeline order: read [references/timeline-comparison.md](../jianying-rough-cut/references/timeline-comparison.md) and verify semantic remapping before reusing earlier timing.

Read-only analysis and prepare commands do not write drafts. Schema 2.0 commits go through this Skill's `commit` adapter and the existing jianying-editor transaction API; encryption, backup, replica, read-back, and rollback primitives remain in jianying-editor. Schema 1.2 and older plans and the legacy `apply`/`preflight` commands are unsupported.
