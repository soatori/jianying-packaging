# Semantic emphasis and sound design

## Subtitle format profile (preflight, before emphasis selection)

Vertical (9:16) delivery uses one standing text profile. It is a format
convention, not a single project's copy, so it may live here; a project that
overrides it keeps the override in its own external case reference.

For `canvas_width < canvas_height`, every approved subtitle line must satisfy:

- One sentence per line. A punctuation-triggered break starts a new line; lines
  are separated by `\n` inside the text material, and one screen never carries
  two sentences.
- No punctuation survives. `。`, `，`, `！`, `？`, `；`, `：`, `……` are split
  triggers only and are deleted after splitting; nothing is left at a line end.
- No unsplit long run. Punctuation-free text longer than the limit must be
  force-split on a real pause or a complete-token edge — never by character
  count alone, and never allowed to wrap by itself.
- At most **13** Chinese characters per line by default; `--profile
  vertical_standing` drops it to **10** for a stricter standing-title look. The
  limit has exactly one source of truth: a case reference may override it, and
  both `subtitle-reflow --max-chars` and `layer-audit --max-chars-per-line` must
  read the same value. Count it programmatically and print each line's length next
  to its verdict — eyeballed counting misreports in both directions, and a
  14-character line will read as "13, fine" on screen.
- Modal particles stand alone: `嗯`, `啊`, `欸`, `哦`, `呢`, `呐` each get their
  own line and are never merged into the neighbouring sentence or dropped.

Example: `今天天气真好啊我们去公园玩吧你说好不好呢` →
`今天天气真好` / `啊` / `我们去公园玩吧` / `你说好不好` / `呢`.

Preflight behavior:

1. Check the current saved subtitles against this profile **before** reading any
   group, so emphasis units are counted on correctly broken lines. A line that
   still contains punctuation or exceeds 10 characters is a profile violation,
   not an emphasis candidate.
2. Packaging never repairs the violation itself. Rewriting line breaks here
   would silently consume an upstream segmentation problem; record the offending
   rows and set `needs_rough_cut_review`, which returns the work to the subtitle
   owner. Horizontal (16:9) delivery is not covered by this profile and keeps
   its own case rule (typically a two-line title fold that preserves the final
   `？`), so never generalize these five bullets across orientations.
3. Any approved re-line breaking must sync `styles[].range` to the new text
   length including `\n`; a stale range is a silent color/stroke truncation. The
   display copy is still one of the subtitle's three text fields; when emphasis
   requires re-lining, the three-field agreement rule in
   `jianying-rough-cut/references/subtitle-proofreading-and-audio-alignment.md`
   still applies — `recognize_text` and `words[].text` keep the ASR original when
   a human only retyped `content.text`, and that stale copy resurfaces as soon as
   a per-character animation or "update recognition" runs.

## Context-first emphasis

Evaluate each complete sentence with the previous and next sentence, the current topic, and the video's communication goal. Subtitle rows are timing containers, not necessarily semantic groups.

The default emphasis unit is a complete sentence. Preserve the sentence as supplied in the current subtitles. Highlight a word, character, or within-sentence fragment only when the user explicitly requests that granularity. Do not fragment a sentence just to increase the number of highlighted elements.

For short videos, group one to three complete sentences when they share a message; two is a useful default when timing and meaning fit. Group size controls the composition, not the unit of text selection. Follow any explicit user grouping.

### Emphasis density modes

Density is a **mode**, not a per-run guess. All three modes share one rule: a unit
is promoted because of what it says, never because of its sentence pattern, its
word frequency, or a cadence target. `semantic_basis` must be non-empty on every
selected unit in every mode.

| Mode | When it applies | Behaviour |
| --- | --- | --- |
| `restraint` (default) | no explicit density instruction | 1–3 groups per topic, supporting facts stay plain; a question is not promoted just because it asks something |
| `qa_framing` | the brief asks for a question-and-answer structure | every genuinely asked question may become its own group, answers are selected as separate groups; **the number of answer groups follows the material, never a fixed quota** |
| `dense_coverage` | the brief asks that every retained row carry emphasis | coverage is the goal; still no promotion on sentence pattern alone, and still record a reason per unit |

Under `qa_framing`, a question that is dropped from emphasis must appear in the
selection preview's dropped list with a reason — "it is a question" is not a
reason to include it, and "it is only a question" is not a reason to drop it.

### Dialogue-aware groups

Multi-speaker dialogue is grouped by turn function, not by adjacent subtitle rows alone.

- Keep the host/guest speaker ID, turn role, and confidence with each semantic unit. If the speaker is inferred rather than heard, mark it for listening review.
- Keep each question and answer as a separate complete semantic unit. When the request calls for question-and-answer emphasis, select the questions and answers that fit the requested scope and density; do not automatically promote every question or impose a fixed answer-group count.
- Do not prepend host setup or append the answer to a question group unless the user explicitly approves that composition. Record selected answers separately as `answer` groups.
- Do not treat repeated technical nouns or a long preamble as emphasis merely because they precede a question.

Good emphasis candidates include:

- decisive product, brand, or technical names;
- numbers together with units, ranges, and conditions;
- conclusions and the premise that makes them true;
- contrast, correction, warning, risk, or unusually strong degree;
- a complete question sentence needed to frame an answer;
- one memorable CTA when it serves the video's goal.

Do not emphasize an isolated word merely because it is frequent, visually convenient, or already has an animation. Avoid highlighting every noun or every sentence.

## Category and level

Recommended categories:

- `question`
- `core_point`
- `number_parameter`
- `product_brand`
- `technical_term`
- `risk_warning`
- `conclusion`
- `contrast_turn`
- `emotion`
- `cta`
- `transition`
- `ordinary_explanation`

The same semantic categories may be expressed through the rough-cut roles `hook`, `background`, `question`, `reaction`, `answer`, `evidence`, `technical_detail`, `contrast`, `benefit`, `summary`, and `cta`. Packaging uses the role as context; it does not rewrite the text.

Use level 1 for supportive emphasis, level 2 for important information, and level 3 for only the few ideas the viewer must remember. Level changes intensity; it does not change meaning.

## Grouping

- Group 1–3 complete sentences when they share one idea; two is a useful default when timing and meaning fit. If subtitle rows split a sentence, the whole sentence remains the emphasis unit. Group size controls visual composition, not text granularity. Yield to the user's confirmed grouping.
- One semantic idea can span one or more text layers.
- A two-line group should share one meaning and one overall visual landing point.
- Preserve the original start of each spoken phrase unless an approved template intentionally stages the phrases.
- Do not merge unrelated lines to fit a template.
- Treat punctuation, labels, icons, and background shapes as subordinate layers of the same group.
- A key-sentence set must cover each retained segment's opening line and its core line, so the preview reads as the segment's spine; a segment with no selected line is a selection gap, not an intentionally quiet segment.
- Cap one screen at 1–2 lines and never more than 3 short lines. More than that is a grouping error to split into another event, not a denser screen.
- When emphasis lines are copied onto an upper track they inherit the caption baseline. Anchor the first/single line on that baseline and move apart only the lines that genuinely overlap in time, by the reference-derived row spacing; for dense multi-name groups prefer a two-column block near the safe-zone edge over an ever-taller single stack.
- Express level with scale, not with font size. Keep one size across the whole package (verify the number in the project reference; the observed engineering size stays constant within a draft) and separate L1→L3 with `uniform_scale` steps taken from the verified reference, e.g. a monotone ladder of about 1.04/1.06/1.08/1.10/1.25. Mixing sizes per line makes the safe-zone fit and the reference comparison unstable.
- Inside a group, use at most one strong accent: the landing sentence carries the accent color, the setup lines stay white or a lighter accent. A pure question group may legitimately stay all-white. Two lines of the same group in the same strong color reads as an error even when each line is individually correct.

### Opening, ending, and spacing

- The opening group must expose the video's subject or mechanism; the ending group must expose the final benefit, risk, consequence, or call to action.
- After required question and answer groups are selected, compare each remaining key group with the previous and next selected group. Large clusters and long empty runs both require review; adjust selection or grouping before applying motion.
- Preserve the user's confirmed group boundaries. A manual split, merge, retime, or transform supersedes an earlier generated group report.

### Review record

Each reviewed key group should be exported with:

- group ID and `group_kind` (`question`, `answer`, `opening_theme`, `ending_theme`, or `other_key`);
- start/end and complete sentence count;
- speaker IDs, turn roles, and confidence;
- neighboring context and spacing notes;
- review status and any listening-dependent issue.

### Emphasis selection preview

The emphasis *selection* is reviewed with a self-contained HTML page (the tool
geometry HTML in SKILL.md step 6 is commit evidence and does not replace this).
Its job is to let the reviewer audit the picks, so it must be a list of **every
current subtitle row in time order**, not only the selected lines — dropped and
reserve rows stay visible so coverage and deletions are checkable.

Per-row data model (keep it as a `const D=[...]` array so the page is one file):

- `i` original row index (never renumber on add/remove — see numbering rule);
- `s`/`e` start/end in seconds, printed to two decimals;
- `t` the display text, and `raw` the untouched source text when `t` was edited;
- `g` group id (empty for ungrouped rows) and `first` = is this the group's head;
- `lv` level 1–3 (0 = not emphasized);
- `cat` short semantic category label for the group;
- `main` primary pick vs reserve/backup candidate;
- flags: profile violation (over line limit, non-standalone particle, dropped
  particle) with a short reason string; fragment split (one sentence shown
  across screens, suggest merging); text edited (non-verbatim, needs confirm).

Rendering conventions:

- Dark page, color-coded left border plus a badge per level. Reserve rows use a
  dashed border and a single top checkbox toggles showing all of them (default
  shown); ungrouped/non-picked rows carry no badge so the eye lands on groups.
- Show the group badge (id + level + category) only on the group's first row, so
  a multi-line group reads as one event.
- Insert a centered "— gap Ns —" divider whenever the silence before a row
  exceeds a review threshold (default ~4s) to surface sparse pacing.
- Header meta states the per-screen line cap (recommend 1–2, max 3), the
  primary/reserve counts, and coverage percentage over the requested scope.

Iteration discipline:

- Numbering is frozen once issued; adding or removing rows never renumbers
  existing rows, so review comments ("#10", "G7") stay addressable across turns.
- Title the page with an explicit `vN` and keep a versioned changelog that
  records, per turn, the changes made in response to the user's instructions.
- Any row whose text was edited (non-verbatim) must be flagged for confirmation
  and retain the original source text.

This page decides *selection* only. Approved layout, flower text, position, and
motion are reviewed with the separate one-screen-per-group card described in
SKILL.md "Preview deliverable gate".

## Sound choice

Choose sound from both motion and meaning:

| Visible motion | Spoken function | Suitable family |
|---|---|---|
| small pop/reveal | a light fact or parameter | soft pop, click, restrained prompt |
| scale landing/impact | major number or core conclusion | hit or impact proportional to level |
| sweep/wipe/fast travel | transition or rapid visual move | whoosh/sweep |
| mechanical opening/operation | machine, cutter, fixture, equipment | mechanical open or operating sound |
| typing/reveal by characters | text entry or typed explanation | typing/UI sound |
| confirmation or completion | conclusion, confirmed result, final CTA | ding/prompt, used sparingly |
| warning pulse/shake | genuine risk or warning | warning cue |

### Motion-family candidates

Build animation and SFX candidates around the visible motion family. These are
generic search families, not Jianying preset names or fixed pairings:

| Motion family | Typical use | SFX families to audition |
|---|---|---|
| `directional_sweep` | Fast travel, wipe, or directional focus | Whoosh or sweep |
| `luminous_reveal` | A restrained reveal, bright fade, or highlighted fact | Soft pop, sparkle, or light chime |
| `numeric_glitch` | A deliberate correction, contrast, or unusually forceful number | Short impact or digital click |
| `completion_glow` | A result landing, confirmation mark, or resolved benefit | Brief ping or restrained bell |
| `expressive_reaction` | An intentionally playful or exaggerated reaction | Short whoop, cartoon pop, or novelty cue |

Use `numeric_glitch` only when the message and visual treatment call for a
disruption. Ordinary numbers and technical terms do not need an impact by
default. Keep the motion-family label separate from the source preset identity;
resolve actual presets through the current case catalog and pool.
Use `expressive_reaction` only when the requested tone supports it; it is not a
default for restrained or technical packaging.

These are families, not fixed asset names. Select an actual asset only after auditioning or identifying a user-approved reusable segment.

Semantic role → motion family, as a reviewable default mapping (resolve real
presets and resource IDs from the current case pool, then intersect with the
local effect cache; never carry preset names across versions unverified):

| Speech/visual role | Motion family | Intent |
|---|---|---|
| setup / lead-in line of a group | `luminous_reveal` (soft fade or typed entry) | open without competing with the landing line |
| question phrasing, conclusion landing | `completion_glow` with a slight scale landing | mark the point where the answer settles |
| number, parameter, ranking | `numeric_glitch` / sparkle-tier reveal | make the figure the memorable item |
| technical term or product name | `directional_sweep` (directional grow or blur-out) | give the term a shape, not a flash |
| risk or consequence | a stronger `directional_sweep` (wipe with a clear direction) | read as warning, not decoration |

Within one group the front line takes the setup treatment and the back line takes
the emphasis treatment; adjacent screens must not repeat the same motion. A group
whose two lines share one role needs a selection review, not two identical
animations.

Every motion family uses a candidate pool rather than one hard-coded sound. A pool contains at least three distinct observed preset IDs before it can support an automatic final apply. Select one candidate after semantic fit, sound-form, leading-silence, dialogue-collision, and reuse checks. A candidate pool is never a request to layer all candidates.

Count reuse across the whole plan before review, not only inside the per-preset validator. A human-readable plan table can silently schedule one preset more than its cap (the cap counts every event selecting it, including cross-group uses); when the count exceeds the cap, swap the least semantically-bound occurrence to a same-family different-timbre preset rather than dropping the sound.

Leading silence of JianYing cache SFX must be measured, never trusted from the reference draft's source range (the reference may already skip it): run `ffmpeg -i <cache-file> -af silencedetect=noise=-35dB:d=0.03 -f null -` (retry `-45dB` when nothing is found); when the first `silence_start` is below 10ms, record `silence_end` as `leading_silence_us` in the catalog and apply the `skip` policy. Observed cache presets commonly carry 30–400ms of leading silence; unmeasured presets land audibly late against the animation even though the target range looks correct.

Inline candidate lists are review evidence only. Final plans must resolve `candidate_pool_ref`, `selected_preset_id`, and `catalog_ref` from the formal sound pool/catalog and the catalog record must be verified. If the pool is incomplete, keep the plan in review and emit `candidate_pool_incomplete`.

Sound-form defaults are:

- `single_hit` and `decay` → text-span trim;
- `multi_hit` and `typing` sounds → motion-span trim;
- known leading silence → skip unless `preserve` is explicitly justified;
- `text_span` target range must equal the text range; `motion_span` target range must equal the parsed motion event;
- Review-mode dialogue overlap is a warning, but final-plan dialogue overlap or missing dialogue interval evidence is a safety block. A selected preset must be present in the formal candidate pool and catalog; final plans additionally require verified pool/candidate/catalog records and a legal leading-silence source range.
- a known leading silence requires an explicit source range so the editor context cannot silently start at source zero;
- unknown form or incomplete duration data → human review.

## Three-layer mix

A finished vertical video has three audio layers, and they are not peers: the
voice leads, everything else makes room.

| Layer | Default | Accepted band | Rules |
| --- | --- | --- | --- |
| Dialogue (spoken voice, including a video's own audio) | 1.00 | 0.90–1.00 | The reference level. Never ducked for music on interview material |
| Sound effects (`type: sound`) | **0.50** | 0.45–0.55, impact hits up to 0.60 | Short transients; must stay distinguishable when music is underneath |
| Background music (`type: music`) | **0.40** | 0.35–0.45, pure-music sections up to 0.55 | Always faded: fade in 1.0 s, fade out 3.0 s |

Hard checks (block, not warning): music above 0.55 while dialogue exists; music
running longer than 5 s with no fade; an SFX segment at volume 0 or above 0.8.
Warning: SFX below 0.25 while overlapping music.

Other rules:

- One music clip at a time. If two beds meet, overlap them by 300–500 ms and fade
  both sides.
- A section with no music is legal. Never add a default bed just to fill silence.
- Measure the tail silence on the dialogue layer when music runs to the end.

`layer-audit` reports all of the above from a snapshot; it never fixes them.

## Music bed

- Place music through the plan's top-level `music[]` array, not inside
  `group.audio`. A group's audio is a sound effect tied to a visible event; a bed
  is not.
- Cut beds at dialogue boundaries. Never start or stop music mid-sentence.
- Two-part structure is common: a lighter opener for the first ~10 s, then the main
  bed. Overlap the join and fade both sides.
- Reuse: the same track may supply at most two segments in one video, and neither
  segment may be stretched by looping beyond 60 s.
- Supply the dialogue intervals (`--existing-audio`) so the audit can tell whether
  music is actually covering speech.

## Transition sound pairing

Sound effects attach to two different kinds of event, and they are counted
separately:

| Visual event | Sound family | Anchor |
| --- | --- | --- |
| Per-row text entrance | light transition (swish, tick, pop) | `entry_start` |
| Page turn / page flip | paper rustle | `transition_peak_us` |
| Whip / whip-pan | whoosh | `transition_peak_us` |
| Scale or impact landing | impact hit | `animation_peak_us` |
| Cross dissolve | none | — |

A transition sound is **not** part of the per-row animation coverage matrix. If a
48-line plan gets one transition sound, coverage is still 48 events, not 49. Count
them in separate buckets so a full-coverage check does not report a phantom gap.

## Sound catalog responsibilities

`jianying-editor` may observe preset ID, display name, duration, waveform, leading silence, tail, and repeatability. It reports observations and performs approved execution. `jianying-packaging` classifies the sound form, assigns trim policy, places the preset in a motion-family pool, chooses one candidate for an approved group, and records the semantic/visual reason. Neither catalog nor pool stores a project's subtitle, timestamp, track, material, or use location.

## Synchronization

Represent the visual event with:

- `animation_start_us`
- `animation_peak_us`
- `animation_end_us`

There is no single global anchor. Pick a policy per event and record both
`anchor_policy` and `anchor_basis`, because a global default is wrong in one
direction or the other:

| Situation | `anchor_policy` | Anchor | Why |
| --- | --- | --- | --- |
| Per-row entrance (fade, 200–400 ms slide) | `entry_start` | `animation_start_us` | A short fade has no independent perceptual landing; the text appearing *is* the beat |
| One-shot transition (page turn, wipe) | `transition_peak_us` | transition midpoint | The motion of the transition is what the ear should hit |
| Scale/impact hit | `animation_peak_us` | scale or impact peak | There is a measurable peak to land on |
| Overlay / B-roll entering frame | `entry_start` | layer start | One-shot appearance |
| Explicit user or reference choice | `explicit_us` | given value | Documented reason |

The audio events of one plan may use different policies. What is forbidden is
carrying no policy at all.

When skipping leading silence, source trimming and timeline placement are separate decisions. Let `audible_source_us` be the first audible transient, `source_start_us` the source in-point, and `anchor_us` the intended visual landing. Place the clip so `target_start_us + max(0, audible_source_us - source_start_us) = anchor_us`. Trimming the source in-point alone does not repair a stale target position. Verify the audible onset against the motion with waveform evidence and listening.

Deduplicate sound events by start time: layers that land on the same beat — a main emphasis line plus an auxiliary mark such as a question mark (which may share the group's text track and animation rather than a dedicated lower track) — get one sound for the beat, not one per layer.

## Restraint and deduplication

- One semantic group normally gets zero or one primary sound.
- Coverage density is a task input. When the brief requests full animation coverage, map each distinct motion event to one semantically matched sound; co-timed layers on one beat share one sound. Do not silently omit a required event under the default restraint rule. Record an unresolved gap only when a real dialogue collision, missing semantic match, or insufficient evidence prevents placement.
- Treat repetition tolerance as a task input. Audit the configured window of consecutive audible SFX events in playback order within the requested content scope. If the brief gives no numeric window, compare adjacent events within each content region and apply the documented whole-plan reuse cap; do not use a global duplicate count across unrelated regions. Exempt only an explicitly approved motif.
- Adjacent groups should not repeat the same strong sound without a deliberate motif.
- Motion reuse is checked only between adjacent events inside the same content region. A shared non-empty `motif_id`, or `intentional_motif` on both events, is an intentional-repeat exemption; static or continuation layers are exempt. Different regions are not compared globally.
- An existing sound covering the same visual event wins over a new insertion unless replacement is approved.
- A sound may be omitted when dialogue density, tonal mismatch, or clutter outweighs the benefit.
- Record `reason` and, for omission/replacement, `decision_basis`. Do not optimize for or report success by sound count.

Use `packaging_tool.py motion-check` for the local reuse audit and
`packaging_tool.py audio-audit` to keep `sfx`, `music`, `ambience`, and
`dialogue`, and `unknown` counts separate. An audio event is bound to a semantic group, not
to every text layer in that group.

## Template selection

Use the generic relative-layout registry. The template describes group slots and relationships, not a fixed sentence or absolute canvas coordinate. Resolve the runtime anchor from the current final subtitle reference (`X0/Y0`), preserve static continuation transforms, and validate text bounds, collisions, and safe zones. The initial registry includes centered, stacked, side-pair, overlay/replace, attached-mark, and composite templates; extensions should inherit or compose these data-only definitions.

## Project-profile boundary

Font, coordinate, line-length, color, layer, animation, and sound preferences are project or user profiles. Load them from an external project case reference at runtime; never promote a single project's values into this reusable reference. Generic registry offsets describe relative template relationships only; verify them against the current subtitle anchor, safe area, and rendered result. The current saved manual timeline remains authoritative when a project profile is supplied.
