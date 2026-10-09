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


## Event-level animation-to-SFX coverage

Role classification and sound-operation checks do not prove that each rendered
animation has the intended sound. Before final review, build an event-level
coverage matrix from the current saved timeline and the approved packaging
scope. Do not infer coverage from matching counts of text segments and audio
clips.

| Field | Record |
|---|---|
| `event_ref` | Stable reference for one perceptual motion beat |
| `content_region_id` | Playback-local region used for repetition checks |
| `member_refs` | Text, mark, or graphic layers that share this beat |
| `motion_event` | Start, perceptual peak, and end when known |
| `coverage_policy` | The task's full or selective coverage requirement |
| `sfx_ref` | Matching audio event and verified source-preset identity, if any |
| `audible_anchor` | Intended perceptual point and measured audible-onset offset |
| `decision` | Covered, intentionally silent with rationale, or unresolved |

Build and review the matrix with these rules:

1. Enumerate rendered motion events, not raw text-segment or audio-clip totals.
   Co-timed layers on the same beat share one event; a later entrance, separate
   transition, or independently moving mark is another event.
2. Match sound to the event's meaning and motion, then align audible onset to
   the intended anchor. Source trimming and target placement are separate; use
   the onset calculation in [semantic-packaging.md](semantic-packaging.md#synchronization).
3. Count only `sfx` toward SFX coverage. `music`, `ambience`, and `dialogue`
   remain separate; `unknown` requires review. List required motion events
   without a sound and SFX events without a matching motion event.
4. Apply the coverage requirement and repetition window supplied by the task.
   Compare verified source-preset/resource identity, not timeline segment or
   material IDs. Keep repetition checks inside the declared content scope and
   apply only an explicit motif exception.
5. Record intentional omissions and unresolved matches separately. If full
   coverage was requested, any unexplained gap blocks the audit; if selective
   coverage was requested, an omission needs its semantic rationale.
6. Use waveform evidence for onset and duration, and listening review when the
   audible attack, masking, or dialogue collision is uncertain. A count match
   or plan-only anchor is not a perceptual pass.

`audio-audit` classifies existing audio roles and `sound-check` validates
planned sound operations; neither establishes event coverage for every
animation in the current timeline. Keep the matrix as a separate read-only
audit result.
