# jianying-packaging 完整审查报告

只读诊断，未改动任何 skill 文件。审查日期：2026-02-18。方法：skill-creator 结构/触发诊断 → writing-skills SDO/词数约束 → ponytail-audit 扫 scripts/agents。

## 0. 执行摘要

| 维度 | 结论 |
|---|---|
| skill-creator 结构 | **PASS**（0 error / 1 warning） |
| 触发（description） | **有问题** — 以 WHAT 开头、汇总了流程、缺中文口语触发词 |
| SDO / 词数 | **超重** — SKILL.md 1518 词；音效选择在 3 处重复 |
| 单元测试 | **13/13 OK** |
| ponytail 最大可删 | flower-text 双份明细 + sfx-palette 重复 + openai.yaml + JSON 考古段 |
| 优先修复 | P0 改 description；P0 去重音效文档 |

---

## 1. skill-creator 结构 / 触发诊断

### 1.1 结构检查（对照 validate_skill.py 与 checklist）

| 检查项 | 结果 |
|---|---|
| 目录 kebab-case 且与 `name` 一致 | ✅ `jianying-packaging` |
| 文件名精确 `SKILL.md` | ✅ |
| 无 skill 内 README.md | ✅ |
| frontmatter 有 `---` / `name` / `description` | ✅ |
| description ≤ 1024 字符 | ✅ 439 |
| frontmatter 无 XML 尖括号 | ✅ |
| 保留前缀 | ✅ 非 claude/anthropic |
| 内部 references 均存在 | ✅ 9 个 md + 1 json 全在 |
| `validate_skill.py` | **PASS：0 error，1 warning** |
| 单元测试 `test_validate_packaging_plan.py` | **13/13 OK** |
| `py_compile` 校验脚本 | ✅ |
| `__pycache__` | 已在 `.gitignore`，仅本地缓存 |

**唯一 WARNING：**

```
WARNING: SKILL.md references 'references/workflow-state.md' but it does not exist in the skill folder
```

对应正文：

```markdown
[the rough-cut workflow reference](../jianying-rough-cut/references/workflow-state.md)
```

这是**跨 skill 相对路径**。实测兄弟 skill 存在且文件在：

- `Desktop/skills/jianying-rough-cut/references/workflow-state.md` ✅
- `jianying-rough-cut` frontmatter `name: jianying-rough-cut` ✅
- `jianying-editor-skill` 目录 frontmatter `name: jianying-editor`（与正文引用一致）✅

**判定：** 多 skill 工作流的有意设计，不是断链。建议在 SKILL.md 加一句“需与 jianying-rough-cut / jianying-editor 同装”，避免 validator 与新环境误解。

### 1.2 触发诊断（关键问题）

当前 description：

```text
Plan, review, and execute post-rough-cut visual and sound packaging in existing Jianying Pro timelines,
including upper-track staging, semantic emphasis, reusable templates, animation/effects, transitions,
and sound effects. Use after content and subtitle alignment are stable; use jianying-editor for draft
access and safe write-back. Do not use for rough-cut content decisions, transcription, or draft
decryption/version recovery itself.
```

| 问题 | 影响 |
|---|---|
| 以 **WHAT**（Plan, review, and execute…）开头，不是 **Use when…** | writing-skills 明确要求描述只写触发条件 |
| **汇总了流程/能力清单**（staging / templates / animation / transitions） | SDO 陷阱：agent 可能照 description 动手，跳过 SKILL.md 的 fail-closed 规则 |
| **缺中文口语触发词** | 本 skill 面向剪映中文工作流，用户更可能说「包装」「花字」「加音效」「强调字幕」「上轨」 |
| 负向触发已有 | ✅ Do not use for rough-cut / transcription / decryption |

**高风险触发场景：**

- 「帮我给这条时间线做包装」→ description 无「包装」中文词，可能 miss 或误路由
- 「用花字强调关键句」→ 无「花字」
- 「给动画配上音效」→ 只有英文 “sound effects”
- 「剪映包装」/「上轨字幕」→ 无

**建议 description 方向（仅提案，本次未改文件）：**

```yaml
description: Use when the user asks to package, polish, or emphasize an already content-stable Jianying Pro timeline with flower-text, upper-track highlights, templates, animation, transitions, or sound effects — including phrases like 包装, 花字, 加音效, 强调字幕, 上轨, packaging, flower text. Requires approved content + subtitle alignment. Do NOT use for rough-cut content decisions, transcription, or draft decryption/version recovery; use jianying-rough-cut and jianying-editor for those.
```

要点：触发条件优先；中英口语词；流程细节留给 body；保留负向触发。

---

## 2. writing-skills SDO / 词数约束

### 2.1 词数现状

| 文件 | 词数 | 字符 | 评估 |
|---|---:|---:|---|
| **SKILL.md** | **1518** | 11195 | skill-creator 上限 ~5000 ✅；writing-skills 非常加载 skill 建议 <500 ❌（约 3×） |
| references/plan-schema.md | 859 | 7996 | 可接受（按需加载） |
| references/capability-audit.md | 888 | 6476 | 可接受 |
| references/semantic-packaging.md | 561 | 3670 | 可接受 |
| references/property-model.md | 626 | 5185 | 可接受 |
| references/flower-text-templates.md | **2554** | 21679 | 偏重，且与 JSON 大量重复 |
| references/flower-text-templates.json | **12090** | **230968** | 机器可读合理，但含考古段 |
| references/staging-and-covered-subtitles.md | 259 | 1799 | 精简 |
| references/sfx-palette.md | 184 | 1137 | **几乎全是重复** |
| references/light-content-policy.md | 123 | 926 | 可并入 plan-schema |
| scripts/validate_packaging_plan.py | 3483 | 43579 | 安全门禁，thorough 合理 |
| scripts/test_validate_packaging_plan.py | 745 | 11267 | 保留 |

SKILL.md 1518 词对复杂安全编排 skill 来说**不极端**，但相对 writing-skills 的 <500 仍偏重；真正的问题是**跨文件重复**，不是单文件爆炸。

### 2.2 SDO / 重复矩阵（核心发现）

| 内容 | SKILL.md | semantic-packaging | sfx-palette | plan-schema | validator |
|---|---|---|---|---|---|
| category 枚举 | 简写 | 全量 | — | — | `CATEGORIES` |
| motion 枚举 | 简写 | — | — | 全量 | `MOTIONS` |
| motion→sound 表 | — | 全量 | **几乎相同** | — | — |
| 音效选择规则 | 9 条 | Sound 章节 | 选择顺序 | audio schema | audio 校验 |
| covered subtitle | 1 条 | — | — | policies | `COVERED_SUBTITLE_POLICIES` |
| light_content_ops | 1 条 | — | — | required | `LIGHT_CONTENT_OPERATIONS` |

**判定：** `references/sfx-palette.md` 与 `semantic-packaging.md` 的 Sound choice 表几乎一字不差地重复；SKILL.md「Sound execution rules」又第三遍重述。agent 每次 load 全文都要吞三份。

### 2.3 description SDO 违规（与 skill-creator 合并）

见 §1.2。writing-skills 铁律：**description = When to use，绝不汇总 process**。当前描述违反。

### 2.4 progressive disclosure 评估

正面：

- 工作流状态、schema、属性映射、能力审计、staging 政策都正确下沉到 references
- 校验逻辑用脚本而非散文（符合 skill-creator「关键校验用 script」）
- fail-closed 规则在 SKILL.md 顶部 Boundaries + Safe execution，位置正确

待改进：

- 音效选择规则未收敛到单一来源
- flower-text 人类可读 MD 与机器可读 JSON 各写一遍层表
- capability-audit 内嵌 `D:/Users/11/...`、`E:/JianyingPro/...` 本机绝对路径，换机即失效

---

## 3. ponytail-audit（scripts / agents / references）

范围：过度工程与可删项。正确性/安全洞/性能不在本轮。

### 3.1 Ranked findings

| Tag | What to cut | Replacement | Path |
|---|---|---|---|
| `delete` | `agents/openai.yaml`（display_name + default_prompt） | MiMo Desktop 不读该文件；除非明确要投 OpenAI skill 市场 | `agents/openai.yaml` |
| `delete` | `sfx-palette.md` 全文 | `semantic-packaging.md` Sound choice 已有同表；SKILL.md 保留选择顺序一句即可 | `references/sfx-palette.md` |
| `shrink` | flower-text MD 里 14 份逐模板层表（与 JSON 重复） | 保留顶部速览表 + 特殊规则（问号层、字体健康）+ 指向 JSON | `references/flower-text-templates.md` |
| `delete` | JSON `not_selected`（54 个源序号 + 淘汰理由） | 运行时不用；若要审计历史，移出 skill 或压成一句「已筛 54 选 14」 | `references/flower-text-templates.json` |
| `shrink` | JSON 里与 MD 重复的 `relative_layout` 全文、本机字体绝对路径 | 相对坐标保留；路径改为字体名 + health 状态 | 同上 |
| `shrink` | SKILL.md「Sound execution rules」9 条与 references 重复的部分 | 收敛为 3 条硬规则 + 指向 semantic-packaging | `SKILL.md:60-68` |
| `yagni` | validator 强制 `start_tolerance_us == 40000` 精确相等 | 默认 40000，允许正整数覆盖 | `validate_packaging_plan.py:307-308` |
| `yagni` | `sound_selection.selection_order` 必须与固定数组逐项相等 | 校验为「已知键的非空列表」 | `validate_packaging_plan.py:344-345` |
| `shrink` | 音效重复计数双轨：`reuse_count` 字段 + `sound_counts` 运行时累计再交叉验证 | 保留累计校验即可，字段只作文档或删字段 | `validate_packaging_plan.py:807-811, 909-917` |
| `shrink` | `validate_plan()` 单函数 550 行 / 145 个 errors.append | 按 source/target/execution/groups/audio 拆分（可选，测试已覆盖） | `validate_packaging_plan.py:384-931` |
| `shrink` | light-content-policy.md（123 词）独立文件 | 并入 plan-schema「light_content_ops」小节 | `references/light-content-policy.md` |
| `native` | 手写 is_int/is_number/is_nonempty_string | 不可删：bool 排除是 stdlib 没有的语义 | — |

### 3.2 不该动的部分（明确保留）

- **`validate_packaging_plan.py` 主体**：安全门禁，skill-creator 明确偏好「关键校验用脚本」。966 行对 schema 契约是合理成本；13 个测试全绿。
- **schema 1.0 读路径**：legacy warning + 禁 apply 是正确的迁移设计，不是 yagni。
- **capability-audit.md**：证据链有价值；只需抽象本机路径。
- **Boundaries / fail-closed 段**：这是 skill 的核心价值，不要为省词砍。
- **14 个已选 flower-text 模板本体**：真实可用资产，保留 JSON 定位符。

### 3.3 净削减估算

| 动作 | 估算 |
|---|---|
| 删 sfx-palette.md | −184 词 / −1.1 KB |
| 压 flower-text-templates.md 层表 | −约 1500 词 / −约 12 KB |
| 删 JSON not_selected + 考古 | −约 1–2 KB 结构 + 可读性提升 |
| 删 openai.yaml | −4 行 / −270 B |
| SKILL.md 音效段去重 | −约 80–120 词 |
| **合计** | **约 −1800–2000 词，−15–20 KB** |

---

## 4. 优先修复项

### P0（触发/可用性，先做）

1. **重写 description**：`Use when…` + 中文口语触发（包装/花字/音效/强调字幕/上轨）+ 保留负向触发；**删掉流程能力清单**。
2. **音效文档三合一**：删 `sfx-palette.md`；SKILL.md 只留「每组至多一个主音 + 对齐 perceptual peak + fail-closed」；细节只留 `semantic-packaging.md`。

### P1（体积与一致性）

3. **flower-text MD 只留速览表 + 特殊规则**，层几何一律以 JSON 为准。
4. **JSON 删 `not_selected` 考古段**；字体绝对路径改为字体名。
5. **validator 放宽两处过约束**（tolerance 精确 40000、selection_order 精确数组）；改后必须跑 `test_validate_packaging_plan.py`。

### P2（整理）

6. 确认是否需要 `agents/openai.yaml`；不需要则删。
7. light-content-policy.md 并入 plan-schema。
8. capability-audit 中绝对路径改为「某项目草稿路径」描述。
9. SKILL.md 注明依赖同装 `jianying-rough-cut`、`jianying-editor`，消解跨 skill warning。

---

## 5. 健康度结论

这个 skill **工程完成度高**：边界清晰、fail-closed、有确定性校验脚本、有回归测试、有证据审计。主要问题不是「缺功能」，而是：

1. **触发面偏窄且偏英文** — 中文用户口语可能根本 load 不到；
2. **描述把流程写进 frontmatter** — 有被 agent 捷径绕过 body 规则的风险；
3. **同一套音效/模板知识写了 2–3 遍** — token 浪费 + 维护漂移风险。

按 P0 → P1 做完，预期：触发命中率上升、SKILL.md 有效信息密度上升、references 减重约 15–20KB，安全语义不丢。

---

## 附录 A. 验证命令与结果

```text
python scripts/validate_skill.py <jianying-packaging>
→ PASS: 0 error(s), 1 warning(s)
   WARNING: references/workflow-state.md 不在 skill 内（跨 skill 路径，文件实际存在于兄弟 skill）

python -m unittest scripts/test_validate_packaging_plan.py -v
→ Ran 13 tests in 0.001s — OK

python -m py_compile scripts/validate_packaging_plan.py
→ OK
```

## 附录 B. 文件清单（审查范围）

```text
jianying-packaging/
├── SKILL.md                              1518 words
├── .gitignore
├── agents/openai.yaml                    4 lines
├── references/
│   ├── capability-audit.md                888 words
│   ├── flower-text-templates.md          2554 words
│   ├── flower-text-templates.json       12090 words / 231KB
│   ├── light-content-policy.md            123 words
│   ├── plan-schema.md                     859 words
│   ├── property-model.md                  626 words
│   ├── semantic-packaging.md              561 words
│   ├── sfx-palette.md                     184 words  ← 重复候选
│   └── staging-and-covered-subtitles.md   259 words
└── scripts/
    ├── validate_packaging_plan.py        966 lines / 13 tests pass
    └── test_validate_packaging_plan.py   293 lines
```
