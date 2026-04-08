# Feature 013: 程序化背景重建 — Human Test Guide

> Version: v0.3.0 | Feature ID: 013 | Date: 2026-04-08

## Overview

Feature 013 添加了 Background Extractor 阶段，在可编辑模式下从页面渲染图中移除文字区域，生成干净背景图像。这使得可编辑 PPTX 的背景更自然，而不是之前的白色填充策略。

### 核心变更

- **新模块**: `stages/background.py` — 背景提取逻辑（5个私有函数 + 1个公共函数）
- **Pipeline 升级**: 5阶段 → 6阶段（Parser → Layout → OCR → **Background** → Assemble → Builder）
- **Builder 更新**: `assemble_slide()` 接受 `background_image` 参数；`build_editable_pptx()` 优先使用 `background_image` 作为幻灯片背景

### 背景分类策略

| 类型 | 条件 | 填充策略 |
|------|------|----------|
| Simple | std < 15 | 中值颜色填充 |
| Gradient | 15 ≤ std < 50 | 按行线性插值 |
| Complex | std ≥ 50 | 白色填充（回退） |

---

## Automated Test Results

```
tests/unit/test_background.py     27 passed
tests/unit/test_pipeline_v2.py    25 passed (6 new for background stage)
tests/unit/test_builder_editable.py 41 passed (2 new for background_image)
──────────────────────────────────────────────────
Total: 280 passed | Coverage: 96% | Lint: Clean
```

---

## Manual Test Plan

### Prerequisites

- 安装依赖: `uv sync --all-extras`
- 准备测试 PDF 文件（包含文字的演示文稿 PDF）
- 确保模型文件已下载到 `~/.noteeditor/models/`

### Test 1: 可编辑模式输出使用背景图像

**目的**: 验证可编辑 PPTX 使用背景重建图像而非原始截图

**步骤**:
1. 运行: `uv run noteeditor input.pdf output.pptx --mode editable`
2. 打开 `output.pptx`
3. 检查幻灯片背景

**预期结果**:
- 幻灯片背景中文字区域被背景颜色填充（非白色）
- 简单背景页面：文字区域用背景中值颜色填充
- 渐变背景页面：文字区域用渐变色自然过渡填充
- 复杂背景页面：文字区域用白色填充（回退策略）

### Test 2: 视觉模式不受影响

**目的**: 验证 `--mode visual` 不调用背景提取

**步骤**:
1. 运行: `uv run noteeditor input.pdf output_visual.pptx --mode visual`
2. 打开 `output_visual.pptx`

**预期结果**:
- 行为与 v0.1.0 一致
- 幻灯片直接使用原始页面截图作为背景
- 不进行背景重建

### Test 3: Pipeline 6阶段调度

**目的**: 验证 Pipeline 正确按顺序执行 6 个阶段

**步骤**:
1. 运行: `uv run noteeditor input.pdf output.pptx --mode editable --verbose`
2. 观察日志输出

**预期结果**:
- 日志中可以看到 Background 阶段的执行（背景分类日志）
- 页面处理顺序: Parse → Layout → OCR → Background → Assemble → Build

### Test 4: 单页失败回退

**目的**: 验证背景提取失败时，该页回退到截图模式

**步骤**:
1. 使用包含多页的 PDF 运行转换
2. 检查所有页面是否都正常输出

**预期结果**:
- 即使某页背景提取失败，其他页正常处理
- 失败页使用原始截图作为背景
- PPTX 中所有页面都有内容

### Test 5: 无文字区域的页面

**目的**: 验证纯图片页面不被修改

**步骤**:
1. 使用包含纯图片页面的 PDF 运行转换
2. 检查纯图片页面的背景

**预期结果**:
- 纯图片页面背景不被修改
- 返回原始页面图像

---

## Risk Areas

1. **内存使用**: 背景重建需要复制整个页面图像，高分辨率 DPI 可能增加内存占用
2. **复杂背景**: 复杂纹理背景回退到白色填充，可能与原始背景不匹配
3. **边界 bbox**: 超出图像范围的 bbox 已有 clamp 处理，但极端情况仍需关注

## Rollback

如果出现问题，可以恢复到 v0.2.0 行为：
- Pipeline 中 `extract_background` 调用可以被跳过（设置 `background_image=None`）
- Builder 已有回退逻辑：`background_image is None` 时使用 `full_page_image`
