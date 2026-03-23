# PDF 页面渲染（PyMuPDF 集成）- 人工测试指导

## 功能概述

**功能名称**: PDF 页面渲染（PyMuPDF 集成）
**版本**: v0.1.0
**Feature ID**: 003
**测试日期**: [待填写]
**测试人员**: [待填写]

**功能描述**:
集成 PyMuPDF，将 PDF 每页渲染为高 DPI 图像，并构造 PageImage 数据对象。支持 RGB、RGBA、灰度图像格式转换，单页渲染失败时自动跳过并记录警告。

---

## 测试环境

### 前置条件
- Python 3.11+ 已安装
- 项目依赖已安装: `uv sync --all-extras`
- 准备测试 PDF 文件（见下方测试数据）

### 测试数据
- **标准 PDF**: 3-5 页的 NotebookLM 导出 PDF（16:9 宽高比）
- **单页 PDF**: 仅包含 1 页的 PDF
- **空 PDF**: 有效 PDF 格式但 0 页
- **损坏 PDF**: 非 PDF 格式文件（如 .txt 改名为 .pdf）

---

## 测试用例

### TC-001: 标准 PDF 渲染

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 准备一个 3 页以上的 NotebookLM PDF

**测试步骤**:
1. 打开 Python REPL: `uv run python`
2. 执行以下代码:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf

pages = parse_pdf(Path("path/to/your/notebooklm.pdf"), 300)
print(f"Total pages: {len(pages)}")
for p in pages:
    print(f"  Page {p.page_number}: {p.width_px}x{p.height_px}, dpi={p.dpi}, ratio={p.aspect_ratio:.4f}")
    print(f"    Image shape: {p.image.shape}, dtype: {p.image.dtype}")
```

**预期效果**:
- [ ] 返回的 PageImage 数量与 PDF 页数一致
- [ ] 每个 PageImage.page_number 从 0 开始递增
- [ ] width_px / height_px 与 300 DPI 下的 PDF 页面尺寸一致
- [ ] image.shape 格式为 (H, W, 3)
- [ ] image.dtype 为 uint8
- [ ] aspect_ratio 约等于 16/9 (1.778) 对于 NotebookLM PDF
- [ ] embedded_images 为空 tuple（v0.1.0 不提取嵌入资源）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-002: DPI 缩放验证

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 准备一个标准 PDF

**测试步骤**:
1. 分别以 150 DPI 和 300 DPI 渲染同一 PDF:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf

pdf = Path("path/to/test.pdf")

pages_150 = parse_pdf(pdf, 150)
pages_300 = parse_pdf(pdf, 300)

for p150, p300 in zip(pages_150, pages_300):
    print(f"Page {p150.page_number}:")
    print(f"  150 DPI: {p150.width_px}x{p150.height_px}")
    print(f"  300 DPI: {p300.width_px}x{p300.height_px}")
    print(f"  Ratio: {p300.width_px / p150.width_px:.1f}x")
```

**预期效果**:
- [ ] 300 DPI 的像素尺寸约为 150 DPI 的 2 倍
- [ ] PageImage.dpi 字段与传入的 DPI 参数一致
- [ ] 宽高比在两种 DPI 下保持一致

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-003: 渲染图像可视验证

**优先级**: 高
**类型**: 正向测试

**前置条件**:
- 准备一个包含文字和图片的 PDF

**测试步骤**:
1. 渲染 PDF 并保存第一页为图片:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf
from PIL import Image

pages = parse_pdf(Path("path/to/test.pdf"), 300)
img = Image.fromarray(pages[0].image)
img.save("page_0_rendered.png")
print("Saved to page_0_rendered.png")
```

**预期效果**:
- [ ] 保存的 PNG 文件可用图片查看器正常打开
- [ ] 图像内容与 PDF 原始内容一致（文字清晰、图片完整）
- [ ] 无色彩失真或黑屏
- [ ] 图像方向正确（无旋转或镜像）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-004: 非 PDF 文件处理

**优先级**: 高
**类型**: 负向测试

**前置条件**:
- 准备一个非 PDF 文件（如 test.txt）

**测试步骤**:
1. 用非 PDF 文件调用 parse_pdf:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf
from noteeditor.errors import InputError

try:
    parse_pdf(Path("test.txt"), 300)
except InputError as e:
    print(f"Caught InputError: {e}")
```

**预期效果**:
- [ ] 抛出 InputError 异常
- [ ] 错误消息包含 "Failed to open PDF"

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-005: 无效 DPI 值处理

**优先级**: 高
**类型**: 负向测试

**测试步骤**:
1. 分别测试 DPI=0 和 DPI=-1:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf
from noteeditor.errors import InputError

for dpi in [0, -1]:
    try:
        parse_pdf(Path("dummy.pdf"), dpi)
    except InputError as e:
        print(f"DPI={dpi}: {e}")
```

**预期效果**:
- [ ] DPI=0 抛出 InputError，消息包含 "DPI must be a positive integer"
- [ ] DPI=-1 抛出 InputError，消息包含 "DPI must be a positive integer"

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-006: 单页 PDF

**优先级**: 中
**类型**: 正向测试

**前置条件**:
- 准备一个仅包含 1 页的 PDF

**测试步骤**:
1. 渲染单页 PDF:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf

pages = parse_pdf(Path("single_page.pdf"), 300)
print(f"Pages: {len(pages)}")
print(f"Page number: {pages[0].page_number}")
```

**预期效果**:
- [ ] 返回 1 个 PageImage
- [ ] page_number == 0

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

### TC-007: RGBA 页面渲染

**优先级**: 中
**类型**: 兼容性测试

**前置条件**:
- 准备一个包含透明图层（RGBA）的 PDF

**测试步骤**:
1. 渲染包含透明图层的 PDF:

```python
from pathlib import Path
from noteeditor.stages.parser import parse_pdf

pages = parse_pdf(Path("rgba_page.pdf"), 300)
print(f"Image shape: {pages[0].image.shape}")
```

**预期效果**:
- [ ] 正常渲染，无报错
- [ ] image.shape 为 (H, W, 3)（alpha 通道被正确移除）

**实际结果**: [待填写]
**是否通过**: [ ] Pass / [ ] Fail

---

## 边界用例

### BC-001: 极高 DPI
- 使用 DPI=1200 渲染，确认不抛出异常但注意内存使用

### BC-002: 极低 DPI
- 使用 DPI=1 渲染，确认生成极小的图像但不报错

### BC-003: 大页数 PDF
- 使用 50+ 页的 PDF，确认全部页面正确渲染，page_number 连续

---

## 测试总结

| 用例数 | 通过 | 失败 | 阻塞 |
|--------|------|------|------|
| 7      | -    | -    | -    |

**测试结论**: [待填写]

**发现的问题**: [如有问题请在此记录]

---

*测试指导生成时间: 2026-03-23*
*Feature ID: 003*
*自动化测试覆盖: 15 个单元测试，parser.py 100% 行覆盖率*
