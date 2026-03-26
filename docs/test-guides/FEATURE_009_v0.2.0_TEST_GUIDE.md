# Feature 009: 布局检测（PP-DocLayout-V3）- 人工测试指导

## 功能概述

**功能名称**: 布局检测（PP-DocLayout-V3）
**版本**: v0.2.0
**测试日期**: [待填写]
**测试人员**: [待填写]

**功能描述**:
集成 PP-DocLayout-V3 文档布局检测模型，对 PDF 每页进行语义区域检测，识别标题、正文、图片、表格、页眉、页脚等区域，输出边界框坐标和语义标签。此功能是 v0.2.0 可编辑 MVP 的基础——后续 OCR 文字提取和文本框放置依赖布局检测结果。

---

## 测试环境

### 前置条件
- Python 3.11+ 已安装
- 项目依赖已安装：`uv sync --all-extras`
- PP-DocLayout-V3 模型文件已下载（131MB）
  - 下载地址：https://huggingface.co/alex-dinh/PP-DocLayoutV3-ONNX/resolve/main/pp_doclayout_v3.onnx
  - 放置路径：`~/.noteeditor/models/pp_doclayout_v3.onnx`

### 测试文件
- 准备多种类型的 PDF 文件用于测试：
  - 简单文档（纯文本，少量标题）
  - 复杂文档（含图片、表格、公式）
  - 多页文档（10+ 页）
  - 扫描版 PDF（纯图片 PDF）

---

## 测试用例

### TC-001: 模型文件缺失 — 明确错误提示

**优先级**: 高
**类型**: 负向测试

**前置条件**:
- `~/.noteeditor/models/` 目录下不存在 `pp_doclayout_v3.onnx`

**测试步骤**:
1. 确保模型文件不在默认路径
2. 运行以下 Python 代码：
   ```python
   from pathlib import Path
   from noteeditor.infra.model_manager import ModelManager

   mgr = ModelManager(models_dir=Path.home() / ".noteeditor" / "models")
   mgr.get_layout_model()
   ```

**预期效果**:
- [ ] 抛出 `FileNotFoundError`
- [ ] 错误消息包含 "Layout model not found"
- [ ] 错误消息包含 HuggingFace 下载 URL（`huggingface`）
- [ ] 错误消息包含目标路径（`pp_doclayout_v3.onnx`）
- [ ] 用户能根据错误消息明确知道去哪里下载、放到哪里

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-002: 模型加载 — CPU 模式

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 模型文件 `pp_doclayout_v3.onnx` 已放置在 `~/.noteeditor/models/`

**测试步骤**:
1. 运行以下 Python 代码：
   ```python
   from pathlib import Path
   from noteeditor.infra.model_manager import ModelManager

   mgr = ModelManager(models_dir=Path.home() / ".noteeditor" / "models", device="cpu")
   session = mgr.get_layout_model()
   print(f"Session created: {session}")
   print(f"Providers: {session.get_providers()}")
   ```

**预期效果**:
- [ ] 不抛出异常
- [ ] 返回的 InferenceSession 对象有效
- [ ] `get_providers()` 包含 `CPUExecutionProvider`
- [ ] 加载时间在合理范围内（< 10 秒）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-003: 模型加载 — Auto 模式（无 GPU）

**优先级**: 中
**类型**: 正向测试

**前置条件**:
- 机器无 NVIDIA GPU 或未安装 CUDA
- 模型文件已就位

**测试步骤**:
1. 运行以下代码（不指定 device，使用默认 auto）：
   ```python
   from pathlib import Path
   from noteeditor.infra.model_manager import ModelManager

   mgr = ModelManager(models_dir=Path.home() / ".noteeditor" / "models")
   session = mgr.get_layout_model()
   print(f"Providers: {session.get_providers()}")
   ```

**预期效果**:
- [ ] 不抛出异常
- [ ] 自动回退到 CPU 模式
- [ ] `get_providers()` 包含 `CPUExecutionProvider`

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-004: 模型加载 — 损坏的模型文件

**优先级**: 中
**类型**: 负向测试

**前置条件**:
- `~/.noteeditor/models/pp_doclayout_v3.onnx` 存在但内容损坏（非有效 ONNX）

**测试步骤**:
1. 将一个非 ONNX 文件（如文本文件）保存为 `pp_doclayout_v3.onnx`
2. 运行以下代码：
   ```python
   from pathlib import Path
   from noteeditor.infra.model_manager import ModelManager

   mgr = ModelManager(models_dir=Path.home() / ".noteeditor" / "models", device="cpu")
   mgr.get_layout_model()
   ```

**预期效果**:
- [ ] 抛出 `RuntimeError`
- [ ] 错误消息包含 "Failed to load"
- [ ] 错误消息包含模型文件路径

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-005: 布局检测 — 纯文本文档

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 模型已加载（参考 TC-002）
- 准备一个纯文本文档的 PDF（含标题和正文段落）

**测试步骤**:
1. 使用 PyMuPDF 渲染 PDF 页面为 PageImage
2. 运行布局检测：
   ```python
   import fitz
   from pathlib import Path
   import numpy as np
   from noteeditor.infra.model_manager import ModelManager
   from noteeditor.stages.layout import detect_layout
   from noteeditor.models.page import PageImage

   # 加载模型
   mgr = ModelManager(models_dir=Path.home() / ".noteeditor" / "models", device="cpu")
   session = mgr.get_layout_model()

   # 渲染页面
   doc = fitz.open("test_document.pdf")
   page = doc[0]
   pix = page.get_pixmap(dpi=300)
   image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
   image = image[:, :, :3]  # 取 RGB

   page_image = PageImage(
       page_number=0,
       width_px=pix.w,
       height_px=pix.h,
       dpi=300,
       aspect_ratio=pix.w / pix.h,
       image=image,
   )

   # 运行检测
   result = detect_layout(page_image, session)
   print(f"Page {result.page_number}: {len(result.regions)} regions detected")
   for region in result.regions:
       print(f"  {region.region_id}: {region.label} (conf={region.confidence:.2f}) "
             f"bbox=({region.bbox.x:.0f},{region.bbox.y:.0f},"
             f"{region.bbox.width:.0f},{region.bbox.height:.0f})")
   ```

**预期效果**:
- [ ] 不抛出异常
- [ ] `result.page_number` 等于 0
- [ ] `result.regions` 不为空（至少检测到标题和正文）
- [ ] 每个区域包含正确的 `RegionLabel`（如 title, body_text）
- [ ] 每个区域的 `confidence` 在 0.0-1.0 之间
- [ ] `region_id` 格式为 `page0_region0`、`page0_region1` 等
- [ ] 区域按 confidence 降序排列
- [ ] `LayoutResult` 是不可变的（frozen dataclass）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-006: 布局检测 — 含图片和表格的文档

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 模型已加载
- 准备一个包含图片和表格的 PDF 文档

**测试步骤**:
1. 使用 TC-005 相同的方法渲染和检测
2. 特别关注检测到的区域标签

**预期效果**:
- [ ] 检测到 `image` 类型的区域（图片）
- [ ] 检测到 `table` 类型的区域（表格）
- [ ] 检测到 `title` 和 `body_text` 类型的区域
- [ ] 各区域的边界框坐标在合理范围内（不超过页面尺寸）
- [ ] 宽度和高度非负

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-007: 布局检测 — 多页文档

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 模型已加载
- 准备一个 10 页以上的 PDF 文档

**测试步骤**:
1. 逐页渲染并检测：
   ```python
   import fitz
   from pathlib import Path
   import numpy as np
   from noteeditor.infra.model_manager import ModelManager
   from noteeditor.stages.layout import detect_layout
   from noteeditor.models.page import PageImage

   mgr = ModelManager(models_dir=Path.home() / ".noteeditor" / "models", device="cpu")
   session = mgr.get_layout_model()
   doc = fitz.open("test_multipage.pdf")

   for page_num in range(len(doc)):
       page = doc[page_num]
       pix = page.get_pixmap(dpi=300)
       image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]

       page_image = PageImage(
           page_number=page_num,
           width_px=pix.w,
           height_px=pix.h,
           dpi=300,
           aspect_ratio=pix.w / pix.h,
           image=image,
       )

       result = detect_layout(page_image, session)
       print(f"Page {page_num}: {len(result.regions)} regions")
   ```

**预期效果**:
- [ ] 所有页面都成功完成检测，无异常
- [ ] 每页的 `page_number` 与实际页码一致
- [ ] 不同页面的 `region_id` 中的页码不同（如 `page0_region0` vs `page1_region0`）
- [ ] 推理时间在合理范围内（每页 < 5 秒 CPU 模式）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-008: 自定义置信度阈值

**优先级**: 中
**类型**: 正向测试

**前置条件**:
- 模型已加载
- 准备一个测试 PDF

**测试步骤**:
1. 使用默认阈值（0.5）运行检测
2. 使用更严格的阈值（0.8）运行检测：
   ```python
   result_default = detect_layout(page_image, session, confidence_threshold=0.5)
   result_strict = detect_layout(page_image, session, confidence_threshold=0.8)
   print(f"Default (0.5): {len(result_default.regions)} regions")
   print(f"Strict (0.8): {len(result_strict.regions)} regions")
   ```

**预期效果**:
- [ ] 严格阈值检测到的区域数 ≤ 默认阈值
- [ ] 严格阈值下所有区域的 confidence >= 0.8
- [ ] 默认阈值下所有区域的 confidence >= 0.5

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-009: 不同 DPI 设置

**优先级**: 中
**类型**: 兼容性测试

**前置条件**:
- 模型已加载
- 准备一个测试 PDF

**测试步骤**:
1. 分别以 72 DPI、150 DPI、300 DPI 渲染同一页面
2. 对每个分辨率运行布局检测
3. 比较检测到的区域数量和标签类型

```python
for dpi in [72, 150, 300]:
    pix = page.get_pixmap(dpi=dpi)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]

    page_image = PageImage(
        page_number=0, width_px=pix.w, height_pix=pix.h,
        dpi=dpi, aspect_ratio=pix.w / pix.h, image=image,
    )
    result = detect_layout(page_image, session)
    print(f"DPI {dpi}: {len(result.regions)} regions, image size {pix.w}x{pix.h}")
```

**预期效果**:
- [ ] 所有 DPI 下都能成功检测
- [ ] 不同 DPI 检测到的区域类型大致相同（标题、正文等）
- [ ] 边界框坐标根据 DPI 正确缩放（高 DPI 下坐标值更大）
- [ ] 区域的相对位置（在页面中的比例）一致

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-010: ModelManager 不可变性

**优先级**: 低
**类型**: 边界测试

**前置条件**:
- 无

**测试步骤**:
1. 运行以下代码：
   ```python
   from pathlib import Path
   from noteeditor.infra.model_manager import ModelManager

   mgr = ModelManager(models_dir=Path("/tmp/models"))
   try:
       mgr.device = "cpu"
       print("ERROR: Should have raised AttributeError")
   except AttributeError:
       print("OK: ModelManager is frozen")
   ```

**预期效果**:
- [ ] 抛出 `AttributeError`（frozen dataclass 不可变）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-011: 自动化测试通过

**优先级**: 高
**类型**: 回归测试

**前置条件**:
- 项目依赖已安装

**测试步骤**:
1. 运行 Feature 009 相关的自动化测试：
   ```bash
   uv run pytest tests/unit/test_model_manager.py tests/unit/test_layout.py -v
   ```
2. 运行全量测试：
   ```bash
   uv run pytest -v
   ```
3. 运行 lint 检查：
   ```bash
   uv run ruff check src/ tests/
   ```
4. 运行类型检查：
   ```bash
   uv run mypy src/noteeditor/infra/model_manager.py src/noteeditor/stages/layout.py
   ```

**预期效果**:
- [ ] Feature 009 测试全部通过（32 个测试）
- [ ] 全量测试通过（130 个测试）
- [ ] 无 lint 错误
- [ ] 新文件无类型错误
- [ ] 新文件覆盖率 100%

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

## 边界用例

### BC-001: 空白页面
- 渲染一个全白页面图像，运行布局检测
- 预期：返回空的 regions 列表（或极低置信度的区域被过滤掉）

### BC-002: 极小页面（72 DPI）
- 以最低 DPI 渲染页面
- 预期：模型仍能正常处理（resize 到 800x800）

### BC-003: 极大页面（600 DPI）
- 以高 DPI 渲染页面（可能产生 5000+ px 宽的图像）
- 预期：坐标正确缩放回大尺寸，无溢出错误

### BC-004: 模型目录不存在
- ModelManager 指向一个不存在的目录
- 预期：get_layout_model() 抛出 FileNotFoundError

---

## 检测标签验证

PP-DocLayout-V3 输出 26 种标签，映射到以下 11 种 RegionLabel：

| RegionLabel | 含义 | 对应原始标签 |
|-------------|------|-------------|
| title | 标题 | doc_title, paragraph_title |
| body_text | 正文 | text, content, aside_text, author |
| image | 图片 | image, chart, embedded_image, header_image, footer_image |
| table | 表格 | table |
| header | 页眉 | header |
| footer | 页脚 | footer |
| figure_caption | 图注 | figure_title |
| equation | 公式 | display_formula, inline_formula, formula_number |
| code_block | 代码块 | （v0.2.0 无对应原始标签） |
| reference | 参考文献 | reference, reference_content |
| unknown | 未知 | abstract, keywords, date, section |

**验证要点**:
- [ ] 文档标题被正确识别为 `title`
- [ ] 正文段落被识别为 `body_text`
- [ ] 图片/图表被识别为 `image`
- [ ] 表格被识别为 `table`
- [ ] 未映射的标签回退到 `unknown`

---

## 测试总结

| 用例数 | 通过 | 失败 | 阻塞 |
|--------|------|------|------|
| 11 + 4 边界 | - | - | - |

**测试结论**: [待填写]

**发现的问题**: [如有问题请在此记录]

---

*测试指导生成时间: 2026-03-26*
*Feature ID: 009*
*Design Doc: docs/features/v0.2.0.md#009*
