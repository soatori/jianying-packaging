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

For raw properties, prefer cloning a working segment and its referenced materials, replacing exact IDs, and changing only approved fields. Keep unknown fields intact. The schema 2.0 adapter performs candidate preparation and uses the existing `jianying-editor` transaction APIs at commit for backups, write-back, replica validation, read-back, and rollback. Unknown field mappings remain blocked pending a same-version prototype.

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

The plan, prepared report, and candidate material must use one microsecond
duration: `min(preset_default_duration_us, visible_text_row_duration_us)`.
Write the exact inventory cache subdirectory to the animation payload. Clamp
before writing, not after the UI has cropped the animation.

## Replica roles and transparency

During prepare and commit source checks, only a mismatch for a positively
associated `writable-backup` is a warning. Primary/template mismatch and
missing, unreadable, or unassociated replica candidates block. Post-write
validation remains strict across the transaction-managed target replicas.

Write transparency to `segment.global_alpha` only when the current text
segment prototype confirms that field and its range. Keep `segment.visible`
separate for hiding. A preview must show both the effective alpha and
visibility state.


## Exact capability tokens

The capability file is matched by literal values. A near-miss token silently
downgrades to "unverified", so these are the exact strings:

| Field | Required value | Common wrong value |
| --- | --- | --- |
| top-level | `jianying_version` must be a string **strictly equal** to the running editor version | omitting it, or writing a range like `">=11"` |
| `verified[].status` | `visually_verified` | `visual_verified`, `verified`, `verified_visual` |
| `verified[].target_kind` | `plain_text` | `text`, `subtitle`, `plain-text` |
| `verified[].required_inputs` | array; **empty** for plain text | omitting it when the preset needs `words` |
| `verified[].resource_id` / `md5` | both present and exact | inventing an md5 from the display name |

`validate capabilities` reports the expected token next to the observed one, so a
typo is caught before `prepare` fails on it. A ready-to-copy shape lives in
[animation-capabilities.example.json](animation-capabilities.example.json).

Two different presets can share a display name (`渐显` exists as both a video and a
sticker animation). Match on `resource_id` + `md5`, never on the name.

## Reference-draft harvesting

Discovering what this machine can actually render is legitimate; sweeping the
machine is not.

- Allowed input: the reference drafts named explicitly for the current case, at
  most five, plus the local `Cache/effect` tree.
- Bounded output: at most 200 items per harvest, with the scanned timeline ids and
  the note recorded as provenance.
- Everything found starts `unverified`. A cache directory existing proves the
  asset was downloaded once; it does not prove plain-text rendering on this
  version. Promotion to `visually_verified` requires a reopen-and-review by a
  person.
- Never enumerate every saved draft, and never scan a whole drive. `catalog-harvest`
  and `animation-inventory` enforce the caps; do not bypass them with ad-hoc
  scripts.
