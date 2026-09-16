# Evidence-based capability audit

This audit separates demonstrated operations from schema observations and requested future capability. Its entries are project- and version-scoped evidence from the Jianying packaging scripts and backup manifests in `D:/Users/11/Documents/ChatGPT/jianyin`, the active timeline of `E:/JianyingPro/JianyingPro Drafts/9月14日 (1)`, and the existing `jianying-rough-cut`, `AI剪口播`, and `jianying-editor` skills. Re-confirm each capability against the current draft and prototype before execution; an observed field or an older audit is not a universal support guarantee.

## Demonstrated packaging operations

| Capability | Evidence | Reusable abstraction |
|---|---|---|
| Clone a source timeline and activate/name the copy | flower-text scripts created derived timelines while retaining the source | `source_timeline`, `target_timeline_name`, `preserve_source` |
| Build text groups from current subtitle boundaries | corrected flower-text scripts replaced rounded seconds with saved subtitle segment boundaries | semantic group with phrase anchors and exact microsecond ranges |
| Reuse flower/question templates | scripts located template timelines and copied prototype segments | `preset_id`, `template_source`, `prototype_segment_id` |
| Copy complete referenced material closure | flower-text and sound-correction scripts traversed material references and remapped IDs | generic closure copy with exact-reference replacement |
| Replace visible text without losing style | scripts updated text plus style ranges; later ordinary-style correction synchronized `content` and `base_content` | synchronized text mirrors and range repair |
| Apply an ordinary style from a user-made reference | first saved subtitle was used as the prototype for font, size, shadow, and normalized Y | `inherit_from_segment` plus minimal overrides |
| Preserve covered subtitles non-destructively | an earlier project pass set covered subtitle segments invisible, but this was not stable across versions | `covered_subtitle_policy: preserve` on source/staging; clone-only disable/delete after read-back and approval |
| Correct multi-layer question composition | question mark was moved to the lowest group layer and aligned to the second phrase | group-level layer/timing constraints |
| Reuse existing sound assets | sound scripts cloned existing target audio segments by material name | `reuse_existing` sound action |
| Import sound from another draft/subdraft | correction script copied a source sound segment and full material closure | `clone_asset` with explicit source locator |
| Avoid duplicate sound events | scripts skipped an insertion when an existing start was within tolerance | perceptual-event deduplication |
| Add sound based on animation/content meaning | the corrected sound pass changed from two repeated sounds to differentiated mechanical, click, prompt, impact, sweep, and CTA choices | motion family + semantic function + rationale |
| Validate and read back changes | scripts and backup manifests show pre/post validation, replica backup, atomic replacement, and read-back | delegated `jianying-editor` transaction |

## High-frequency operation families

1. Resolve current timeline and its exact segment/material graph.
2. Select a current manual segment or template segment as a prototype.
3. Clone the segment and referenced materials with new IDs.
4. Override text, timing, position, visibility, or volume while preserving the rest.
5. Create or reuse a suitable track and keep segments ordered and non-overlapping.
6. Compare with existing events to avoid duplication and preserve manual edits.
7. Validate candidate, write safely, decrypt/read back, and validate again.

These are one family of operations parameterized by object type, prototype source, time anchor, track/layer target, and allowed overrides. They should not be reimplemented as one script per sentence.

## Failures and corrections that change the design

- Rounded plan timecodes caused visible offsets. Use exact current subtitle, waveform, animation, or transition boundaries.
- Copying only obvious top-level text fields did not reproduce the Jianying UI style. `content`, `base_content`, nested style arrays, and top-level compatibility fields may all participate; cloning a confirmed prototype is safer.
- Replacing text without updating all style ranges caused missing characters or uneven styling. Recalculate ranges after every replacement.
- Regenerating from an older timeline overwrote manual corrections. Diff the current user-confirmed timeline and patch incrementally.
- Treating every animated text layer as a sound event produced repetitive sound design. Model one sound event per semantic animation group and require a rationale.
- Question punctuation is a composed layer, not part of ordinary text. Its track order and phrase-aligned start must be preserved.
- File values and UI values may use different coordinate/scale systems. Infer conversion from a user-set reference and verify visually.

## Observed but not demonstrated as stable packaging execution

- The active draft exposes video `clip.scale`, `clip.transform`, `flip`, material `crop`, transition materials, and referenced animation materials.
- The older wrapper documents media import and keyframes, but the current project has no keyframes and the packaging scripts did not successfully exercise rotation, opacity, mask, feather, blend, freeze, or custom keyframe editing.
- The active timeline has no sticker track. Standalone sticker/PNG animation behavior was not validated here.
- Audio fade materials exist in the draft schema, but the packaging scripts only demonstrated segment placement, duration, source range, and volume changes.

For these operations, prefer cloning a working template object and run a visual read-back test. Mark unsupported property-level edits as experimental until verified.

## Responsibilities outside this skill

- Topic understanding, filler removal, pause trimming, repetition removal, speaker/Q&A detection, and rough-cut structure belong to `jianying-rough-cut` or `AI剪口播`.
- Encryption detection, layout/version compatibility, active timeline resolution, replica association, backups, atomic write-back, validation, and rollback belong to `jianying-editor`.
- Transcription and subtitle word timing are evidence inputs, not packaging capabilities.
- Exporting/rendering is a separate delivery operation unless explicitly requested.
