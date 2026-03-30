# FEATURE_010 OCR 文字提取（GLM-OCR）- 人工测试指导

## 功能概述

**功能名称**: OCR 文字提取（GLM-OCR）
**版本**: v0.2.0
**测试日期**: [待填写]
**测试人员**: [待填写]

**功能描述**:
集成 GLM-OCR 文字识别模型，对布局检测到的文字区域进行 OCR 识别，提取文本内容。支持中英文混合和公式识别。提供 ONNX 本地推理和 Zhipu 云端 API 两种模式。

---

## 测试环境

### 前置条件
- Python 3.11+ 已安装
- 项目依赖已安装：`uv sync --all-extras`
- 已完成 FEATURE_009（布局检测）的测试
- 至少准备一个包含文字的 PDF 测试文件

### 模型文件（ONNX 模式）
- 下载 GLM-OCR ONNX 模型并放置到 `~/.noteeditor/models/glm_ocr.onnx`
- 下载地址：`https://huggingface.co/THUDM/glm-ocr/`

### API 密钥（API 模式）
- 从 [智谱开放平台](https://open.bigmodel.cn/) 获取 API Key
- 设置环境变量：`export ZHIPU_API_KEY=your_api_key`

### 测试文件
- `test_notebook.pdf` — 包含中文标题、正文、公式的 NotebookLM 导出 PDF
- `test_multilingual.pdf` — 包含中英文混合内容的 PDF
- `test_equations.pdf` — 包含数学公式的 PDF

---

## 测试用例

### TC-001: ONNX 模式 - 基础文字提取

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- GLM-OCR ONNX 模型已下载到 `~/.noteeditor/models/glm_ocr.onnx`
- 布局检测功能正常（FEATURE_009）

**测试步骤**:
1. 准备一个包含纯文本的 PDF（如 NotebookLM 导出的演示文稿）
2. 使用 Python 脚本调用 OCR 阶段：
   ```python
   from noteeditor.infra.model_manager import ModelManager
   from noteeditor.stages.ocr import extract_text

   mgr = ModelManager(models_dir=Path("~/.noteeditor/models").expanduser())
   ocr_session = mgr.get_ocr_model()

   # 假设已有 page_image 和 layout_result
   results = extract_text(page_image, layout_result, ocr_session)
   for r in results:
       print(f"{r.region_id}: {r.text} (conf={r.confidence:.2f})")
   ```
3. 检查输出的 OCRResult 列表

**预期效果**:
- [ ] 所有文字类型区域（TITLE, BODY_TEXT, EQUATION, CODE_BLOCK）均被识别
- [ ] 每个结果包含正确的 `region_id`（格式 `page{N}_region{M}`）
- [ ] 识别出的文本内容与 PDF 中的原文基本一致
- [ ] confidence 值在 0.0-1.0 范围内
- [ ] 返回值为不可变 tuple

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-002: API 模式 - 基础文字提取

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 已设置 `ZHIPU_API_KEY` 环境变量
- 网络可访问 `https://open.bigmodel.cn`

**测试步骤**:
1. 设置环境变量：`export ZHIPU_API_KEY=your_key`
2. 使用 Python 脚本调用 API 模式：
   ```python
   import os
   from noteeditor.stages.ocr import extract_text_api

   api_key = os.environ["ZHIPU_API_KEY"]
   results = extract_text_api(page_image, layout_result, api_key)
   for r in results:
       print(f"{r.region_id}: {r.text} (conf={r.confidence:.2f})")
   ```
3. 检查返回结果

**预期效果**:
- [ ] API 调用成功，返回 OCRResult 列表
- [ ] 识别文本准确
- [ ] 每个区域的 region_id 正确

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-003: 文字区域过滤

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 布局检测产生的 LayoutResult 包含多种类型的区域

**测试步骤**:
1. 使用包含文字、图片、表格、页眉页脚的 PDF
2. 运行 OCR 提取
3. 检查哪些区域被处理，哪些被跳过

**预期效果**:
- [ ] TITLE 区域被处理
- [ ] BODY_TEXT 区域被处理
- [ ] EQUATION 区域被处理
- [ ] CODE_BLOCK 区域被处理
- [ ] IMAGE 区域被跳过（不出现在 OCR 结果中）
- [ ] TABLE 区域被跳过
- [ ] HEADER / FOOTER 区域被跳过
- [ ] FIGURE_CAPTION 区域被跳过
- [ ] REFERENCE 区域被跳过
- [ ] UNKNOWN 区域被跳过

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-004: 区域裁切（Padding 和边界 Clamp）

**优先级**: 中
**类型**: 正向测试

**前置条件**:
- 同 TC-001

**测试步骤**:
1. 准备一个文字靠近页面边缘的 PDF
2. 在 debug 模式下保存裁切出的区域图像
3. 检查裁切图像的边界是否正确

**预期效果**:
- [ ] 正常区域裁切后有 10px padding
- [ ] 靠近页面左/上边缘的区域，padding 被正确 clamp（不会超出图像边界）
- [ ] 靠近页面右/下边缘的区域，padding 被正确 clamp
- [ ] 裁切出的图像不包含黑色填充区域

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-005: 公式识别

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 包含数学公式的 PDF

**测试步骤**:
1. 使用包含数学公式的 PDF（如 E=mc², a²+b²=c²）
2. 运行 OCR 提取
3. 检查公式区域的 OCRResult

**预期效果**:
- [ ] 公式区域被正确识别
- [ ] `is_formula` 字段为 `True`
- [ ] `formula_latex` 字段包含 LaTeX 源码（如 `a^2+b^2=c^2`）
- [ ] LaTeX 格式合理，可被后续渲染工具解析

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-006: 中英文混合识别

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 包含中英文混合内容的 PDF

**测试步骤**:
1. 使用中英文混合的 PDF
2. 运行 OCR 提取
3. 检查识别结果

**预期效果**:
- [ ] 中文文字被正确识别（无乱码）
- [ ] 英文文字被正确识别
- [ ] 中英文混合段落中两种文字均被正确识别
- [ ] 标点符号正确

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-007: 缺失模型文件错误处理

**优先级**: 中
**类型**: 负向测试

**前置条件**:
- 模型文件未下载（删除或重命名 `~/.noteeditor/models/glm_ocr.onnx`）

**测试步骤**:
1. 确保模型文件不存在
2. 调用 `ModelManager.get_ocr_model()`
3. 检查异常信息

**预期效果**:
- [ ] 抛出 `FileNotFoundError`
- [ ] 错误信息包含模型文件路径
- [ ] 错误信息包含下载 URL
- [ ] 错误信息清晰易懂，指导用户如何获取模型

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-008: API 错误处理 - 无效 API Key

**优先级**: 中
**类型**: 负向测试

**前置条件**:
- 无效的 API Key

**测试步骤**:
1. 使用无效 API Key 调用 `extract_text_api()`
2. 检查错误响应

**预期效果**:
- [ ] 抛出 `RuntimeError`
- [ ] 错误信息包含 HTTP 状态码
- [ ] 错误信息包含 region_id 上下文
- [ ] 不会导致程序崩溃

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-009: API 错误处理 - 网络异常

**优先级**: 中
**类型**: 负向测试

**前置条件**:
- 断开网络或使用不可达的 URL

**测试步骤**:
1. 断开网络连接
2. 调用 `extract_text_api()` 并指定一个不可达的 URL
3. 检查错误响应

**预期效果**:
- [ ] 抛出 `RuntimeError`
- [ ] 错误信息包含原始异常类型（如 `ConnectionError`）
- [ ] 错误信息包含 region_id 上下文

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-010: 空文字区域

**优先级**: 中
**类型**: 边界测试

**前置条件**:
- LayoutResult 中没有任何文字类型区域

**测试步骤**:
1. 构造只包含 IMAGE 和 TABLE 区域的 LayoutResult
2. 调用 `extract_text()` 或 `extract_text_api()`

**预期效果**:
- [ ] 返回空 tuple `()`
- [ ] 不抛出异常
- [ ] 不发起任何 ONNX 推理或 API 调用

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-011: ONNX 推理失败错误处理

**优先级**: 中
**类型**: 负向测试

**前置条件**:
- 使用损坏的模型文件

**测试步骤**:
1. 在模型目录放一个损坏的文件（如一个文本文件重命名为 `glm_ocr.onnx`）
2. 调用 `ModelManager.get_ocr_model()` 或在推理时观察错误

**预期效果**:
- [ ] `ModelManager.get_ocr_model()` 抛出 `RuntimeError`
- [ ] 错误信息包含模型文件路径
- [ ] 推理阶段失败时抛出 `RuntimeError`，包含页码和 region_id

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-012: GPU 自动检测

**优先级**: 低
**类型**: 正向测试

**前置条件**:
- 系统有 NVIDIA GPU（可选）

**测试步骤**:
1. 使用 `device="auto"` 创建 ModelManager
2. 加载 OCR 模型
3. 检查使用的 ExecutionProvider

**预期效果**:
- [ ] 有 GPU 时自动使用 `CUDAExecutionProvider`
- [ ] 无 GPU 时回退到 `CPUExecutionProvider`
- [ ] 模型正常加载和推理

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

## 边界用例

### BC-001: 页面边缘文字裁切
- 文字区域 bbox 紧贴页面左/上/右/下边缘时，padding 正确 clamp
- 不产生越界索引

### BC-002: 极大页面
- 高分辨率 PDF（如 A0 海报，600 DPI）下裁切和推理正常
- 不出现内存溢出

### BC-003: 极小区域
- bbox width 或 height 接近 0 的区域
- 10px padding 后仍可能为空或极小的区域

### BC-004: 无文字的纯图片页
- 整页只有图片，无任何文字区域
- 返回空 tuple，不报错

### BC-005: API 返回非 JSON 内容
- API 返回纯文本（非 JSON 格式）
- 代码回退到将整个内容作为 text 处理，confidence=0.5

---

## 性能验证

| 场景 | 页数 | 模式 | 预期耗时 | 实际耗时 |
|------|------|------|----------|----------|
| 单页纯文本 | 1 | ONNX CPU | < 5s | [待填写] |
| 单页纯文本 | 1 | API | < 10s | [待填写] |
| 10 页混合 | 10 | ONNX CPU | < 60s | [待填写] |
| 10 页混合 | 10 | API | < 120s | [待填写] |

---

## 测试总结

| 用例数 | 通过 | 失败 | 阻塞 |
|--------|------|------|------|
| 12 + 5 边界 | - | - | - |

**测试结论**: [待填写]

**发现的问题**: [如有问题请在此记录]

---

*测试指导生成时间: 2026-03-26*
*Feature ID: FEATURE_010*
