# Packaging staging and covered subtitles

Packaging starts from an approved content pass and an approved subtitle-alignment plan. It first creates a reversible working timeline and an upper review layer.

## Staging sequence

1. Clone the source timeline through `jianying-editor`.
2. Keep the source subtitle track unchanged and visible.
3. Copy candidate sentence, phrase, word, or character text to an upper track.
4. Mark `packaging_staging=reviewing` and let the user review emphasis, wording, timing, segmentation, overlap, and obstruction.
5. Record any user edits against the current saved staging timeline.
6. Only after review approval apply templates, motion, effects, transitions, color, transform, background, and sound.

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
