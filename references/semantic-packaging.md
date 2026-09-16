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

## Synchronization

Represent the visual event with:

- `animation_start_us`
- `animation_peak_us`
- `animation_end_us`

Default the sound anchor to the perceptual landing point, usually `animation_peak_us` or `transition_peak_us`. Use group start only when the sound itself initiates the visible action.

## Restraint and deduplication

- One semantic group normally gets zero or one primary sound.
- Adjacent groups should not repeat the same strong sound without a deliberate motif.
- An existing sound covering the same visual event wins over a new insertion unless replacement is approved.
- A sound may be omitted when dialogue density, tonal mismatch, or clutter outweighs the benefit.
- Record `reason` and, for omission/replacement, `decision_basis`. Do not optimize for or report success by sound count.

## Learned local convention

For the user's current Jianying workflow, ordinary text uses a user-confirmed prototype corresponding to 点宋体, size 10, shadow enabled, UI Y `-850`, and no more than 13 Chinese characters per line. This is a project profile, not a universal default. The current manual timeline is the authoritative reference.
