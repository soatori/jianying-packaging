# DONE — 2026-09-16 Review Fixes

Plan: `docs/superpowers/plans/2026-09-16-review-fixes.md`

## Status: complete

All 6 tasks executed. Zero files deleted.

## Commits

| Task | Commit | Summary |
|------|--------|---------|
| 1 | `888b125` | Rewrite description for SDO and Chinese triggers |
| 2 | `5b099e0` | Collapse sound docs into semantic-packaging single source |
| 3 | `7ef41d3` | Flower-text MD becomes overview; geometry stays in JSON |
| 4 | `a08b2da` | Abstract host paths in capability-audit |
| 5 | `55ff696` | Relax tolerance and selection_order gates with tests |
| 6 | `3b178ad` | Co-install note and light-content pointer |

## Done criteria

- [x] Description has Use when + Chinese triggers (花字, 音效, 上轨) + negatives (Do NOT use) — 416 chars ≤ 1024
- [x] Sound knowledge has one canonical table (`semantic-packaging.md#sound-choice`); `sfx-palette.md` is a pointer
- [x] Flower-text MD no longer dumps JSON geometry — overview table + special rules only
- [x] No host absolute paths in capability-audit (`<user-draft-root>`, `<jianying-install-or-material-root>`)
- [x] Validator accepts custom positive tolerance (e.g. 25000) and flexible selection_order (non-empty known keys)
- [x] All packaging unit tests pass: **15/15 OK**
- [x] Zero files deleted

## Test evidence

```
Ran 15 tests in 0.002s
OK
```

New tests:
- `test_tolerance_may_override_default` — was FAIL before relaxation, now PASS
- `test_selection_order_accepts_nonempty_known_keys` — was FAIL before relaxation, now PASS

## Skill structure validation

```
PASS: 0 error(s), 1 warning(s)
```

Warning: cross-skill relative link to `../jianying-rough-cut/references/workflow-state.md` — expected and documented as intentional.

## Deferred (not done this phase)

Per plan: `agents/openai.yaml`, `sfx-palette.md`, `light-content-policy.md` deletion; flower-text JSON archaeology; validate_plan split; `__pycache__` purge.
