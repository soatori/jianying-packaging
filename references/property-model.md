# Packaging property model

Use semantic property names in plans. Map them to raw Jianying fields only after inspecting the target version and a confirmed prototype.

## Parameter operation

Every override is either absolute or relative:

```json
{
  "position_y": {"mode": "absolute", "value": -0.4427083333},
  "scale": {"mode": "relative", "delta": 0.15}
}
```

An inherited template property is omitted. Never encode inheritance as a guessed default value.

## Common semantic variables

| Domain | Variables |
|---|---|
| Timing | `start_us`, `duration_us`, `end_us`, `source_start_us`, `source_duration_us`, `audio_offset_us` |
| Transform | `position_x`, `position_y`, `scale_x`, `scale_y`, `uniform_scale`, `rotation`, `opacity`, `anchor_x`, `anchor_y` |
| Text | `text`, `font_family`, `font_resource_id`, `font_size`, `font_weight`, `letter_spacing`, `line_spacing`, `alignment`, `fill_color`, `stroke_width`, `stroke_color`, `shadow`, `background`, `text_box` |
| Motion | `animation_in`, `animation_out`, `animation_loop`, `animation_duration_us`, `animation_peak_offset_us`, `keyframes` |
| Video/image | `crop`, `mask`, `feather`, `blend`, `speed`, `freeze`, `transform`, `keyframes` |
| Audio | `volume`, `last_nonzero_volume`, `fade_in_us`, `fade_out_us`, `speed`, `channel_mapping`, `source_range`, `target_range` |
| Composition | `track_id`, `track_order`, `render_index`, `track_render_index`, `visible`, `group_id` |

## Evidence status by object

### Text

Demonstrated mappings in the current draft:

- visible string: JSON strings in material `content` and sometimes `base_content`; `recognize_text` can mirror recognized subtitle text;
- font: top-level `font_path`, `font_resource_id`, `fonts`, and nested `content.styles[].font`;
- size: top-level `font_size` and nested `content.styles[].size`;
- color: top-level `text_color` and nested `content.styles[].fill`;
- shadow: top-level `has_shadow` and shadow fields plus nested `content.styles[].shadows`;
- border: top-level `border_width`/`border_color` and possible nested style data;
- position/scale: segment `clip.transform.x/y`, `clip.scale.x/y`, and version-dependent `uniform_scale`;
- layer and visibility: track order, `track_render_index`, `render_index`, and segment `visible`;
- animation/template dependencies: segment `extra_material_refs` leading to material animations, effects, and drafts.

Do not update only one representation. Either clone the complete confirmed prototype or update every representation that exists and verify the UI result.

### Video

Observed in the current draft:

- segment source and target timeranges;
- segment `clip.scale`, `clip.transform`, and `flip`;
- material path, dimensions, duration, and `crop`;
- transition materials and referenced animation/effect materials.

Rotation, opacity, masks, feather, blend, freeze, speed, and keyframes are semantic variables but were not demonstrated by this packaging workflow. Use a working prototype or run a small cloned-timeline experiment before relying on raw fields.

### Image, PNG, and sticker

No standalone sticker track was present in the audited active timeline. Treat these as template/media objects:

1. locate a working source segment created by Jianying;
2. copy its material closure and track behavior;
3. replace only the media path/content and approved transform/timing fields;
4. validate and visually inspect.

Do not assume an image and sticker share the same material schema.

### Audio and sound effects

Demonstrated mappings:

- audio identity in material `name`, `path`, `resource_id`, `effect_id`, and source platform fields;
- placement and crop in segment `target_timerange` and `source_timerange`;
- loudness through segment `volume` and `last_nonzero_volume` when present;
- dependencies through `extra_material_refs` such as fades, beats, channel mappings, or loudness metadata.

Preserve the complete source segment and material closure. Override placement, source crop, duration, and volume only when approved. Fade and channel changes need template or version-specific confirmation.

## Coordinate conversion

The audited vertical project stored a UI Y setting of `-850` as approximately `-850 / 1920 = -0.4427083333`. This is evidence of a normalized coordinate in that project, not a universal constant.

For every project:

1. identify canvas dimensions;
2. read a user-confirmed segment with known UI position;
3. derive the conversion and sign convention;
4. compare a second reference if available;
5. visually verify after reopening Jianying.

## Preset model

```json
{
  "preset_id": "question-template-a",
  "preset_name": "Question Template A",
  "preset_type": "composite_text",
  "template_source": {
    "timeline": "question-template",
    "segment_ids": ["..."],
    "material_ids": ["..."]
  },
  "inherits": ["style", "animation", "geometry", "layering"],
  "default_parameters": {},
  "allowed_overrides": ["text", "start_us", "duration_us", "position_y"],
  "requires_visual_verification": true
}
```

Composite presets may include multiple text layers, graphics, animation materials, and one optional sound event. Keep their internal layer relationship intact.
