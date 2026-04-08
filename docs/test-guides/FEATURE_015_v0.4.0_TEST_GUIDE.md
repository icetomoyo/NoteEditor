# Feature 015: 字体映射表 - 人工测试指导

> 版本: v0.4.0 | Feature ID: 015 | 状态: Ready for Testing

## 测试目标

验证 Font Matcher 阶段正确匹配字体映射表，为文本区域分配正确字体。

## 前置条件

- 已安装依赖: `uv sync --all-extras`
- 准备一份 NotebookLM PDF 文件
- 确认 `fonts/font_map.yaml` 存在且包含 title/body_text/code_block 映射

## 测试用例

### TC-015-01: 字体映射表加载

**步骤:**
1. 检查 `fonts/font_map.yaml` 内容
2. 确认包含 3 个映射: title, body_text, code_block

**预期结果:**
- title → Google Sans Bold
- body_text → Google Sans Regular
- code_block → Google Sans Mono

### TC-015-02: 可编辑模式 PPTX 字体应用

**步骤:**
1. 运行: `uv run noteeditor input.pdf output.pptx --mode editable`
2. 打开生成的 PPTX 文件
3. 检查文本框字体

**预期结果:**
- TITLE 区域使用 Google Sans Bold（如有字体文件）或 Arial fallback
- BODY_TEXT 区域使用 Google Sans Regular（如有字体文件）或 Arial fallback
- CODE_BLOCK 区域使用 Google Sans Mono（如有字体文件）或 Consolas fallback
- EQUATION 区域使用 Arial fallback（无映射）

### TC-015-03: 字体文件缺失降级

**步骤:**
1. 暂时移除 `fonts/` 中的 .ttf 文件
2. 运行转换
3. 检查 PPTX 文本框字体

**预期结果:**
- 所有文本使用 system_fallback 字体（Arial/Consolas）
- is_fallback=True
- 不崩溃

### TC-015-04: 无字体映射表

**步骤:**
1. 暂时移除 `fonts/font_map.yaml`
2. 运行转换

**预期结果:**
- 所有文本使用 Arial 默认字体
- 不崩溃

### TC-015-05: Pipeline 集成

**步骤:**
1. 运行: `uv run noteeditor input.pdf output.pptx --mode editable`
2. 确认输出无错误

**预期结果:**
- 8 阶段 pipeline 正确执行
- 输出 PPTX 包含正确文本和图片

## 自动化测试覆盖

- 15 个 font stage 单元测试
- 2 个 pipeline 集成测试 (match_fonts 调用 + 传递)
- 2 个 builder 集成测试 (font_matches 使用 + fallback)
- 1 个 visual 模式测试 (不调用 match_fonts)

**总计: 338 个自动化测试全部通过**

## 回归检查

- [ ] Visual 模式仍正常工作
- [ ] 可编辑模式背景正确
- [ ] 图片提取正常
- [ ] OCR 文本正确
