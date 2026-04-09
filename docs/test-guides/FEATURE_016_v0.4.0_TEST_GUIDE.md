# Feature 016: 字号颜色估计 - 人工测试指导

> 版本: v0.4.0 | Feature ID: 016 | 状态: Ready for Testing

## 测试目标

验证 Text Style Estimator 阶段正确估算文本区域的字号和颜色，并在可编辑 PPTX 中正确应用。

## 前置条件

- 已安装依赖: `uv sync --all-extras`
- 准备一份 NotebookLM PDF 文件（含标题、正文、公式等区域）
- 确认 `fonts/font_map.yaml` 存在（Feature 015 已完成）

## 测试用例

### TC-016-01: 字号估计准确性

**步骤:**
1. 运行: `uv run noteeditor input.pdf output.pptx --mode editable`
2. 打开生成的 PPTX 文件
3. 选择标题文本框，查看字号
4. 选择正文文本框，查看字号

**预期结果:**
- 标题文本字号明显大于正文（通常 18-24pt vs 10-12pt）
- 字号视觉上与原始 PDF 匹配
- 所有文本可读，不过大或过小

### TC-016-02: 字体颜色准确性

**步骤:**
1. 打开生成的 PPTX 文件
2. 选择文本框
3. 查看字体颜色

**预期结果:**
- 深色文本（黑色/深灰）正确应用
- 如果原始 PDF 有彩色标题（如蓝色），PPTX 中应保持
- 白色背景区域不会误采样为文字颜色

### TC-016-03: 字体名称应用

**步骤:**
1. 打开 PPTX 文件
2. 检查各文本框字体名称

**预期结果:**
- 不再全部显示 "Arial"
- 使用 font_map.yaml 中匹配的字体名称
- 缺少字体文件时降级到 system_fallback

### TC-016-04: Pipeline 9 阶段调度

**步骤:**
1. 运行: `uv run noteeditor input.pdf output.pptx --mode editable`
2. 确认输出无错误

**预期结果:**
- 9 阶段 pipeline 正确执行
- 输出 PPTX 包含正确文本、图片、背景
- 无阶段执行错误

### TC-016-05: Visual 模式不受影响

**步骤:**
1. 运行: `uv run noteeditor input.pdf output_visual.pptx --mode visual`
2. 打开 PPTX 文件

**预期结果:**
- 纯截图模式正常工作
- 不调用 estimate_styles 阶段
- 输出与之前版本一致

## 自动化测试覆盖

- 18 个 style stage 单元测试（字号估计 6 + 颜色采样 5 + 集成 7）
- 2 个 pipeline 集成测试（calls estimate_styles + passes to assemble）
- 1 个 visual 模式测试（不调用 estimate_styles）
- 3 个 builder 集成测试（style_attached + style_none + font_color_applied + font_size_override）

**总计: 363 个自动化测试全部通过**

## 回归检查

- [ ] Visual 模式仍正常工作
- [ ] 可编辑模式背景正确
- [ ] 图片提取正常
- [ ] OCR 文本正确
- [ ] 字体映射正常
