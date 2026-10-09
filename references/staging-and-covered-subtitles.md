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

## Track copy and disable mechanics

- Deep-copy each copied segment's text material under a new UUID and repoint `material_id`; a copy that shares the source material pollutes color/animation edits on the original.
- Clear `extra_material_refs` on copies; motion is attached later per the approved packaging plan.
- When a copy's tail is extended (hold) into the next sentence's span, same-track time overlap will fail validation. Split alternating sentence positions across two upper tracks (e.g. sentences 1/3 on one track, 2 on the next).
- Locate segments by `(track_id, start_us)`, never by text keyword: the subtitle track contains identical wording and will silently mismatch.
- Disable the covered original segments with the editor-native per-segment `"visible": false` flag (what the JianYing eye-icon toggle writes; verified on 11.5). `clip.transform.x = 99` (move off-canvas) is a reversible fallback only when the native flag is unavailable; it changes the stored display position and users may reject it. Track-level `is_hide` and `global_alpha = 0` do not work for text in 11.5. Never delete.
- Group layout defaults: the group's last sentence stays pinned at the subtitle line position; only sentences that temporally overlap an earlier held sentence are raised. A stacked line step of about `0.10` normalized units fits font size 10; `0.16+` reads as too far apart. Let the user's manual corrections set the final rule and copy their measured values. These tiers are scaffolding: once the user fine-tunes per-line positions, later passes must preserve each adjusted value and never re-flatten the group back to uniform steps.
- Left/right staggered pairs are geometrically bounded: at font size 10 each CJK glyph is roughly `0.15` normalized x-units (calibrate from a screenshot). Two simultaneously visible lines can be side-by-side only while their combined character count stays within the canvas safe width (about 12 glyphs at fs10); beyond that keep the group centered.

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
