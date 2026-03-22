# NoteEditor HLD

> High-Level Design | 版本: 0.1-draft | 日期: 2026-03-22

## 1. 系统架构概览

NoteEditor 是一个 6 阶段流水线 CLI 工具，每阶段封装为独立模块，由 Pipeline Orchestrator 协调调度。

```
┌─────────────────────────────────────────────────────────┐
│                      CLI (cli.py)                        │
│                  参数解析 / 模式选择 / 入口                │
└──────────────────────┬──────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│              Pipeline Orchestrator (pipeline.py)          │
│           阶段调度 / 进度追踪 / 断点续传 / 错误隔离         │
└──┬────┬────┬────┬────┬────┬─────────────────────────────┘
   ↓    ↓    ↓    ↓    ↓    ↓
 ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐
 │ P  ││ L  ││ E  ││ B  ││ Bu ││ O  │   ← stages/
 │ a  ││ a  ││ x  ││ a  ││ i  ││ u  │
 │ r  ││ y  ││ t  ││ c  ││ l  ││ t  │
 │ s  ││ o  ││ r  ││ k  ││ d  ││ pu │
 │ e  ││ u  ││ a  ││ g  ││ e  ││ t  │
 │ r  ││ t  ││ c  ││ r  ││ r  ││    │
 └────┘└────┘└────┘└────┘└────┘└────┘
 Parser  Layout Extract Back Builder  Output
               ┌───┤
               │   │
              OCR  Img
              Font
               ↓
┌─────────────────────────────────────────────────────────┐
│                    Infrastructure                        │
│   model_manager │ config │ progress │ checkpoint         │
└─────────────────────────────────────────────────────────┘
```

### 1.1 各模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| CLI | `cli.py` | 命令行参数解析、输入校验、输出模式选择 |
| Pipeline Orchestrator | `pipeline.py` | 阶段调度、并行协调、断点续传、单页隔离 |
| Parser | `stages/parser.py` | PDF 解析、页面渲染、资源提取 |
| Layout | `stages/layout.py` | PP-DocLayout-V3 布局检测 |
| OCR | `stages/ocr.py` | GLM-OCR 文字识别 |
| Image Extractor | `stages/image.py` | 图片区域裁切、原始资源提取 |
| Background | `stages/background.py` | 背景提取（可编辑模式） |
| Font Matcher | `stages/font.py` | 字体映射表匹配 |
| Builder | `stages/builder.py` | PPTX 组装（python-pptx） |
| Model Manager | `infra/model_manager.py` | 模型下载、加载、缓存 |
| Config | `infra/config.py` | 全局配置管理 |
| Progress | `infra/progress.py` | CLI 进度显示 |
| Checkpoint | `infra/checkpoint.py` | 页级断点续传 |

## 2. 数据流

### 2.1 整体数据流

```
input.pdf
    ↓ Parser
PageImage[]          ← 高 DPI 页面图像 + 页面元数据 + 嵌入资源
    ↓ Layout
LayoutResult[]       ← 每页的区域列表 (bbox + semantic label)
    ↓ Extract (OCR ∥ Image ∥ Font)
SlideContent[]       ← 每页的完整内容描述 (背景 + 图片 + 文字 + 字体)
    ↓ Background (仅可编辑模式)
CleanBackground[]    ← 去除文字后的干净背景
    ↓ Builder
output.pptx
```

### 2.2 阶段间数据传递原则

- 阶段间通过不可变数据对象（dataclass）传递，不共享可变状态
- 每个阶段接收上游数据，产出新的数据对象，不修改输入
- 并行阶段（OCR / Image / Font）共享 LayoutResult 作为输入，产出各自独立的输出

## 3. 核心数据模型

### 3.1 数据模型定义

所有核心数据结构定义在 `models/` 目录下，使用 Python dataclass。

| 模型 | 文件 | 描述 |
|------|------|------|
| `PageImage` | `models/page.py` | 单页渲染结果：图像数据、页码、尺寸、DPI、嵌入资源列表 |
| `PageMetadata` | `models/page.py` | 页面元数据：页码、宽高比、总页数 |
| `LayoutRegion` | `models/layout.py` | 单个检测区域：bbox (x, y, w, h)、语义标签、置信度 |
| `LayoutResult` | `models/layout.py` | 单页布局检测结果：页码、区域列表 |
| `OCRResult` | `models/content.py` | 单区域 OCR 结果：文本内容、置信度、源区域引用 |
| `ExtractedImage` | `models/content.py` | 提取的图片：图像数据、bbox、来源（嵌入/裁切）、分辨率 |
| `FontMatch` | `models/content.py` | 字体匹配结果：字体名称、字体文件路径、是否为回退字体 |
| `SlideContent` | `models/slide.py` | 单页完整内容：页码、背景图、图片列表、文字区域列表 |
| `PipelineConfig` | `infra/config.py` | 运行时配置：输出模式、DPI、设备、模型路径 |

### 3.2 数据模型关系

```
PageImage (1) ──→ (1) LayoutResult
                       ├── (N) LayoutRegion ──→ OCRResult (1:1)
                       ├── (N) LayoutRegion ──→ ExtractedImage (1:1)
                       └── (N) LayoutRegion ──→ FontMatch (按标签)

LayoutResult + PageImage + OCRResult[] + ExtractedImage[] + FontMatch[]
    └──→ SlideContent (1:1)

SlideContent[] + CleanBackground[] (可选)
    └──→ output.pptx
```

## 4. Pipeline Orchestrator 设计

### 4.1 调度流程

```
1. 加载配置 (PipelineConfig)
2. 加载/创建 checkpoint
3. 遍历页码:
   a. 跳过 checkpoint 中已完成的页
   b. 执行 Parser → Layout → Extract → Background → Builder
   c. 任何阶段失败: 标记该页为 failed, 使用原始截图兜底
   d. 标记该页为 completed, 更新 checkpoint
4. 输出摘要报告
```

### 4.2 并行策略

阶段内并行（阶段 [3] Extract）：

```
LayoutResult
    ├── OCR (GLM-OCR 推理)      ← GPU/CPU 密集
    ├── Image (裁切 + 资源提取)  ← IO 密集
    └── Font (映射表查询)        ← CPU 轻量

三者在单页范围内并行，页间串行（简化资源管理和进度显示）。
```

### 4.3 断点续传

- 粒度：页级别
- 存储：JSON 文件（与输入 PDF 同目录，`.noteeditor_checkpoint.json`）
- 内容：已完成页码列表、每页处理状态（success/failed）、失败原因
- 恢复：启动时检测同名 checkpoint 文件，提示用户是否续传

### 4.4 错误隔离

- 单页处理异常捕获在 Pipeline Orchestrator 层
- 失败页不写入 checkpoint（可重试）
- 最终 PPTX 中失败页使用原始截图作为该页幻灯片内容

## 5. CLI 接口设计

### 5.1 命令格式

```bash
noteeditor <input.pdf> [options]
```

### 5.2 参数列表

| 参数 | 缩写 | 默认值 | 描述 |
|------|------|--------|------|
| `--output` | `-o` | 与输入同目录，同文件名 `.pptx` | 输出文件路径 |
| `--mode` | `-m` | `visual` | 输出模式：`visual` / `editable` |
| `--dpi` | | `300` | 页面渲染 DPI |
| `--device` | `-d` | `auto` | 模型运行设备：`auto` / `gpu` / `cpu` / `api` |
| `--retry-pages` | | 无 | 重试指定页码，如 `3,7,12` |
| `--force` | | `false` | 忽略已有 checkpoint，重新处理 |
| `--verbose` | `-v` | `false` | 详细日志输出 |

### 5.3 使用示例

```bash
# 基本用法（视觉保真模式）
noteeditor presentation.pdf

# 可编辑模式
noteeditor presentation.pdf --mode editable

# 指定输出路径和 GPU
noteeditor presentation.pdf -o slides.pptx --device gpu

# 重试失败的第 3 页和第 7 页
noteeditor presentation.pdf --retry-pages 3,7
```

## 6. 项目目录结构

```
noteeditor/
├── src/
│   └── noteeditor/
│       ├── __init__.py
│       ├── cli.py                  # CLI 入口
│       ├── pipeline.py             # Pipeline Orchestrator
│       ├── models/                 # 数据模型
│       │   ├── __init__.py
│       │   ├── page.py             # PageImage, PageMetadata
│       │   ├── layout.py           # LayoutRegion, LayoutResult
│       │   ├── content.py          # OCRResult, ExtractedImage, FontMatch
│       │   └── slide.py            # SlideContent
│       ├── stages/                 # 管线阶段
│       │   ├── __init__.py
│       │   ├── parser.py           # PDF 解析
│       │   ├── layout.py           # 布局检测
│       │   ├── ocr.py              # 文字 OCR
│       │   ├── image.py            # 图片提取
│       │   ├── background.py       # 背景提取
│       │   ├── font.py             # 字体匹配
│       │   └── builder.py          # PPTX 组装
│       └── infra/                  # 基础设施
│           ├── __init__.py
│           ├── model_manager.py    # 模型下载与管理
│           ├── config.py           # 配置管理
│           ├── progress.py         # 进度显示
│           └── checkpoint.py       # 断点续传
├── models/                         # 预训练模型文件（.gitignore）
├── fonts/                          # NotebookLM 字体文件
│   └── font_map.yaml               # 字体映射表配置
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                   # 测试用 PDF 文件
├── docs/
├── pyproject.toml
└── README.md
```

## 7. 依赖清单

| 依赖 | 用途 | 许可 | 必须/可选 |
|------|------|------|----------|
| PyMuPDF | PDF 解析、页面渲染、资源提取 | AGPL-3.0 | 必须 |
| PP-DocLayout-V3 | 布局检测模型 | Apache 2.0 | 必须 |
| GLM-OCR | 文字 OCR 模型 | Apache 2.0 | 必须 |
| LaMA | 背景文字去除（可编辑模式） | Apache 2.0 | 可选（可编辑模式需要） |
| python-pptx | PPTX 生成 | MIT | 必须 |
| ONNX Runtime | 模型推理运行时 | MIT | 必须 |
| Pillow | 图像处理 | HPND | 必须 |
| PyYAML | 字体映射表解析 | MIT | 必须 |
| click | CLI 框架 | BSD-3 | 必须 |
| rich | CLI 进度条和格式化输出 | MIT | 必须 |
| httpx | 模型下载（model_manager） | Apache 2.0 | 必须 |
