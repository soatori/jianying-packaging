# jianying-packaging Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix P0–P2 review findings without deleting files in this phase — restore discoverability (description/SDO), collapse triple-duplicated sound docs into one source of truth, relax two over-strict validator gates, and abstract host-specific paths.

**Architecture:** Edit `SKILL.md` frontmatter and sound section in place; rewrite `references/sfx-palette.md` as a thin pointer (do not delete); shrink `references/flower-text-templates.md` to overview-only; tighten `references/capability-audit.md` paths; relax two equality checks in `scripts/validate_packaging_plan.py` with new unit tests first.

**Tech Stack:** Markdown, Python 3 stdlib (`unittest`, `importlib.util`)

**Spec:** `C:\Users\cbsjz\Desktop\skills\jianying-packaging\REVIEW.md` (sections 1.2, 2, 3, 4)

## Global Constraints

- **No file deletions in this plan.** `agents/openai.yaml`, `references/sfx-palette.md`, and `references/light-content-policy.md` stay on disk; deferred list at the end.
- Do not weaken fail-closed safety gates, schema 1.0 migration path, or Boundaries section.
- Every validator change must keep `scripts/test_validate_packaging_plan.py` green and add coverage for the new behavior.
- Cross-skill relative link to `../jianying-rough-cut/references/workflow-state.md` must remain intact.
- Description must stay under 1024 characters, start with trigger conditions, include Chinese literal phrases, and keep negative triggers.

## File Map

| File | Change |
|------|--------|
| `SKILL.md` | Rewrite description; compress Sound execution rules; note co-install deps |
| `references/sfx-palette.md` | Replace body with pointer to `semantic-packaging.md` |
| `references/flower-text-templates.md` | Keep overview table + special rules; point geometry to JSON |
| `references/capability-audit.md` | Replace absolute `D:/` `E:/` paths with generic descriptions |
| `references/plan-schema.md` | Document default tolerance 40000 and flexible selection_order |
| `scripts/validate_packaging_plan.py` | Relax two equality checks |
| `scripts/test_validate_packaging_plan.py` | Add 2 tests for relaxed gates |

---

### Task 1: Rewrite packaging description (SDO)

**Files:**
- Modify: `SKILL.md:1-4` (frontmatter only)

**Interfaces:**
- Consumes: current description text (see REVIEW §1.2)
- Produces: new `description` field used by skill catalog / skill_search

- [ ] **Step 1: Replace description**

Replace the entire YAML `description` value with:

```yaml
description: Use when packaging or polishing an already content-stable Jianying Pro / 剪映 timeline — flower text (花字), upper-track emphasis (上轨强调), templates, animation, transitions, or sound effects (加音效/卡点音效). Requires approved content pass and subtitle alignment. Do NOT use for rough-cut content decisions, transcription, or draft decryption/version recovery; use jianying-rough-cut and jianying-editor for those.
```

- [ ] **Step 2: Verify frontmatter constraints**

Run:

```powershell
$desc = (Select-String -Path SKILL.md -Pattern '^description:').Line
if ($desc.Length -gt 1024) { throw "description too long: $($desc.Length)" }
# must contain Use when, 花字, 包装 is optional but 音效/上轨 required
$desc
```

Expected: description starts with `Use when`, contains `花字`, `音效`, `Do NOT use`, length ≤ 1024.

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "fix(packaging): rewrite description for SDO and Chinese triggers"
```

---

### Task 2: Collapse sound docs to one source of truth (no delete)

**Files:**
- Modify: `SKILL.md:60-68` (Sound execution rules)
- Modify: `references/sfx-palette.md` (entire body)

**Interfaces:**
- Consumes: `references/semantic-packaging.md` `## Sound choice` section (canonical table)
- Produces: SKILL.md holds only 3 hard rules; sfx-palette becomes a pointer

- [ ] **Step 1: Rewrite Sound execution rules in SKILL.md**

Replace the current `## Sound execution rules` section body with:

```markdown
## Sound execution rules

- At most one primary sound per semantic animation group unless the approved design explicitly requires a layer.
- Align to the perceptual landing point (`animation_peak` or `transition_peak` when that is where the motion lands); do not auto-align every sound to segment start. Fail closed when duration, mask, or dialogue collision is unresolved.
- Select motion family → sound family → reuse cap (default 3) → semantic special slot. The canonical table and selection detail live in [references/semantic-packaging.md](references/semantic-packaging.md#sound-choice). Do not infer a sound from a cache md5. Preserve manual replacements/deletions and record rationale.
```

- [ ] **Step 2: Rewrite `references/sfx-palette.md` as pointer (keep file)**

Replace entire file content with:

```markdown
# SFX Palette (pointer)

Canonical motion→sound mapping and selection rules live in
[semantic-packaging.md](semantic-packaging.md#sound-choice).

This file remains only as a stable inbound link. Do not duplicate tables here.
```

- [ ] **Step 3: Confirm semantic-packaging has the table**

Run:

```powershell
Select-String -Path references/semantic-packaging.md -Pattern '## Sound choice'
```

Expected: at least one match. If missing, do not proceed — restore sfx-palette from git and re-read semantic-packaging.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md references/sfx-palette.md
git commit -m "refactor(packaging): collapse sound docs into semantic-packaging single source"
```

---

### Task 3: Shrink flower-text MD to overview + special rules

**Files:**
- Modify: `references/flower-text-templates.md`

**Interfaces:**
- Consumes: `references/flower-text-templates.json` (authoritative geometry/locators)
- Produces: shorter MD; JSON remains machine source

- [ ] **Step 1: Keep only these MD sections**

Retain/rewrite so the file contains:

1. Purpose (2–3 sentences)
2. Overview table of the 14 selected templates (id, one-line use, level hint)
3. Special rules that are NOT in JSON (question-mark layer order, font health, same-group fallback, text-fit line rules) — copy those paragraphs from the current file if present
4. Explicit note: **layer geometry, relative positions, and exact locators are defined only in `flower-text-templates.json`**

Remove per-template layer dumps that duplicate JSON (the 14 detailed layer tables called out in REVIEW §3.1).

- [ ] **Step 2: Word count sanity**

```powershell
(Get-Content references/flower-text-templates.md | Measure-Object -Word).Words
```

Expected: target ≈ 800–1200 words (down from ~2554). If still >1800, another duplicate block remains.

- [ ] **Step 3: Commit**

```bash
git add references/flower-text-templates.md
git commit -m "refactor(packaging): flower-text MD becomes overview; geometry stays in JSON"
```

---

### Task 4: Abstract host-specific paths in capability-audit

**Files:**
- Modify: `references/capability-audit.md`

**Interfaces:**
- Consumes: current absolute paths like `D:/Users/...`, `E:/JianyingPro/...`
- Produces: portable descriptions

- [ ] **Step 1: Replace absolute paths**

Replace every absolute Windows path with a generic token + note:

- `D:/Users/...` → `<user-draft-root>/...` (example draft path on author machine)
- `E:/JianYingPro/...` or `E:/JianyingPro/...` → `<jianying-install-or-material-root>/...`

Add at top of file (after title) one line:

```markdown
> Paths below are evidence provenance examples, not runtime requirements. Always use the user-provided draft path.
```

- [ ] **Step 2: Verify no drive-letter paths remain**

```powershell
Select-String -Path references/capability-audit.md -Pattern '[A-Za-z]:/'
```

Expected: no matches (or only intentional non-path citations — none expected).

- [ ] **Step 3: Commit**

```bash
git add references/capability-audit.md
git commit -m "docs(packaging): abstract host paths in capability-audit"
```

---

### Task 5: Relax two over-strict validator gates (TDD)

**Files:**
- Modify: `scripts/test_validate_packaging_plan.py`
- Modify: `scripts/validate_packaging_plan.py:300-345`
- Modify: `references/plan-schema.md` (document the defaults)

**Interfaces:**
- Consumes: `valid_plan()` fixture with `start_tolerance_us: 40000` and fixed `selection_order`
- Produces: validator accepts positive tolerance ≠ 40000 and any non-empty known-key selection_order list

- [ ] **Step 1: Write failing tests**

Append to `scripts/test_validate_packaging_plan.py` (same class style as existing tests):

```python
    def test_tolerance_may_override_default(self):
        plan = valid_plan()
        plan["duplicate_policy"]["start_tolerance_us"] = 25_000
        result = VALIDATOR.validate_plan(plan)
        self.assertTrue(result["ok"], result)

    def test_selection_order_accepts_nonempty_known_keys(self):
        plan = valid_plan()
        plan["sound_selection"]["selection_order"] = ["sound_family", "motion_family"]
        result = VALIDATOR.validate_plan(plan)
        self.assertTrue(result["ok"], result)
```

If the module exposes validation under a different function name than `validate_plan`, inspect the existing tests and match that name exactly (do not invent).

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
Set-Location C:\Users\cbsjz\Desktop\skills\jianying-packaging
& $env:MIMO_PYTHON -m unittest scripts.test_validate_packaging_plan -v
```

Expected: the two new tests FAIL (`start_tolerance_us must be 40000us` / `selection_order must document...`).

- [ ] **Step 3: Implement relaxation**

In `validate_packaging_plan.py`, replace the tolerance equality check:

```python
        elif tolerance != 40_000:
            errors.append("duplicate_policy.start_tolerance_us must be 40000us")
```

with:

```python
        # default is 40000us; any positive integer override is allowed
```

(so only the positive-integer check remains).

Replace the selection_order equality check:

```python
        if sound_selection.get("selection_order") != ["motion_family", "sound_family", "reuse_cap", "semantic_special_slot"]:
            errors.append("sound_selection.selection_order: must document motion-to-sound selection")
```

with:

```python
        order = sound_selection.get("selection_order")
        if not isinstance(order, list) or not order:
            errors.append("sound_selection.selection_order: must be a non-empty array")
        else:
            allowed = {"motion_family", "sound_family", "reuse_cap", "semantic_special_slot"}
            if any((not isinstance(key, str)) or key not in allowed for key in order):
                errors.append("sound_selection.selection_order: unknown selection key")
```

- [ ] **Step 4: Run full packaging tests — expect PASS**

```powershell
& $env:MIMO_PYTHON -m unittest scripts.test_validate_packaging_plan -v
```

Expected: all tests OK (previous 13 + 2 new).

- [ ] **Step 5: Document in plan-schema.md**

In `references/plan-schema.md` near the duplicate_policy / sound_selection examples, note:

```markdown
- `start_tolerance_us` defaults to `40000` but any positive integer is valid.
- `selection_order` must be a non-empty list of known keys (`motion_family`, `sound_family`, `reuse_cap`, `semantic_special_slot`); order may vary.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/test_validate_packaging_plan.py scripts/validate_packaging_plan.py references/plan-schema.md
git commit -m "fix(packaging): relax tolerance and selection_order gates with tests"
```

---

### Task 6: Co-install note + residual cleanup (no delete)

**Files:**
- Modify: `SKILL.md` (Boundaries)

**Interfaces:**
- Consumes: cross-skill link to workflow-state.md
- Produces: explicit co-install requirement

- [ ] **Step 1: Add co-install sentence**

In `## Boundaries`, after the workflow-state bullet, add:

```markdown
- This skill assumes `jianying-rough-cut` and `jianying-editor` are installed as sibling skills. The relative link to rough-cut workflow state is intentional, not a broken path.
```

- [ ] **Step 2: Optional merge note (content only)**

If `references/light-content-policy.md` content is short and unique, append its rules into `plan-schema.md` under `light_content_ops` as a sub-bullet list, but **keep the original file** (no delete this phase). Leave a one-line pointer in light-content-policy.md:

```markdown
Canonical rules are in [plan-schema.md](plan-schema.md) under `light_content_ops`. This file remains for inbound links.
```

- [ ] **Step 3: Validate structure**

```powershell
# if skill-creator validator is available
& $env:MIMO_PYTHON "C:\Users\cbsjz\.local\share\mimocode\builtin_skills\desktop-5198ff5\skills\skill-creator\scripts\validate_skill.py" .
```

Expected: PASS, 0 errors (workflow-state warning may remain until sibling skill present — acceptable).

- [ ] **Step 4: Final commit**

```bash
git add SKILL.md references/light-content-policy.md references/plan-schema.md
git commit -m "docs(packaging): co-install note and light-content pointer"
```

---

## Deferred (NOT in this plan — user said 先不删除)

1. Delete `agents/openai.yaml`
2. Delete `references/sfx-palette.md` after inbound links are updated
3. Delete `references/light-content-policy.md` after merge is proven
4. Delete `not_selected` archaeology from `flower-text-templates.json`
5. Split 550-line `validate_plan()` (optional; low priority)
6. `__pycache__` purge if tracked

## Done criteria

- [ ] Description has Use when + Chinese triggers + negatives
- [ ] Sound knowledge has one canonical table
- [ ] flower-text MD no longer dumps JSON geometry
- [ ] No host absolute paths in capability-audit
- [ ] Validator accepts custom positive tolerance and flexible selection_order
- [ ] All packaging unit tests pass
- [ ] Zero files deleted
