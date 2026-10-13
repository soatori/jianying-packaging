# Packaging plan schema

Validate a plan before presenting or executing it. Apply it only through the schema 1.2 packaging adapter:

```powershell
python scripts/packaging_tool.py validate plan <plan.json>
python scripts/packaging_tool.py apply --draft <draft> --timeline <source> --plan <plan.json>
```

The plan is a semantic and execution contract. It may contain exact runtime locators supplied by the user, but this reference and its examples must remain generic. The packaging adapter owns schema 1.2 plan translation; encryption, replica discovery, backup, low-level transaction writes, and read-back use the existing `jianying-editor` API. Its `apply-plan` command remains limited to `keep_blocks`.

## Schema versions

- New plans use `schema_version: "1.2"`.
- Version `1.1` remains readable for review and migration only.
- Version `1.0` remains readable as legacy input and is never directly applied.
- Do not migrate by changing only `schema_version`: final 1.2 layouts need registered `template_id`/version data and numeric safe-zone bounds. A review-only validation does not run apply migration guards; only the actual apply path enforces write eligibility.
- A `1.2` final plan requires an approved final-subtitle reference, verified order mapping, relative layout or explicitly reviewed legacy layout, sound selection evidence, clone/source-preservation settings, and a required pre-write backup.
- A `1.2` final plan also requires `staging.review_status: "approved"`; a final plan with pending or reviewing staging is blocked.

Execution phases:

- `staging`: copy subtitle candidates to an upper review layer; preserve source subtitles; do not add final templates or sound effects.
- `final`: apply the approved visual/audio package after staging, subtitle alignment, and remapping are approved.

## Required 1.2 contract

```json
{
  "schema_version": "1.2",
  "source": {
    "draft_path": "<runtime draft path>",
    "timeline": "<runtime source timeline>",
    "content_pass": "approved",
    "subtitle_alignment": {"id": "alignment-ref", "hash": "sha256:...", "status": "approved"},
    "final_subtitle_reference": {"id": "subtitle-ref", "hash": "sha256:...", "status": "approved"},
    "final_subtitle_units": [
      {"unit_id": "semantic-unit-ref", "text_hash": "sha256:<utf8-text-hash>", "status": "approved"}
    ]
  },
  "comparison": {
    "source_order_hash": "sha256:...",
    "target_order_hash": "sha256:...",
    "remap_status": "verified"
  },
  "target": {"timeline_name": "<runtime target name>", "clone_source": true},
  "staging": {
    "required": true,
    "mode": "copy_to_upper_review_track",
    "source_timeline": "<runtime source timeline>",
    "target_timeline": "<runtime target name>",
    "review_status": "approved",
    "original_subtitles": "preserve"
  },
  "execution": {
    "mode": "review",
    "phase": "final",
    "clone_source": true,
    "preserve_source": true,
    "preserve_manual_edits": true,
    "pre_write_backup": "required",
    "covered_subtitle_policy": "preserve",
    "context_contract": {
      "anchor_policy": "runtime_final_subtitle_x0_y0",
      "layout_policy": "group_atomic_relative",
      "sound_policy": "catalog_candidate_single",
      "readback_required": true,
      "stop_conditions": [
        "pending_remap",
        "text_mismatch",
        "layout_collision",
        "unverified_sound",
        "leading_silence_unresolved",
        "missing_backup"
      ]
    }
  }
}
```

`source.content_pass` may be `stable` or `approved`, and `source.subtitle_alignment.status` may be `stable` or `approved` for a review-only plan. `stable` is not user approval. For every schema 1.2 write plan (`execution.mode: apply`), the validator requires both statuses to be `approved` for staging and final phases. Final also requires `staging.review_status: approved`, an approved final-subtitle reference, and `comparison.remap_status` of `not_required` or `verified`. `pending` and `blocked` stop final execution. Validator success does not grant conversational write authorization. The `apply` command requires a second `--apply` flag for disk writes; the Agent must still verify the user's authorization for the exact phase and target. A 1.2 execution context must include every listed stop condition.

`source.final_subtitle_units` is the approved per-unit text-hash manifest. Its `text_hash` is the SHA-256 hash of the exact UTF-8 final subtitle text. Schema 1.2 text visuals must carry the matching `text_ref` and `text_hash`; every text `copy_from_subtitle` operation also requires `text`, and its hash must match that exact UTF-8 text even when `text_ref` names an auxiliary mark. Semantic subtitle references must additionally match the corresponding `source.final_subtitle_units` hash. A mismatch is `text_mismatch` and blocks final/apply.

The existing 1.1 contract remains required for 1.1 plans: `staging`, `duplicate_policy`, `template_health`, `sound_selection`, `visual_capability_requirements`, and `light_content_ops`.

## Canonical fields, reports and exit codes

Schema 1.2 uses `group.visual` as the canonical visual-operation array. The resolver accepts `visuals` and `visual_operations` only as read-only legacy aliases; if more than one alias is present, their contents must be identical. Apply-mode transforms require the canonical `group.visual` field. Text visuals must bind `text_ref` and a SHA-256 UTF-8 `text_hash` to exactly one entry in `source.final_subtitle_units` when the reference is semantic.

All commands return the same JSON envelope by default: `report_type`, `ok`, `status`, `errors`, `input_errors`, `warnings`, `summary`, and `data`. A later command may consume that complete envelope and automatically use `data`; raw data JSON remains valid. `--format text` is a presentation-only mode. Exit code `0` means a usable report (including warnings/review), `1` means a safety/evidence/validation block, and `2` means malformed JSON, missing/unreadable input, argument, or output-path failure.

`resolve` uses the observation subtitle unit's numeric `runtime_anchor.x/y` (with explicitly checked legacy aliases) and never reads a guessed plan-side runtime anchor. `verify` requires non-empty, equal `source_timeline_hash` values in both snapshots and blocks every unplanned target addition, deletion, order change, or field change.

## Group contract

Every group keeps the existing `id`, `status`, `range`, `context`, `category`, `level`, `motion`, and `motion_event` fields. A 1.2 group also records:

```json
{
  "semantic_unit_refs": ["semantic-unit-ref"],
  "subtitle_anchor": {
    "unit_id": "semantic-unit-ref",
    "text_hash": "sha256:...",
    "text_authority": "final_visible_subtitle"
  },
  "auxiliary_text_refs": ["question-mark-ref"],
  "remap_status": "verified",
  "source_order_hash": "sha256:source",
  "target_order_hash": "sha256:target",
  "layout": {
    "template_id": "center_stack",
    "template_version": 1,
    "position_mode": "relative_template",
    "anchor": {"type": "runtime_reference", "x": "X0", "y": "Y0"},
      "slots": [
        {"id": "main", "ref_type": "subtitle_unit", "text_ref": "subtitle-ref", "offset": {"dx": 0, "dy": 0}},
        {"id": "secondary", "ref_type": "subtitle_unit", "text_ref": "subtitle-ref-2", "relative_to": "main", "offset": {"dx": 0, "dy": 0.1}, "inherit_transform_from": "main"}
      ],
      "constraints": {"safe_zone": {"x_min": -0.8, "x_max": 0.8, "y_min": -0.8, "y_max": 0.8}, "collision": "block"},
      "fallback": "manual_review"
  },
  "sound_selection_basis": "motion and spoken function are compatible"
}
```

### Optional dialogue and same-screen metadata

These fields are optional and backward compatible. They make speaker-aware selection and same-screen review machine-checkable without changing the required group contract:

```json
{
  "group_kind": "question",
  "sentence_count": 2,
  "speaker_context": [
    {
      "unit_ref": "semantic-unit-ref",
      "speaker_id": "host",
      "turn_role": "question",
      "confidence": "high"
    }
  ],
  "spacing_after_us": 5540000,
  "same_screen": {
    "enabled": true,
    "extend_to_group_end": true,
    "overlap_policy": "separate_upper_tracks"
  }
}
```

- `group_kind` is one of `question`, `answer`, `opening_theme`, `ending_theme`, or `other_key`.
- `sentence_count` is an integer from 1 through 3.
- `speaker_context[].unit_ref` must identify a semantic unit; `turn_role` is one of `narration`, `question`, `answer`, `reaction`, or `other`; `confidence` is `high`, `medium_high`, `medium`, `low`, or `unknown`.
- `spacing_after_us` records the gap to the next selected group and must be non-negative.
- When `same_screen.enabled` is true, `extend_to_group_end` must be true and `overlap_policy` must be `separate_upper_tracks`.

`layout` is required for final visual groups in 1.2. A slot has a unique ID, a typed subtitle/auxiliary reference, and numeric relative offsets. `relative_to` and `inherit_transform_from` may refer to any declared slot. The validator rejects unknown references and cycles. Use `legacy_absolute` only with explicit visual verification and manual-review fallback.

For 1.2, every slot must declare `ref_type`. `subtitle_unit` references must be listed in `semantic_unit_refs`; `auxiliary_mark` references must be listed in `auxiliary_text_refs`. Template inheritance uses parent slots first, then child slots; a same-ID child slot overrides the parent and a new child slot is appended. Inheritance cycles are invalid.

Every schema 1.2 text `copy_from_subtitle` operation must supply `text`, `text_ref`, and `text_hash`. Other text operations that supply `text` must also supply `text_ref` and `text_hash`. Subtitle-unit references must resolve through `source.final_subtitle_units`; auxiliary marks must be declared in `auxiliary_text_refs`.

The template registry defines generic slot relationships; it must not contain project text, project timestamps, draft paths, or project IDs. Final/apply automatic layout requires numeric `safe_zone` bounds in normalized canvas coordinates and `project_profile.canvas_width`/`canvas_height`. Bounds use the same normalized coordinate space as relative slots. The adapter measures each current text line with the font file and size in its material, converts glyph bounds to normalized coordinates, and fits the planned operation inside the safe zone. Missing or unreliable font metrics block automated layout. A symbolic safe-zone name remains review-only; it cannot authorize a write.

Manual transforms are preserved when the plan does not include a layout change. If `layout.pattern` is `diagonal_stagger`, positions may be staggered across lines but text rotation must stay at zero. Preview and apply use the same candidate geometry; an explicit override that moves text outside the safe zone blocks. A layout operation must identify an existing unique topmost text track for auxiliary text, and the adapter blocks same-track overlap rather than creating a track.

Plans with layout, animation, position, scale, rotation, or alpha changes produce a deterministic HTML geometry/timing preview and a `visual_preview_sha256`. After reviewing that exact preview, record:

```json
{
  "review_report": {
    "visual_preview_status": "approved",
    "visual_preview_sha256": "sha256:<reported-preview-hash>"
  }
}
```

`--apply` recomputes the candidate preview and blocks unless both fields match. The HTML shows measured line widths, safe zone, position, layer order, visibility, alpha, and animation duration. It is not evidence that an effect survives a native Jianying reopen; final visual and audio acceptance remains a separate human review.

An animated visual may include `animation: {"resource_id": "<TextIntro-resource-id>", "duration_us": 1840000}`. `duration_us` is in microseconds and must equal `min(current preset duration, visible text-row duration)`; generic plan validation can check the row window, while apply checks the current preset duration too. The adapter builds a local inventory from `TextIntro` and the exact MD5 cache directory, requires same-version native capability evidence for plain-text compatibility, and writes the exact resolved cache path. Unknown/ambiguous paths, resource types, versions, or required text inputs block. A shader file is not a cross-version compatibility guarantee. The recorded duration is checked against the plan, operation report, and candidate animation material.

Transparency maps to `segment.global_alpha` only when that field exists on the current segment prototype, with a value from 0 through 1. Hiding continues to use `segment.visible`; alpha zero is not a replacement for hiding.

### Review evidence for these fields

A plan that carries dialogue or same-screen metadata should also carry a review report containing:

- the current source/target hashes and duration;
- group start/middle/end preview times and observed layer counts;
- source visibility and clone-only hidden-row read-back;
- assigned upper track IDs and moved segment IDs;
- manual transform comparisons;
- backup path and replica-validation result.

A missing or stale review report blocks final/apply even when the structural plan validates. If the plan changes its layout/animation or its current source changes, regenerate and reapprove the preview hash.

## Replica audit

Read-only source preflight and apply dry-run classify replica mismatches using the current `ReplicaManifest` roles. Drift in an associated `writable-backup` is a warning; primary and associated `writable-template` drift block. Missing, unreadable, or unassociated candidates also block. After a transaction write, replica validation remains strict and every required target copy must match.

## Visual and audio operations

Use exact locators for executable operations. A new object needs a target track locator; an existing object needs a segment locator. A copied template must identify its source closure and allowed overrides. Every override is either `{ "mode": "absolute", "value": ... }` or `{ "mode": "relative", "delta": ... }`.

`visual.overrides` is a direct adapter contract and currently allows only
`position_x`, `position_y`, `scale_x`, `scale_y`, `uniform_scale`, `start_us`,
`duration_us`, `visible`, and `global_alpha`. Semantic fields such as
`rotation`, `opacity`, and `anchor_x` may remain in the property model, but
they are not executable direct overrides. Layout slot transforms are a
separate adapter path; a supported layout rotation must not be encoded as a
direct visual override.
Absolute scale overrides must be positive; absolute `start_us` values must be
non-negative and absolute `duration_us` values must be positive. Relative
values are checked again after applying them to the current draft prototype.

The adapter copies a template segment and its complete material closure from
the current draft. A preset with one source segment needs no extra selector; if
it declares multiple source segments, each `clone_template` visual operation
must include `template_segment_id` naming exactly one of them. For
`add_overlay`, `clone_asset`, and `add_asset`, use a segment locator or an
existing `asset_id`/`material_id` in the draft with one unambiguous same-type
segment prototype. External files must be staged into the draft first. Missing
or ambiguous prototypes block before write.

Audio `fade_in_us` and `fade_out_us` require the target segment to reference
exactly one `materials.audio_fades` item with `type: "audio_fade"` and integer
duration fields. The adapter clones and rebinds a shared fade material before
changing it; a missing or ambiguous fade prototype blocks the operation. The
saved fade values still require listening review in Jianying.

The adapter does not synthesize motion from a family label. A final group with
`motion` other than `none` must resolve to a copied segment whose referenced
closure contains a non-empty animation/keyframe payload; otherwise apply is
blocked. A declared `motion: none` also blocks when the selected prototype
contains motion. Matching the payload to the intended animation family and
checking timing/readability still require reopened Jianying review.

For a non-`none` audio action, require:

```json
{
  "motion_family": "reveal",
  "candidate_pool_ref": "reveal-default",
  "selected_preset_id": "preset-id",
  "sound_form": "single_hit",
  "trim_policy": "text_span",
  "leading_silence_policy": "skip",
  "leading_silence_us": 0,
  "selection_basis": "single hit matches the spoken emphasis",
  "reason": "One restrained sound supports the visual landing",
  "reuse_count": 1
}
```

`single_hit` and `decay` default to `text_span`; `multi_hit` and typing-like sounds default to `motion_span`. A known leading silence must be skipped or explicitly preserved with a reason. Do not stretch or loop unless the catalog permits it. A group has at most one primary sound.

`text_span` requires `text_range`; `motion_span` requires a valid group motion event. A final apply plan must select a verified candidate from a pool containing at least three unique candidates. The pool is a choice set, not simultaneous playback.

`text_span` also requires `target_range == text_range`; `motion_span` requires `target_range == motion_event.start_us..end_us`. Known leading silence requires an explicit `source_range`; `skip` must start after the silence, while `preserve` requires an override reason. Final/apply plans must resolve the candidate pool and selected preset from a verified sound catalog.

Sound catalogs and motion pools are case inputs. The skill package contains no ready-to-use project assets, and the validator does not load a hidden default catalog. For plans with sound, pass the current verified files explicitly: `python scripts/packaging_tool.py validate plan <plan.json> --catalog <case-catalog.json> --pools <case-pools.json>`. Missing inputs keep sound selection unresolved; do not substitute assets from another project.

Final/apply sound checks also require explicit dialogue interval evidence so
the adapter can block SFX/dialogue collisions. The adapter derives intervals
when the current draft's audio material or track metadata identifies dialogue;
when those roles are unknown, provide `--existing-audio` as a JSON list with
`id`, `kind: "dialogue"`, `start_us`, and `end_us`. Unknown audio roles never
count as evidence that dialogue is absent.

## Safety gates

- `execution.mode` is `review` or `apply`.
- Apply requires `target.clone_source=true`, `execution.clone_source=true`, `preserve_source=true`, `preserve_manual_edits=true`, and `pre_write_backup=required`, unless the user has explicitly authorized a documented safety exception.
- Staging apply requires approved content and subtitle alignment, plus authorization for the staging write.
- Final apply requires approved content, subtitle alignment, and staging; it also requires authorization for final application.
- Final requires approved final-subtitle reference and verified/not-required remapping.
- Final requires the complete execution context contract; the packaging adapter consumes it as an execution gate.
- Staging may use subtitle-copy/display-review operations only; it must not add final templates or sound.
- Covered subtitles remain preserved on source and staging. Clone-only disable/delete requires read-back, approval, and backup.
- Unknown or unsupported capabilities require visual verification and a risk note.
- Semantic rewriting, deletion, reordering, or factual correction returns to `jianying-rough-cut`.
