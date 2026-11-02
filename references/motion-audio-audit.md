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

For a saved `jianying_timeline_observation@1`, use
`packaging_tool.py audit-bundle --observation <workspace>/temp/jianying-analysis.json`
to run snapshot, inventory, layer, motion, and audio checks in one process. Use
the individual commands only when the request needs a narrower check.

The schema 2.0 `prepare` phase also checks dialogue collisions before a sound
write. It derives intervals only from recognized current-draft audio roles; if
those roles do not identify dialogue, supply explicit intervals through
`packaging_tool.py prepare --existing-audio <dialogue-intervals.json>`. Missing
dialogue evidence blocks final sound operations before commit.


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

## Candidate-pool evidence gates

Build candidate pools from the current readable primary timeline and only the
reference drafts explicitly supplied for the current case. If the current-case
catalog or pools are missing, leave sound selection unresolved and request them.

**Bounded discovery is allowed; unbounded scanning is not.** `catalog-harvest`
and `animation-inventory` may read reference drafts, but only those named
explicitly for this case, at most five, capped at 200 items, with the scanned
timeline ids recorded as provenance. Never enumerate every saved draft, never
scan a whole drive, and never treat a machine-wide sweep as "just looking".

Everything harvested starts as `unverified`. A path existing on disk proves the
asset was downloaded once; it does not prove it renders on this version, in this
composition, with plain text. Keep source-specific names, IDs, paths, and
timecodes in the external case catalog and pools. Record evidence separately; one
check does not stand in for another.

| Evidence | Establishes | Does not establish |
|---|---|---|
| Primary timeline decodes and parses | The observed event and material records can be read | That referenced media is present or renders |
| Referenced media exists and a media probe parses it | Container/codec metadata and stream presence | Full-stream integrity, semantic fit, audible quality, or correct visual behavior |
| A full decoder pass succeeds | The referenced media payload can be read through its duration | Semantic fit, audible quality, or correct visual behavior |
| Entry, peak, and exit preview checked | The motion family and dynamic readability at sampled points | Native Jianying playback or sound quality |
| Waveform and listening review completed | Audible onset, duration, masking, and dialogue fit | That another project or version will render identically |
| Current project reopened in Jianying and reviewed | Presentation and playback in that project/version | Suitability for every future case |

Reject a candidate whose primary content is unreadable or whose role-specific
media closure is missing or cannot be decoded. A missing video blocks using a
timeline as a visual/motion source; it does not by itself invalidate a separate
SFX asset whose own file passes a full decode. Keep that asset audio-only and
provisional until listening review. Keep a readable primary with replica/backup
drift, placeholder animation labels, or no listening review provisional; do not
use it as a verified template or final-apply candidate. File health alone never
promotes a sound to verified. Deduplicate SFX by the source preset/resource
identity, not by repeated timeline clips or segment IDs.

## Beat grouping and reuse cap

- A beat is a **screen**, not a cue. Decide same-screen membership by interval
  overlap: compare each candidate sound's text interval with the visible interval
  of every box on that screen; any overlap means one beat, one sound. A
  proximity/gap threshold (e.g. "merge events closer than 300 ms") is wrong — the
  two boxes of a group are routinely 0.3–0.7 s apart, so gap clustering splits one
  screen into two beats and stacks two sounds on the same perceptual moment.
  Verify by comparing screen count with sound count (e.g. 22 screens → 22 sounds);
  a plan with more sounds than screens has a membership bug, not a denser design.
- Default cap until the current task says otherwise: at most 2 uses per preset; no
  repeat on the adjacent beat and none two beats away (an A-B-A run reads as a
  glitch). An approved motif may override, recorded per event. A looser rule
  (≤4 per preset, one sound per line) has already been rejected by the user as
  "too repetitive"; do not reintroduce it as a default.
- The code default must match this document: `sound_check.reuse_cap` and
  `plan_impl` both default to **2**. A plan that omits `sound_selection.reuse_cap`
  is checked at 2, so a third use fails without any extra configuration.
- Deduplicate by **preset identity and file path**, not by display name. Two
  differently-captured sounds can share a name ("swish" ×2); conversely one file
  can appear under two names. Both count as a repeat.

### Animation reuse cap

Motion has a cap too, and it is role-dependent:

| `motion_role` | Cap | Conditions |
| --- | --- | --- |
| `uniform_entry` | no count limit | one `resource_id` and one duration family across the whole plan; applies to the first row of each group |
| `emphasis` | 2 uses per resource per region | no adjacent repeat, no A-B-A run |

Mixing the two roles in one plan is allowed, but a `uniform_entry` resource may not
be reused as `emphasis` (and vice versa) — the audience reads it as the same
animation doing two different jobs. Batch entry animations with `expand-plan`, which
fills the per-visual `duration_us` from the visible row window.

## Layer audit

`layer-audit` reads a snapshot (tracks plus materials) and reports what the
finished composition actually contains. It is the only way to check layers that
schema 2.0 cannot write.

| Layer | What is checked | What is **not** possible |
| --- | --- | --- |
| Music | count, ranges, volume band, fade in/out presence | writing a bed through a plan `groups[]` entry — use `music[]` |
| SFX | count, total duration, volume band | inferring coverage from the SFX count alone |
| Transitions | name, duration (≤600 ms), `is_overlap` | writing transitions — no schema 2.0 field exists |
| Overlays (extra video tracks) | track index, segment count, total duration | planning an overlay through this skill's plan; use the editor driver |
| Effects / colour | material count | reading effect parameters as if they were verified capabilities |
| Text | row count, animated rows, line widths, residual punctuation | re-breaking a line — that belongs to `subtitle-reflow` |

Violations are aggregated per rule with a count and up to three samples. A single
rule affecting 48 segments reports once, not 48 times: the number that matters is
"this rule is violated", and the count tells you the blast radius.

Reading a layer is not permission to write it. A transition or effect found in a
reference video is evidence that the reference has it, not that this skill can
reproduce it.

## Machine-readable layout of the observation

`layer-audit`, `animation-inventory`, and `catalog-harvest` all consume the same
plain snapshot shape, produced outside this skill (by the editor's inspect step):

```json
{
  "timeline_id": "<id>",
  "duration_us": 0,
  "tracks": [{"id": "<id>", "type": "video|text|audio",
              "segments": [{"id": "<id>", "material_id": "<id>",
                            "target_timerange": {"start": 0, "duration": 0},
                            "volume": 1.0, "visible": true,
                            "extra_material_refs": []}]}],
  "materials": {"audios": [], "texts": [], "material_animations": [],
                "audio_fades": [], "transitions": [], "effects": []}
}
```

Missing keys are treated as empty; the auditors never fail because a track type
is absent.
