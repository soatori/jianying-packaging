# Packaging staging and covered subtitles

Packaging starts from an approved content pass and an approved subtitle-alignment plan. It first creates a reversible working timeline and an upper review layer.

This document also carries the text-track copy/staging operations formerly owned by a standalone `jianying-track-copy-staging` skill (now merged here). All project I/O still delegates to `jianying-editor`.

## Staging sequence

1. Ask where the staging surface belongs: the current working timeline (in-place, with backup) or a fresh clone. The clone is the safe default, but users often review only the timeline they had open and will report "nothing changed" when staging landed on a clone they never opened. Record the answer before writing.
2. Clone the source timeline through `jianying-editor` (when a clone was chosen).
3. Keep the source subtitle track unchanged and visible.
4. Copy complete candidate sentences to an upper track, preserving the approved sentence segmentation. Use phrase-, word-, or character-level fragments only when the user explicitly requests that granularity.
5. Mark `packaging_staging=reviewing` and let the user review emphasis, wording, timing, segmentation, overlap, and obstruction.
6. Record any user edits against the current saved staging timeline.
7. Only after review approval apply templates, motion, effects, transitions, color, transform, background, and sound.

## Phase-specific covered-subtitle policy

| Surface | Default | When it may change |
|---|---|---|
| Source timeline | `preserve`, visible, unchanged | Never disable or delete to make an overlay look correct |
| Staging clone before approval | `preserve`, visible, unchanged | Record the candidate coverage only |
| Staging clone after explicit approval | covered originals may use `"visible": false` | Require backup, read-back, and preview confirmation |
| Final clone after approved staging | follow the approved `covered_subtitle_policy` | `delete` still requires explicit approval and backup |

The phase controls the operation. Copying a sentence to an upper track does not by itself authorize hiding the source; the user must approve clone-only disabling after reviewing the overlay.

## Plan-level operation contract

A packaging plan may request two editor mutations; packaging records the approval and acceptance criteria, while `jianying-editor` only translates them:

- `clone_only_disable_covered_originals`: explicit authorization is required; target a clone only; hide the approved covered segments individually; never alter or hide the source timeline or source subtitle track.
- `same_screen_retrack`: use approved group end times; extend and move only approved segments; record the source and destination track for every moved segment; preserve text, material, style, and manual transforms; require zero same-track overlap.

Before either mutation, re-decode the current saved source and target and compare the plan snapshot. Require a pre-write backup, unchanged source hash, validated replicas, read-back equality, and a report containing the backup path, changed segment IDs, track IDs, visibility flags, and validation results. Stale locators or manual-edit drift are stop conditions.

## Track copy and disable mechanics

- Deep-copy each copied segment's text material under a new UUID and repoint `material_id`; a copy that shares the source material pollutes color/animation edits on the original.
- Clear `extra_material_refs` on copies; motion is attached later per the approved packaging plan.
- When a copy's tail is extended (hold) into the next sentence's span, same-track time overlap will fail validation. Split alternating sentence positions across two upper tracks (e.g. sentences 1/3 on one track, 2 on the next).
- Locate segments by `(track_id, start_us)`, never by text keyword: the subtitle track contains identical wording and will silently mismatch.
- After explicit user approval, disable only the covered original segments on the clone with the editor-native per-segment `"visible": false` flag (what the JianYing eye-icon toggle writes; verified on 11.5). Require backup, read-back, and visual confirmation. `clip.transform.x = 99` (move off-canvas) is a reversible fallback only when the native flag is unavailable; it changes the stored display position and users may reject it. Track-level `is_hide` and `global_alpha = 0` do not work for text in 11.5. Never delete, and never disable the source timeline.
- Group layout defaults: the group's last sentence stays pinned at the subtitle line position; only sentences that temporally overlap an earlier held sentence are raised. A stacked line step of about `0.10` normalized units fits font size 10; `0.16+` reads as too far apart. Let the user's manual corrections set the final rule and copy their measured values. These tiers are scaffolding: once the user fine-tunes per-line positions, later passes must preserve each adjusted value and never re-flatten the group back to uniform steps.
- Left/right staggered pairs are geometrically bounded: at font size 10 each CJK glyph is roughly `0.15` normalized x-units (calibrate from a screenshot). Two simultaneously visible lines can be side-by-side only while their combined character count stays within the canvas safe width (about 12 glyphs at fs10); beyond that keep the group centered.

## Same-screen group layout

For a reviewed group whose last text ends at `group_end`:

1. Set every copied segment in that group to `target_timerange.end == group_end` while preserving its start, text, material, style, and manual transform.
2. Treat each extended segment as a timeline interval. If two intervals overlap on the same upper track, move the later segment to another upper review track; never enable same-track overlap.
3. Reuse a previous upper track only when its last segment ends before the next segment starts. Create another upper review track when no previous track is free.
4. Leave the source subtitle track untouched. Record `group_id`, `group_end`, assigned `track_id`, and whether each segment moved.
5. Validate before write: all group ends match, all upper segments are visible, same-track overlap is zero, text/material IDs remain unique, and the source track hash is unchanged.
6. After write, re-decode and inspect group start/middle/end frames. Stop if the expected simultaneous lines are missing, collide, obstruct the subject, or if a manual transform changed.

## Staging review checklist

- Re-read the current saved staging timeline; treat any hash, duration, row-count, visibility, or transform change as a stale-plan condition.
- Compare the selected group rows with the current upper tracks; record manual additions, removals, merges, and splits.
- At each group start/middle/end, verify the complete text, `句N/M` label, safe area, subject obstruction, and expected layer count.
- Verify same-track overlap is zero and that moved segments are on the recorded upper tracks.
- Verify the source timeline still has the original subtitle text and visibility. Verify clone-only hides with both read-back and preview.
- Confirm the backup path, replica validation, source hash preservation, and an `ir-diff`/frame comparison with no unplanned changes.
- Stop on stale locators, text mismatch, collision, source mutation, missing backup, or an unresolved speaker/listening issue.

## Editor state and write-back pitfalls

- JianYing does not hot-reload a draft file. After any write, the user must return to the draft list (or restart) and reopen; saving from a stale editor session overwrites the write.
- A running JianYing rewrites draft replicas (content hashes change). Re-decode the current saved timeline at the start of every pass; never reuse a decoded snapshot or locator cache.
- To discover what the user changed manually, diff a pre-write backup against the current primary: JianYing rotates `.bak` and primary to the same hash on each save, so `.bak` vs primary shows nothing.
- `_write_content` flushes before validation. If validation fails, the bad structure is already on disk: remove the offending track/object and rebuild in a follow-up transaction rather than assuming a rollback occurred.

During a read-only analysis request, do not create the clone or staging layer. Report the observed template, motion, transition, and sound behavior only. A staging plan may describe candidate visual treatment, but it must not add final templates or sound effects.

## Final-subtitle and remap gate

Packaging text always comes from the approved final-subtitle reference. ASR and older text fields are discrepancy evidence only. Each group carries a semantic-unit reference, subtitle anchor, source/target order fingerprints, and `remap_status`. If source and target order differ, old timestamps are not reusable until semantic remapping is `verified`.

This staging layer is not a semantic second rough cut. It is a visual review surface. If the text is factually wrong, the unit should be returned to `jianying-rough-cut`.

## Covered subtitle policy

The default is `preserve` on the source and staging timeline. `enable=false` is not a success criterion because some Jianying versions continue rendering the segment.

Allowed final-target policies are:

- `preserve`: leave the original visible;
- `disable_after_readback`: try disabling only on the clone and require read-back/visual confirmation;
- `delete_on_clone_after_approval`: delete only on the clone with explicit authorization and a backup;
- `review`: stop for manual handling.

Never delete or disable the source timeline merely to make an overlay look correct.

## Duplicate rules

Use start-time overlap within ±40ms and do not require identical text. A cross-track duplicate can be covered or removed on the clone after review. A same-track continuation, such as an animated first segment followed by an unanimated continuation, remains in place.
