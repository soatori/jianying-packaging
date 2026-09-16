# 花字预设可复用模板目录

本目录记录从源草稿筛出的 14 个可复用花字预设：按语义和层数筛选，再检查样例长度、字号与相对位置。**层几何、相对位置和精确定位符只定义在同目录的 [flower-text-templates.json](flower-text-templates.json)；本文件不再复制 JSON 明细。**

## 使用原则

- 复制时以 JSON 中的 `template_source.segment_id` 为入口，克隆完整外层复合片段及其 `source_extra_material_refs` 闭包；不要只复制一个文本 material。
- 替换文本要同步 `content`、存在时的 `base_content`/`recognize_text`，并重算所有 style range。默认单行不超过 13 个汉字，英文和数字按实际宽度检查。
- 坐标是 1080×1920 项目中的存储归一化值。`x_px≈x_norm×1080`、`y_px≈y_norm×1920` 只用于估算，目标项目必须重新确认画布并做视觉复核。
- 先保持参考层和各层的 `dx_norm/dy_norm` 相对关系；文字变长时优先微调 `position_x`，仍可能溢出再微调该层缩放。保留原字体、颜色、阴影、描边、动画和层序。
- 普通花字的本地约定仍是点宋体、字号 10、阴影开启、UI Y=-850；具体模板有自己的已验证样式时，以模板样式为准。
- 复制前检查字体健康与同组回退；字体缺失或 fallback 不可确认时 fail closed。

## 已选模板速览

| ID | 适用内容 | 层数 | 样例形态 | 难度 |
|---|---|---:|---|---|
| `flower-two-layer-base-emphasis` | ordinary_explanation / conclusion | 2 | 解决这个问题 → 想办法为用户 | easy |
| `flower-two-layer-fade-emphasis` | ordinary_explanation / risk_warning / core_point | 2 | 使用刀具的成本 → 压力非常大 | easy |
| `flower-title-detail-offset` | technical_term / core_point / ordinary_explanation | 2 | 高速高精 → 大量使用直驱技术 | easy |
| `flower-three-layer-service` | ordinary_explanation / core_point / cta | 3 | 恒锋为客户提供 → 花键加工 → 全套解决方案 | easy |
| `flower-body-number-accent` | number_parameter / technical_term / core_point | 2 | 那现在为什么客户会 → 选择24寸 | easy |
| `flower-material-capacity-table` | number_parameter / technical_term / contrast_turn | 6 | 铝合金 / 钛合金 / 不锈钢 材料孔数对照 | moderate |
| `flower-three-benefits-fade` | core_point / conclusion / ordinary_explanation | 3 | 切削阻力小 → 稳定性高 → 使用寿命长 | easy |
| `flower-single-number-title` | number_parameter / product_brand / core_point | 1 | 2026 CCMT | easy |
| `flower-technical-callout` | technical_term / number_parameter | 2 | 液压双向主轴夹座 → 通孔300 | easy |
| `flower-typing-body-accent` | ordinary_explanation / core_point / conclusion | 2 | 可以夹持零件中段 → 双端同时加工 | easy |
| `flower-single-brand-typing` | product_brand / technical_term | 1 | 庄田铁工株式会社 | easy |
| `flower-body-brand-staggered` | product_brand / ordinary_explanation | 2 | 后来又到 → 日本丸仲机械 | easy |
| `flower-memory-two-layer-typing` | ordinary_explanation / emotion / conclusion | 2 | 我有一个记忆 → 还是比较深刻的 | easy |
| `flower-question-mark-lower` | question | 3 | 是不是对日本 → ？ → 有什么看法 | moderate |

## 特殊规则（不在 JSON 中）

### 问号层序

对于已确立的问句模板（`flower-question-mark-lower`），问号必须保持独立层，不要并入正文；问号轨道放在该组文字轨道之下，并从第二短语开始。单短语问句则从该短语同起。

### 字体健康与同组回退

复制前确认各层字体存在且可加载；若字体缺失、或 fallback 与原样式不可比，不得静默替换样式，应 fail closed 并请求用户确认。

### 文本适配与行规则

- 默认单行不超过 13 个汉字；英文和数字按实际宽度检查，不等同于汉字字数。
- 样例最大行长见 JSON 中对应模板的 `max_sample_line_length`；替换为更长文本时必须拆行、缩小或重新定位。
- `flower-material-capacity-table` 等长数字对照模板，超长数字行须先做宽度检查。
- 保持 `content` 与存在时的 `base_content`/`recognize_text` 同步；style range 必须覆盖完整替换文本。

## 权威几何来源

**层几何、相对位置（`dx_norm`/`dy_norm`）、精确 segment/material/draft 定位符、参考层、缩放与可覆盖字段，只在 [flower-text-templates.json](flower-text-templates.json) 中定义。** 本文件仅作选型说明与非几何特殊规则入口。

源时间线与校验：主时间线 `07E95BA2-D2CB-4fc3-9B07-5A50D787A533` / `时间线01`；布局 `hybrid`。所有模板在 Jianying 重新打开后仍须做文字宽度、相对位置、层序和动画的视觉检查。
