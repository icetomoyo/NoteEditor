# Feature 012 - Pipeline 多阶段扩展 人工测试指南

**版本**: v0.2.0
**日期**: 2026-04-08
**前置条件**: Features 009-011 已完成

---

## 前置条件

1. 准备一个 NotebookLM 导出的 PDF 文件（含文字和图片区域）
2. 确保 PP-DocLayout-V3 模型已下载到 `~/.noteeditor/models/`
3. 确保 GLM-OCR 模型已下载或 ZhipuAI API Key 已配置

## 测试用例

### TC-001: 可编辑模式（默认）

**步骤**:
1. 运行 `noteeditor input.pdf`
2. 用 PowerPoint/WPS 打开输出的 PPTX 文件
3. 点击文字区域

**预期结果**:
- 默认使用 editable 模式
- 文字区域可直接选中、编辑
- 非文字区域保留在背景中

### TC-002: 视觉模式（--mode visual）

**步骤**:
1. 运行 `noteeditor input.pdf --mode visual`
2. 打开输出的 PPTX 文件

**预期结果**:
- 输出纯截图 PPTX（与 v0.1.0 行为一致）
- 没有文本框覆盖
- 幻灯片只有全页截图

### TC-003: 指定 DPI

**步骤**:
1. 运行 `noteeditor input.pdf --dpi 150`

**预期结果**:
- DPI 设置生效
- 输出 PPTX 正常生成

### TC-004: 混合页面成功与失败

**步骤**:
1. 使用包含多页的 PDF 输入
2. 运行 pipeline
3. 检查输出日志

**预期结果**:
- 成功页面有可编辑文本框
- 失败页面回退到截图模式
- 不阻塞其他页面的处理

### TC-005: 全部页面失败

**步骤**:
1. 在没有模型文件的情况下运行可编辑模式
2. 检查输出

**预期结果**:
- 所有页面回退到截图模式
- 仍然生成有效的 PPTX 文件
- 日志记录失败原因

### TC-006: 空 PDF

**步骤**:
1. 使用空 PDF（0 页）作为输入
2. 检查输出

**预期结果**:
- 输出有效的 PPTX 文件
- 0 张幻灯片
- 不崩溃

### TC-007: CLI --mode 选项验证

**步骤**:
1. 运行 `noteeditor --help`
2. 检查 --mode 选项描述
3. 尝试无效模式值

**预期结果**:
- 帮助文本显示 --mode visual|editable
- 无效值被拒绝并提示

---

## 边界测试

### BT-001: 自定义 models_dir
- 使用不同模型目录路径
- 预期：正确加载或明确报错

### BT-002: 非常大的 PDF
- 输入 50+ 页的 PDF
- 预期：逐页处理，单页失败不影响其他页

### BT-003: ModelManager 无模型
- models_dir 为空目录
- 预期：FileNotFoundError 含下载指引

---

## 自动化测试覆盖

### PipelineConfig v2 (5 tests)
- 默认 mode 为 editable
- mode 可设为 visual
- 默认 models_dir
- 自定义 models_dir
- frozen 不可变

### build_config v2 (3 tests)
- 传递 mode 参数
- 默认 mode
- 自定义 models_dir

### Editable Pipeline (6 tests)
- 单页成功
- 调用 detect_layout
- 调用 extract_text
- layout 失败回退
- OCR 失败回退
- 混合成功/失败

### Visual Pipeline (4 tests)
- 单页成功
- 不调用 layout
- 不调用 OCR
- 不创建 ModelManager

### ModelManager 集成 (1 test)
- 使用 config.models_dir

### 全部失败场景 (2 tests)
- 所有页面回退
- 空 PDF 可编辑模式

**总计**: 21 个新自动化测试（加上原有测试共 246 个）
