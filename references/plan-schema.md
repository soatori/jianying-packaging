# Packaging plan schema

Store plans as UTF-8 JSON and validate before presenting or executing:

```powershell
python scripts/validate_packaging_plan.py <plan.json>
```

The plan is a decision and execution contract. It contains semantic decisions and exact object locators, but no encryption keys, replica paths, or custom write logic; those belong to `jianying-editor`.

New plans use `schema_version: "1.1"`. Version 1.0 remains readable for migration only and must not be applied without review. Version 1.1 requires an approved subtitle-alignment reference, a reversible upper-track staging record, an explicit duplicate policy, template health, and sound-selection rules.

The v1.1 execution phases are:

- `staging`: copy subtitle candidates to the upper review track; preserve original subtitles; do not add sound or final templates;
- `final`: apply the approved visual/audio package only after staging review and subtitle alignment are approved.

The canonical v1.1 additions are:

```json
{
  "source": {
    "content_pass": "approved",
    "subtitle_alignment": {"id": "alignment-v1", "hash": "sha256:...", "status": "approved"}
  },
  "execution": {"mode": "review", "phase": "final", "covered_subtitle_policy": "preserve"},
  "staging": {
    "required": true,
    "mode": "copy_to_upper_review_track",
    "source_timeline": "manual",
    "target_timeline": "packaged",
    "review_status": "approved",
    "original_subtitles": "preserve"
  },
  "duplicate_policy": {
    "start_tolerance_us": 40000,
    "text_must_match": false,
    "cross_track": "cover_or_delete_target",
    "same_track": "preserve_continuation"
  },
  "template_health": [{"preset_id": "question-a", "status": "verified", "font_source": "fonts[0].path"}],
  "sound_selection": {
    "reuse_cap": 3,
    "selection_order": ["motion_family", "sound_family", "reuse_cap", "semantic_special_slot"]
  },
  "visual_capability_requirements": [],
  "light_content_ops": []
}
```

## Legacy 1.0 example (migration reference)

```json
{
  "schema_version": "1.0",
  "source": {
    "draft_path": "E:/JianyingPro/JianyingPro Drafts/example",
    "timeline": "manual-reference"
  },
  "target": {
    "timeline_name": "manual-reference-packaged",
    "clone_source": true
  },
  "execution": {
    "mode": "review",
    "preserve_source": true,
    "preserve_manual_edits": true,
    "allow_in_place": false,
    "allow_manual_overwrite": false,
    "covered_subtitle_policy": "disable"
  },
  "project_profile": {
    "canvas_width": 1080,
    "canvas_height": 1920,
    "max_chars_per_line": 13,
    "ordinary_style_reference": {
      "timeline": "manual-reference",
      "segment_id": "manual-subtitle-segment"
    }
  },
  "presets": [
    {
      "preset_id": "question-a",
      "preset_type": "composite_text",
      "template_source": {
        "timeline": "question-template",
        "segment_ids": ["template-question-segment"]
      },
      "allowed_overrides": ["text", "start_us", "duration_us", "position_y"]
    }
  ],
  "groups": [
    {
      "id": "q1",
      "status": "approved",
      "range": {"start_us": 3133333, "duration_us": 3433333},
      "context": "Host asks which equipment is commonly used.",
      "category": "question",
      "level": 2,
      "motion": "reveal",
      "motion_event": {
        "start_us": 3133333,
        "peak_us": 3500000,
        "end_us": 3800000
      },
      "visual": [
        {
          "operation": "clone_template",
          "object_type": "text",
          "preset_id": "question-a",
          "target_locator": {
            "timeline": "target",
            "track_id": "target-question-text-track"
          },
          "text": "比较常见的车齿设备有哪些呢",
          "phrase_start_us": 3133333,
          "overrides": {
            "position_y": {"mode": "absolute", "value": -0.4427083333}
          }
        }
      ],
      "audio": {
        "action": "reuse_existing",
        "asset_id": "light-question-prompt-asset",
        "asset_name": "light-question-prompt",
        "sound_family": "prompt",
        "target_locator": {
          "timeline": "target",
          "segment_id": "target-prompt-segment"
        },
        "sync": {"anchor": "animation_peak", "offset_us": 0},
        "volume": 0.55,
        "reason": "The prompt lands with the second question phrase and its question animation.",
        "dedupe_tolerance_us": 1000
      },
      "risk_note": "Verify question-mark track order in Jianying."
    }
  ]
}
```

## Required fields and safety

- `execution.mode` is `review` or `apply`. In `apply` mode every non-skipped group must be `approved`.
- In v1.1, `execution.phase` is `staging` or `final`; final requires approved staging and subtitle alignment.
- `target.clone_source` and `execution.preserve_source` remain true by default. An apply plan may set either false only when `execution.allow_in_place` is true and `execution.authorization_note` is a non-empty record of the user's explicit request.
- `execution.preserve_manual_edits` remains true by default. An apply plan may set it false only when `execution.allow_manual_overwrite` is true and the same authorization note is present.
- `status` is `approved`, `review`, or `skip`; `context`, `category`, `level`, and `motion` are required for every group.
- `motion` is one of `pop`, `reveal`, `typing`, `sweep`, `impact`, `mechanical_open`, `warning_pulse`, `confirmation`, `none`, or `custom`. A `custom` motion requires `motion_note`. Any motion other than `none` requires `motion_event` with ordered `start_us`, `peak_us`, and `end_us`.
- `range.end_us`, when present, must equal `start_us + duration_us`. All timestamps are integer microseconds.
- In v1.1, `execution.covered_subtitle_policy` defaults to `preserve`. `disable_after_readback` and `delete_on_clone_after_approval` are clone-only policies; `enable=false` is never sufficient proof of coverage.
- In v1.1, every non-`none` audio action records `motion_family`, `sound_family`, `selection_basis`, and the occurrence number `reuse_count`; the validator enforces the configured reuse cap.

## Locators and operations

Use a locator object with a non-empty `timeline` and exact identifiers. A target for a new object must contain `track_id` or an explicit `track_type` selector; a target for an existing object must contain `segment_id`. A source locator must contain `segment_id`, `material_id`, or `asset_id` as appropriate. `timeline: "target"` is the symbolic name of the cloned target timeline.

| Operation | Required source | Required target |
|---|---|---|
| `clone_template` | `preset_id` whose `template_source` has timeline and segment IDs | track locator |
| `copy_from_subtitle` | source segment locator | track locator |
| `modify_text` | none | existing segment locator |
| `modify_segment` | none | existing segment locator |
| `add_overlay` | source asset/segment locator | track locator |
| `disable_original` | none | existing segment locator |
| `none` | none | none |

`visual[].object_type` is `text`, `video`, `image`, `png`, or `sticker`. Every preset has a `preset_type`, exact `template_source`, and `allowed_overrides`; every override must explicitly use `absolute/value` or `relative/delta`, and must be listed as allowed by its preset.

For a non-`none` audio action, provide `reason`, `sound_family`, a sync anchor, an exact `target_locator`, and an `asset_id` or `source_locator`. `clone_asset` and `add_asset` require a source locator. `reuse_existing` targets an existing sound segment. Valid sync anchors are `group_start`, `phrase_start`, `animation_start`, `animation_peak`, `transition_peak`, or `custom`; animation anchors require `motion_event`, while `transition_peak` and `custom` require an explicit `sync.time_us`.

If a line exceeds `max_chars_per_line`, either split it or provide a `risk_note` explaining the intentional exception. Any raw-field operation not listed as demonstrated in the capability audit requires a `risk_note` and visual verification.
