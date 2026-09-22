# Semantic emphasis and sound design

## Context-first emphasis

Evaluate the current subtitle unit together with the previous and next unit, the current topic, and the video's communication goal. Subtitle rows are timing containers, not necessarily semantic groups.

Good emphasis candidates include:

- decisive product, brand, or technical names;
- numbers together with units, ranges, and conditions;
- conclusions and the premise that makes them true;
- contrast, correction, warning, risk, or unusually strong degree;
- the short question phrase needed to frame an answer;
- one memorable CTA when it serves the video's goal.

Do not emphasize a word merely because it is frequent, visually convenient, or already has an animation. Avoid highlighting every noun or every line.

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

- One semantic idea can span one or more text layers.
- A two-line group should share one meaning and one overall visual landing point.
- Preserve the original start of each spoken phrase unless an approved template intentionally stages the phrases.
- Do not merge unrelated lines to fit a template.
- Treat punctuation, labels, icons, and background shapes as subordinate layers of the same group.

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

These are families, not fixed asset names. Select an actual asset only after auditioning or identifying a user-approved reusable segment.

Every motion family uses a candidate pool rather than one hard-coded sound. A pool contains at least three distinct observed preset IDs before it can support an automatic final apply. Select one candidate after semantic fit, sound-form, leading-silence, dialogue-collision, and reuse checks. A candidate pool is never a request to layer all candidates.

Inline candidate lists are review evidence only. Final/apply plans must resolve `candidate_pool_ref`, `selected_preset_id`, and `catalog_ref` from the formal sound pool/catalog and the catalog record must be verified. If the pool is incomplete, keep the plan in review and emit `candidate_pool_incomplete`.

Sound-form defaults are:

- `single_hit` and `decay` → text-span trim;
- `multi_hit` and typing/continuous-click sounds → motion-span trim;
- known leading silence → skip unless `preserve` is explicitly justified;
- `text_span` target range must equal the text range; `motion_span` target range must equal the parsed motion event;
- Review-mode dialogue overlap is a warning, but final/apply dialogue overlap or missing dialogue interval evidence is a safety block. A selected preset must be present in the formal candidate pool and catalog; final/apply additionally require verified pool/candidate/catalog records and a legal leading-silence source range.
- a known leading silence requires an explicit source range so the editor context cannot silently start at source zero;
- unknown form or incomplete duration data → human review.

## Sound catalog responsibilities

`jianying-editor` may observe preset ID, display name, duration, waveform, leading silence, tail, and repeatability. It reports observations and performs approved execution. `jianying-packaging` classifies the sound form, assigns trim policy, places the preset in a motion-family pool, chooses one candidate for an approved group, and records the semantic/visual reason. Neither catalog nor pool stores a project's subtitle, timestamp, track, material, or use location.

## Synchronization

Represent the visual event with:

- `animation_start_us`
- `animation_peak_us`
- `animation_end_us`

Default the sound anchor to the perceptual landing point, usually `animation_peak_us` or `transition_peak_us`. Use group start only when the sound itself initiates the visible action.

## Restraint and deduplication

- One semantic group normally gets zero or one primary sound.
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

Font, coordinate, line-length, color, layer, animation, and sound preferences are project or user profiles. Load them from an external project case reference at runtime; never promote a single project's values into this reusable reference. The current saved manual timeline remains authoritative when a project profile is supplied.
