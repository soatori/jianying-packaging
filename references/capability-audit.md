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

For raw properties, prefer cloning a working segment and its referenced materials, replacing exact IDs, and changing only approved fields. Keep unknown fields intact. `jianying-editor` owns project probing, backups, write-back, replica validation, read-back, and rollback; this skill owns semantic packaging decisions and the evidence needed for them.
