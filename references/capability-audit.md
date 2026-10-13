# Evidence-based capability audit

Use this reference to decide whether an operation is supported by the current Jianying version and target project. A field name or a result from another project does not prove that a write is safe or visible.

## Evidence levels

| Level | Meaning | Use |
|---|---|---|
| Schema observation | A property or object exists in decoded data | Discovery only; not proof of render behavior |
| Prototype verified | A small edit to a confirmed object was saved and read back | Supports only the tested field, object type, and application version |
| Visual/audio verified | The reopened project visibly renders or audibly plays the result as intended | Supports the tested presentation on that project and version |
| Unsupported/unknown | No reliable proof, or evidence conflicts | Keep in review; do not write by guessing |

## Audit procedure

1. Resolve the current saved timeline and preserve the user's latest edits.
2. Identify the target object and its complete referenced material closure.
3. Inspect a user-confirmed prototype from the same project and Jianying version.
4. Test only the requested field on a clone or reversible prototype.
5. Save, read back the result, compare untouched fields, then reopen and visually or audibly verify when presentation matters.
6. Record the evidence level, tested version, limits, and remaining review requirement in the external case record.

## Operations that need project evidence

Confirm support separately for text/style mirrors, coordinate conversion, layer ordering, visibility, animation materials, sound placement/cropping/volume, transitions, masks, and other effect fields. Do not infer that support for one object type or one version transfers to another.

For raw properties, prefer cloning a working segment and its referenced materials, replacing exact IDs, and changing only approved fields. Keep unknown fields intact. The schema 1.2 packaging adapter performs plan translation and calls the existing `jianying-editor` transaction APIs for backups, write-back, replica validation, read-back, and rollback. Unknown field mappings remain blocked pending a same-version prototype.

## Animation resources

For TextIntro-based entrance animations, intersect the current `TextIntro`
enumeration with the running installation's `Cache/effect/<resource_id>/<md5>`
directories. Resolve exactly one matching directory; never guess between
resource/effect IDs or infer a path from display metadata. Keep the inventory
and native capability evidence outside the generic Skill so each run records
the current Jianying version, resource hash, type, required input data, and
reopen result.

File type is a clue, not a version-independent compatibility rule. Treat
unknown resource types, unresolved cache paths, version mismatch, missing
required input data, or missing plain-text evidence as blockers. A script can
require per-word/per-character payload unavailable to ordinary text. A shader
resource also needs same-version evidence before it is treated as compatible.
The generated HTML and successful JSON read-back do not prove that Jianying
retains the effect after reopening.

The plan, apply report, and candidate material must use one microsecond
duration: `min(preset_default_duration_us, visible_text_row_duration_us)`.
Write the exact inventory cache subdirectory to the animation payload. Clamp
before writing, not after the UI has cropped the animation.

## Replica roles and transparency

During read-only checks and apply dry-run, only a mismatch for a positively
associated `writable-backup` is a warning. Primary/template mismatch and
missing, unreadable, or unassociated replica candidates block. Post-write
validation remains strict across the transaction-managed target replicas.

Write transparency to `segment.global_alpha` only when the current text
segment prototype confirms that field and its range. Keep `segment.visible`
separate for hiding. A preview must show both the effective alpha and
visibility state.
