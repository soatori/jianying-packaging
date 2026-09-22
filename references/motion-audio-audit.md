# Motion and audio audit contract

Packaging observations may provide `tracks`, `motion_events`, and
`audio_events` without exposing a Jianying schema. The read-only audit tools
use these relationships:

- `layers`: discover baseline, emphasis, auxiliary, and continuation layers
  from explicit roles or relative render order; never assume a fixed count;
- `motion-check`: partition playback into content regions, then flag adjacent
  reuse of the same motion family only inside one region. It accepts
  `content_region_id` and the legacy `semantic_region`, and can start a new
  inferred region at an explicit section/content boundary. Different regions
  are never compared as a whole-film duplicate set. A shared non-empty
  `motif_id`, or `intentional_motif` on both events, exempts the pair; static
  continuation is not a missing animation;
- `audio-audit`: classify event roles separately as `sfx`, `music`, `ambience`,
  `dialogue`, or `unknown` so background music does not inflate SFX reuse and
  unclassified events remain visible for review;
- `sound-check`: validate motion event anchors, sound form, trim span, leading
  silence, candidate-pool evidence, reuse caps, and dialogue collision.

These reports are evidence for review. They do not select assets or write a
Jianying draft.
