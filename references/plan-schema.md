# Packaging plan schema

Validate a plan before presenting or executing it:

```powershell
python scripts/packaging_tool.py validate plan <plan.json>
```

The plan is a semantic and execution contract. It may contain exact runtime locators supplied by the user, but this reference and its examples must remain generic. Encryption keys, replica paths, backup paths, and project-specific mutation code belong to `jianying-editor`.

## Schema versions

- New plans use `schema_version: "1.2"`.
- Version `1.1` remains readable for review and migration only.
- Version `1.0` remains readable as legacy input and is never directly applied.
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

`source.content_pass` must be `stable` or `approved`, and `source.subtitle_alignment.status` must be `stable` or `approved`. `source.final_subtitle_reference.status` must be `approved` for a 1.2 plan. `comparison.remap_status` must be `not_required` or `verified` for a final phase. `pending` and `blocked` stop final execution. A 1.2 execution context must include every listed stop condition.

`source.final_subtitle_units` is the approved per-unit text-hash manifest. Its `text_hash` is the SHA-256 hash of the exact UTF-8 final subtitle text. Schema 1.2 text visuals must carry the matching `text_ref` and `text_hash`; the validator compares both the declared hash and the actual visual text. A mismatch is `text_mismatch` and blocks final/apply.

The existing 1.1 contract remains required for 1.1 plans: `staging`, `duplicate_policy`, `template_health`, `sound_selection`, `visual_capability_requirements`, and `light_content_ops`.

## Canonical fields, reports and exit codes

Schema 1.2 uses `group.visual` as the canonical visual-operation array. The resolver accepts `visuals` and `visual_operations` only as read-only legacy aliases; if more than one alias is present, their contents must be identical. Text visuals must bind `text_ref` and a SHA-256 UTF-8 `text_hash` to exactly one entry in `source.final_subtitle_units`.

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
      "constraints": {"safe_zone": "project_safe_zone", "collision": "block"},
      "fallback": "manual_review"
  },
  "sound_selection_basis": "motion and spoken function are compatible"
}
```

`layout` is required for final visual groups in 1.2. A slot has a unique ID, a typed subtitle/auxiliary reference, and numeric relative offsets. `relative_to` and `inherit_transform_from` may refer to any declared slot. The validator rejects unknown references and cycles. Use `legacy_absolute` only with explicit visual verification and manual-review fallback.

For 1.2, every slot must declare `ref_type`. `subtitle_unit` references must be listed in `semantic_unit_refs`; `auxiliary_mark` references must be listed in `auxiliary_text_refs`. Template inheritance uses parent slots first, then child slots; a same-ID child slot overrides the parent and a new child slot is appended. Inheritance cycles are invalid.

When a visual text operation supplies `text`, it must also supply `text_ref` and `text_hash`. Subtitle-unit references must resolve through `source.final_subtitle_units`; auxiliary marks must be declared in `auxiliary_text_refs`.

The template registry defines generic slot relationships; it must not contain project text, project timestamps, draft paths, or project IDs. Runtime `jianying-editor` resolves `X0/Y0`, canvas conversion, text bounds, safe zones, and actual rendered fields.

## Visual and audio operations

Use exact locators for executable operations. A new object needs a target track locator; an existing object needs a segment locator. A copied template must identify its source closure and allowed overrides. Every override is either `{ "mode": "absolute", "value": ... }` or `{ "mode": "relative", "delta": ... }`.

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

`text_span` also requires `target_range == text_range`; `motion_span` requires `target_range == motion_event.start_us..end_us`. Known leading silence requires an explicit `source_range`; `skip` must start after the silence, while `preserve` requires an override reason. Final/apply plans must resolve the candidate pool and selected preset from the formal sound catalog; inline candidate pools are review-only.

## Safety gates

- `execution.mode` is `review` or `apply`.
- Apply requires `target.clone_source=true`, `execution.clone_source=true`, `preserve_source=true`, `preserve_manual_edits=true`, and `pre_write_backup=required`, unless the user has explicitly authorized a documented safety exception.
- Final requires approved staging and subtitle alignment.
- Final requires approved final-subtitle reference and verified/not-required remapping.
- Final requires the complete execution context contract; it is passed to editor as context until a runtime consumer is implemented.
- Staging may use subtitle-copy/display-review operations only; it must not add final templates or sound.
- Covered subtitles remain preserved on source and staging. Clone-only disable/delete requires read-back, approval, and backup.
- Unknown or unsupported capabilities require visual verification and a risk note.
- Semantic rewriting, deletion, reordering, or factual correction returns to `jianying-rough-cut`.
