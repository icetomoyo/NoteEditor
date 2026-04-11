# NoteEditor DD

> Detailed Design | 版本: 0.1-draft | 日期: 2026-03-22

## 1. 数据结构定义

### 1.1 PageImage（models/page.py）

```python
@dataclass(frozen=True)
class PageImage:
    page_number: int                # 页码（0-based）
    width_px: int                   # 渲染宽度（像素）
    height_px: int                  # 渲染高度（像素）
    dpi: int                        # 渲染 DPI
    aspect_ratio: float             # 宽高比 (16:9 = 1.778)
    image: np.ndarray               # 页面图像 (H, W, 3) RGB
    embedded_images: tuple[EmbeddedResource, ...]  # PDF 中嵌入的原始图片（frozen 用 tuple）
```

```python
@dataclass(frozen=True)
class EmbeddedResource:
    index: int                      # 资源在 PDF 中的索引
    bbox: BoundingBox               # 在页面中的位置
    image: np.ndarray               # 图片数据 (H, W, 3) RGB
    width_px: int                   # 原始宽度
    height_px: int                  # 原始高度
```

```python
@dataclass(frozen=True)
class PageMetadata:
    page_number: int                # 页码（0-based）
    width_px: int                   # 渲染宽度（像素）
    height_px: int                  # 渲染高度（像素）
    aspect_ratio: float             # 宽高比 (16:9 = 1.778)
    total_pages: int                # PDF 总页数
```

### 1.2 LayoutRegion / LayoutResult（models/layout.py）

```python
from enum import StrEnum

class RegionLabel(StrEnum):
    TITLE = "title"
    BODY_TEXT = "body_text"
    IMAGE = "image"
    TABLE = "table"
    HEADER = "header"
    FOOTER = "footer"
    FIGURE_CAPTION = "figure_caption"
    EQUATION = "equation"
    CODE_BLOCK = "code_block"
    REFERENCE = "reference"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class BoundingBox:
    x: float                        # 左上角 x（像素，相对于渲染图）
    y: float                        # 左上角 y
    width: float                    # 宽度
    height: float                   # 高度

@dataclass(frozen=True)
class LayoutRegion:
    bbox: BoundingBox
    label: RegionLabel
    confidence: float               # 0.0 - 1.0
    region_id: str                  # 唯一标识，格式 "page{N}_region{M}"

@dataclass(frozen=True)
class LayoutResult:
    page_number: int
    regions: tuple[LayoutRegion, ...]
```

### 1.3 Content Types（models/content.py）

```python
@dataclass(frozen=True)
class OCRResult:
    region_id: str                  # 引用 LayoutRegion.region_id
    text: str                       # OCR 识别的文本
    confidence: float               # 识别置信度
    is_formula: bool                # 是否为公式（LaTeX）
    formula_latex: str | None       # LaTeX 公式内容（仅 is_formula=True 时）

@dataclass(frozen=True)
class ExtractedImage:
    region_id: str                  # 引用 LayoutRegion.region_id
    image: np.ndarray               # 图片数据
    source: Literal["embedded", "cropped"]  # 来源：PDF 嵌入 or 从渲染图裁切
    bbox: BoundingBox               # 在原始页面中的位置
    width_px: int
    height_px: int

@dataclass(frozen=True)
class FontMatch:
    region_id: str                  # 引用 LayoutRegion.region_id
    label: RegionLabel              # 用于查找的语义标签
    font_name: str                  # 匹配到的字体名称
    font_path: Path | None          # 字体文件路径（None 表示使用系统字体）
    system_fallback: str | None     # 回退系统字体名称（font_path 为 None 时）
    is_fallback: bool               # 是否使用了回退字体
```

### 1.4 SlideContent（models/slide.py）

```python
@dataclass(frozen=True)
class TextBlock:
    region_id: str
    bbox: BoundingBox
    text: str
    font_match: FontMatch
    is_formula: bool
    formula_latex: str | None

@dataclass(frozen=True)
class ImageBlock:
    region_id: str
    bbox: BoundingBox
    image: np.ndarray
    source: Literal["embedded", "cropped"]

@dataclass(frozen=True)
class SlideContent:
    page_number: int
    background_image: np.ndarray | None   # 干净背景（仅可编辑模式）
    full_page_image: np.ndarray          # 完整页面截图（视觉保真模式背景）
    text_blocks: tuple[TextBlock, ...]
    image_blocks: tuple[ImageBlock, ...]
    status: Literal["success", "failed", "fallback"]
```

### 1.5 PipelineConfig（infra/config.py）

```python
@dataclass(frozen=True)
class PipelineConfig:
    input_path: Path
    output_path: Path
    mode: Literal["visual", "editable"]       # 默认 "editable"
    dpi: int                                   # 默认 300
    device: Literal["auto", "transformers", "ollama", "vllm", "api"]  # 默认 "auto"
    verbose: bool
    models_dir: Path                           # 布局检测模型目录
    fonts_dir: Path                            # 字体目录
    retry_pages: frozenset[int] | None         # 重试指定页码（frozen 保持不可变）
    force: bool                                # 忽略 checkpoint
    checkpoint_path: Path                      # checkpoint 文件路径
```

## 2. 管线阶段详细设计

### 2.1 Stage: Parser（stages/parser.py）

**输入：** `Path` (PDF 文件路径)、`PipelineConfig`
**输出：** `list[PageImage]`

**处理流程：**

```
1. 打开 PDF (fitz.open)
2. 获取总页数
3. 遍历每页:
   a. 获取页面尺寸，计算宽高比
   b. 以 config.dpi 渲染为 numpy array (RGB)
   c. 提取嵌入图片资源:
      - 遍历页面 image list (fitz.Page.get_images)
      - 获取图片 bbox (fitz.Page.get_image_rects)
      - 提取原始图片数据 (fitz.extract_image)
      - 构造 EmbeddedResource 列表
   d. 构造 PageImage (frozen dataclass)
4. 返回 PageImage 列表
```

**错误处理：**
- PDF 无法打开：抛出 `InputError`，终止管线
- 单页渲染失败：标记该页 `status=failed`，跳过

**关键实现细节：**
- PyMuPDF 的 `Page.get_pixmap(dpi=N)` 渲染为 Pixmap，转 numpy: `np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.h, pixmap.w, pixmap.n)`
- 嵌入图片提取时需要处理内联图片（small inline images）和外部图片（XObjects），优先提取 XObjects

### 2.2 Stage: Layout（stages/layout.py）

**输入：** `PageImage`
**输出：** `LayoutResult`

**处理流程：**

```
1. 将 PageImage.image 转为模型输入格式
2. 运行 PP-DocLayout-V3 推理:
   - 输入: 页面图像 (H, W, 3)
   - 输出: 区域列表 [(bbox, label, confidence), ...]
3. 将模型输出映射到 LayoutRegion:
   - bbox → BoundingBox(x, y, w, h)
   - label → RegionLabel (模型标签到枚举的映射)
   - 生成 region_id: "page{N}_region{M}"
4. 过滤低置信度区域 (confidence < 0.5)
5. 构造 LayoutResult (frozen dataclass)
```

**标签映射：**

PP-DocLayout-V3 输出标签到 `RegionLabel` 的映射关系，维护在模块内部常量中（26 类 → 11 枚举值）。

**NMS 后处理（v0.5.0 新增）：**

PP-DocLayout-V3 可能输出重叠的检测区域（同一内容被检测为不同标签）。需在 confidence 过滤之后执行 IoU-based NMS：

```
1. 按 confidence 降序排列
2. 遍历每个区域 A:
   a. 如果 A 未被抑制:
      - 对所有 confidence 更低的区域 B:
        - 如果 IoU(A, B) > 0.5: 标记 B 为被抑制
3. 返回未被抑制的区域列表
```

**运行时适配：**
- GPU: `onnxruntime.InferenceSession(providers=["CUDAExecutionProvider"])`
- CPU: `onnxruntime.InferenceSession(providers=["CPUExecutionProvider"])`
- 由 `infra/model_manager.py` 根据配置选择 provider

### 2.3 Stage: OCR（stages/ocr.py）

**输入：** `PageImage`, `LayoutResult` (过滤 label ∈ {TITLE, BODY_TEXT, EQUATION, CODE_BLOCK}), `OCRBackend`
**输出：** `tuple[OCRResult, ...]`

**架构说明：**

GLM-OCR 是 Vision-Language Model（CogViT 0.4B 视觉编码器 + GLM-0.5B 语言解码器），推理需要自回归 token 生成（非单次前向传播）。OCR Stage 通过 `OCRBackend` 抽象层调用推理，不直接依赖任何具体推理框架。

**处理流程：**

```
1. 从 LayoutResult 中筛选文字类区域:
   labels = {TITLE, BODY_TEXT, EQUATION, CODE_BLOCK}
2. 对每个文字区域:
   a. 根据 bbox 从 PageImage.image 裁切区域图像
   b. 适当扩展 bbox 边界 (padding=10px, 防止文字被截断)
   c. 根据区域语义标签选择 OCR 任务提示词:
      - TITLE / BODY_TEXT: "Text Recognition:"
      - EQUATION: "Formula Recognition:"
      - TABLE: "Table Recognition:"
   d. 调用 backend.recognize(cropped_image, task_prompt) → OCRResponse
   e. 构造 OCRResult (frozen dataclass)
3. 返回 OCRResult 元组
```

**OCR Backend 抽象层（infra/ocr_backend.py）：**

OCR Stage 通过统一的 `OCRBackend` Protocol 调用推理，隔离具体推理框架差异。详见 §3.5。

```python
class OCRBackend(Protocol):
    def recognize(self, image: np.ndarray, task: str) -> OCRResponse: ...
    def is_available(self) -> bool: ...
```

**四种后端实现：**

| 后端 | 类名 | 调用方式 | 模型管理 |
|------|------|---------|---------|
| Transformers | `TransformersBackend` | 进程内 `model.generate()` | HuggingFace 自动缓存 |
| Ollama | `OllamaBackend` | HTTP POST `localhost:11434` | `ollama pull glm-ocr` |
| vLLM | `VLLMBackend` | HTTP POST `localhost:8000` (OpenAI 兼容) | 启动时指定模型 ID |
| Zhipu API | `ZhipuAPIBackend` | HTTP POST 云端 API | 无需本地模型 |

**公式/表格处理：**
- GLM-OCR 通过不同的 task prompt 区分任务类型
- 公式输出 LaTeX 字符串，`is_formula=True`，`formula_latex` 存储原始 LaTeX
- 表格输出 HTML/Markdown 格式（v0.5.0 暂作为文本处理，不还原为原生表格对象）
- PPTX Builder 阶段负责将 LaTeX 渲染为图片

### 2.4 Stage: Image Extractor（stages/image.py）

**输入：** `PageImage`, `LayoutResult` (过滤 label = IMAGE), `list[EmbeddedResource]`
**输出：** `list[ExtractedImage]`

**处理流程：**

```
1. 从 LayoutResult 中筛选图片类区域 (label = IMAGE)
2. 对每个图片区域:
   a. 检查是否有嵌入资源与该区域重叠 (IoU > 0.5):
      - 有匹配: 使用嵌入资源 (source="embedded")，分辨率更高
      - 无匹配: 从 PageImage.image 裁切 (source="cropped")
   b. 裁切时使用 bbox 坐标从渲染图中提取子图
   c. 构造 ExtractedImage (frozen dataclass)
3. 返回 ExtractedImage 列表
```

**嵌入资源匹配算法：**
```
IoU(EmbeddedResource.bbox, LayoutRegion.bbox) > 0.5 → 使用嵌入资源
```

### 2.5 Stage: Font Matcher（stages/font.py）

**输入：** `LayoutResult` (筛选 label ∈ {TITLE, BODY_TEXT, CODE_BLOCK}), `fonts_dir`
**输出：** `list[FontMatch]`

**处理流程：**

```
1. 加载字体映射表: fonts/font_map.yaml
2. 对每个文字区域:
   a. 以 label (TITLE/BODY_TEXT 等) 作为键查映射表
   b. 找到字体名称 → 检查字体文件是否存在:
      - 存在: font_path=文件路径, is_fallback=False
      - 不存在: 使用映射表中的 system_fallback, is_fallback=True
   c. 映射表无匹配: 使用默认系统字体 (Arial), is_fallback=True
   d. 构造 FontMatch (frozen dataclass)
3. 返回 FontMatch 列表
```

**字体映射表格式（fonts/font_map.yaml）：**

```yaml
# NotebookLM 字体映射表
# label: NotebookLM 模板中该文本类型使用的字体
title:
  font_name: "Google Sans"
  font_file: "GoogleSans-Bold.ttf"
  system_fallback: "Arial"

body_text:
  font_name: "Google Sans"
  font_file: "GoogleSans-Regular.ttf"
  system_fallback: "Arial"

code_block:
  font_name: "Google Sans Mono"
  font_file: "GoogleSansMono-Regular.ttf"
  system_fallback: "Consolas"
```

### 2.6 Stage: Background Extractor（stages/background.py）

**输入：** `PageImage`, `LayoutResult`
**输出：** `np.ndarray` (干净背景图像)
**条件：** 仅在 `mode=editable` 时执行

**处理流程：**

```
1. 构造文字区域 mask:
   - 合并所有文字类区域 (TITLE, BODY_TEXT, EQUATION, CODE_BLOCK) 的 bbox 为 mask
   - mask: uint8 (H, W), 255=文字区域, 0=背景
2. 判断背景复杂度:
   a. 取 mask=0 区域的像素
   b. 计算颜色标准差 (RGB 三通道整体):
      - std < 15: 简单背景 (纯色或近似纯色)
      - 15 <= std < 50: 渐变背景
      - std >= 50: 复杂背景 (图案/照片)
3. 根据复杂度选择策略:
   - 简单背景: 用背景区域的颜色中值填充文字区域
   - 渐变背景: 向量化线性插值填充（v0.5.0 需优化，避免逐行 Python 循环）
   - 复杂背景: 运行 LaMA Inpainting（v0.5.0 新增），以 mask 为输入；LaMA 不可用时回退白色填充
4. 返回干净背景图像（新数组，不修改输入）
```

**渐变填充性能要求（v0.5.0）：**

v0.4.0 的 `_fill_gradient` 使用纯 Python 逐行循环，在 300 DPI 图像 (~2109 行) 上耗时数秒。v0.5.0 需改为 numpy 向量化操作或使用 `cv2.inpaint()`，目标单页 < 100ms。

### 2.7 Stage: Assemble（stages/builder.py — assemble_slide）

**输入：** `PageImage`, `LayoutResult`, `OCRResult[]`, `ExtractedImage[]`, `FontMatch[]`, `TextStyle[]`, `background_image`
**输出：** `SlideContent`

**职责：** 将各阶段的独立输出组合为完整的 `SlideContent`。这是一个纯数据组装阶段，不涉及推理或图像处理。

**处理流程：**

```
1. 构建区域查找表: region_id → LayoutRegion
2. 构建字体/样式查找表: region_id → FontMatch / TextStyle
3. 将 OCRResult 映射为 TextBlock（关联 bbox、font、style）
4. 将 ExtractedImage 映射为 ImageBlock
5. 组装 SlideContent (frozen dataclass)
```

**回退逻辑：**
- OCRResult 引用的 region_id 在 LayoutResult 中不存在：跳过该文本块
- FontMatch 不存在时使用 fallback（Arial）
- TextStyle 不存在时 Builder 使用 bbox 高度估算

### 2.8 Stage: Builder（stages/builder.py）

**输入：** `list[SlideContent]`, `PipelineConfig`
**输出：** `.pptx` 文件

**处理流程：**

```
1. 创建 PPTX (Presentation)
2. 设置幻灯片尺寸:
   - 从第一页 PageImage 的宽高比计算英寸尺寸
   - 16:9 → slide_width=13.333in, slide_height=7.5in
3. 遍历 SlideContent:
   a. status=failed:
      - 将 full_page_image 作为背景图 (兜底)
      - 继续
   b. mode=visual:
      - 将 full_page_image 设为幻灯片背景 (BackgroundFill)
      - 遍历 image_blocks: 添加图片 (slide.shapes.add_picture)
      - 不添加文字框
   c. mode=editable:
      - 将 background_image 设为幻灯片背景
      - 遍历 image_blocks: 添加图片
      - 遍历 text_blocks:
        - is_formula=True: 渲染 LaTeX 为图片，添加图片
        - is_formula=False: 添加文字框 (slide.shapes.add_textbox)
          - 设置字体 (font_match.font_name / system_fallback)
          - 设置字体大小 (根据 bbox 高度估算)
          - 设置字体颜色 (从原始区域图像中采样)
4. 保存 PPTX
```

**字号估算算法（v0.5.0 修正）：**

v0.4.0 的公式 `bbox_height * (72/dpi) * 0.8` 假设 bbox 只包含一行文字，对多行 BODY_TEXT 区域会严重高估。v0.5.0 结合 OCR 文本内容修正：

```
line_count = max(1, text.count('\n') + 1)
single_line_height = bbox_height_px / line_count
font_size_pt ≈ single_line_height * (72 / dpi) * 0.8
```

字号估算逻辑位于独立的 `stages/style.py` 阶段，不在 Builder 内部。

**字体颜色采样：**
```
从 PageImage.image 中取 bbox 顶部 1/3、中间 80% 宽度区域的像素
过滤掉近白色/背景色像素（brightness > 690），对深色像素取量化后的众数
无深色像素时回退到黑色 (0, 0, 0)
```

**文本框填充策略（v0.5.0 修正）：**

v0.4.0 的文本框始终使用白色填充，与背景提取结果矛盾。v0.5.0 根据背景可用性选择填充方式：

```
如果 SlideContent.background_image 存在（已提取干净背景）:
    → 文本框无填充（透明），文字直接显示在干净背景上
否则（回退到截图背景）:
    → 文本框白色填充，覆盖原始文字
```

**背景图设置（v0.5.0 修正）：**

使用 python-pptx 的 `slide.background` API 设置原生幻灯片背景，而非 `add_picture` 添加图片 Shape。原生背景不可被用户误操作移动或删除。

**LaTeX 渲染为图片：**
- 使用 matplotlib 或 latex2png 将 LaTeX 字符串渲染为 PNG
- 渲染尺寸根据 bbox 大小缩放
- 添加到幻灯片作为图片

## 3. 基础设施详细设计

### 3.1 Model Manager（infra/model_manager.py）

**职责：** 布局检测模型（ONNX）的加载，以及 OCR Backend 的创建。

```python
@dataclass(frozen=True)
class ModelManager:
    models_dir: Path
    device: str = "auto"

    def get_layout_model(self) -> ort.InferenceSession:
        """加载 PP-DocLayout-V3 ONNX 模型。
        缺失时抛出 FileNotFoundError + 下载指引。"""

    def create_ocr_backend(self) -> OCRBackend:
        """根据 device 设置创建对应的 OCR 后端。
        auto: 按优先级探测 vLLM → Ollama → Transformers(GPU) → Transformers(CPU)
        transformers: TransformersBackend
        ollama: OllamaBackend
        vllm: VLLMBackend
        api: ZhipuAPIBackend
        """
```

**布局检测模型注册表：**

```python
_LAYOUT_MODEL_FILENAME = "pp_doclayout_v3.onnx"
_LAYOUT_MODEL_URL = "https://huggingface.co/alex-dinh/PP-DocLayoutV3-ONNX/resolve/main/pp_doclayout_v3.onnx"
```

> **注意**: GLM-OCR 模型不再由 ModelManager 直接加载，而是由各 OCR Backend 自行管理（Transformers: HuggingFace 缓存, Ollama: ollama pull, vLLM: 启动参数）。

### 3.2 Config（infra/config.py）

**职责：** 从 CLI 参数和环境变量构建 `PipelineConfig`。

```
优先级: CLI 参数 > 环境变量 > 默认值

环境变量:
  NOTEEDITOR_DPI          → 默认 DPI
  NOTEEDITOR_DEVICE       → 默认设备
  NOTEEDITOR_MODELS_DIR   → 模型目录
  NOTEEDITOR_FONTS_DIR    → 字体目录
  ZHIPU_API_KEY           → GLM-OCR 云端 API 密钥 (device=api 时需要)
```

### 3.3 Progress（infra/progress.py）

**职责：** CLI 进度显示，使用 rich 库。

```
输出格式:
  [1/15] Page 1 ─── Layout detection... ████████░░ 80%
  [1/15] Page 1 ─── OCR...              ░░░░░░░░░░   0%

预计剩余时间基于已处理页的平均耗时 × 剩余页数。
```

### 3.4 Checkpoint（infra/checkpoint.py）

**职责：** 页级断点续传。

```python
@dataclass
class CheckpointData:
    input_pdf: str               # 输入 PDF 路径（用于校验）
    total_pages: int
    completed_pages: dict[int, str]  # {页码: "success" | "failed"}
    failed_reasons: dict[int, str]   # {页码: 失败原因}

class CheckpointManager:
    def __init__(self, checkpoint_path: Path)

    def load(self) -> CheckpointData | None:
        """加载 checkpoint，不存在或格式不匹配时返回 None。"""

    def save(self, data: CheckpointData) -> None:
        """保存 checkpoint 到 JSON 文件。"""

    def mark_completed(self, data: CheckpointData, page: int, status: str, reason: str = "") -> CheckpointData:
        """标记页完成，返回新的不可变 CheckpointData。"""

    def clear(self) -> None:
        """处理完成后删除 checkpoint 文件。"""
```

**Checkpoint 文件格式：**

```json
{
  "input_pdf": "presentation.pdf",
  "total_pages": 15,
  "completed_pages": {
    "0": "success",
    "1": "success",
    "2": "failed"
  },
  "failed_reasons": {
    "2": "Layout detection: ONNX runtime error - OOM"
  }
}
```

**校验逻辑：**
- 加载时检查 `input_pdf` 是否与当前输入匹配
- 不匹配则提示用户（可能是不同 PDF），由 `--force` 参数控制是否覆盖

### 3.5 OCR Backend（infra/ocr_backend.py）

**职责：** 为 GLM-OCR 推理提供统一接口，隔离 Transformers / Ollama / vLLM / API 四种后端的差异。

**接口定义：**

```python
@dataclass(frozen=True)
class OCRResponse:
    """单次 OCR 推理的原始响应。"""
    text: str
    is_formula: bool
    formula_latex: str | None
    raw_output: str  # 后端原始输出（用于调试）

class OCRBackend(Protocol):
    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        """对单张裁切图像执行 OCR。
        task: "Text Recognition:" / "Formula Recognition:" / "Table Recognition:"
        """

    def is_available(self) -> bool:
        """检查后端是否可用（模型已加载 / 服务已启动）。"""
```

**后端实现：**

#### TransformersBackend

```python
class TransformersBackend:
    """进程内 HuggingFace Transformers 推理。"""

    def __init__(self, model_id: str = "zai-org/GLM-OCR", device: str = "auto"):
        # 延迟加载: 首次 recognize() 时才加载模型
        self._model = None
        self._processor = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from transformers import AutoModelForImageTextToText, AutoProcessor
            self._processor = AutoProcessor.from_pretrained(self._model_id)
            self._model = AutoModelForImageTextToText.from_pretrained(
                self._model_id, torch_dtype="auto", device_map="auto",
            )

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        self._ensure_loaded()
        # 构造 chat message → processor.apply_chat_template → model.generate → decode
```

**显存**: 4-6GB (FP16) / 2-3GB (BF16)
**首次加载**: ~10-20秒（模型下载 + 加载）
**推理速度**: ~2-3秒/区域 (GPU)

#### OllamaBackend

```python
class OllamaBackend:
    """调用本地 Ollama 服务。"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "glm-ocr"):
        ...

    def is_available(self) -> bool:
        # GET /api/tags 检查模型是否已拉取
        ...

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        # 1. 图像编码为 base64
        # 2. POST /api/generate {"model": "glm-ocr", "prompt": task, "images": [base64]}
        # 3. 解析响应 → OCRResponse
```

**显存**: 2-3GB (GGUF 量化)
**推理速度**: ~2-4秒/区域 (GPU)

#### VLLMBackend

```python
class VLLMBackend:
    """调用本地 vLLM 服务（OpenAI 兼容 API）。"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        ...

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        # 1. 图像编码为 base64
        # 2. POST /v1/chat/completions（OpenAI 格式）
        # 3. 解析响应 → OCRResponse
```

**显存**: 4-6GB (FP16)
**推理速度**: ~0.5秒/区域 (批量优化)

#### ZhipuAPIBackend

```python
class ZhipuAPIBackend:
    """调用 Zhipu BigModel 云端 API。"""

    def __init__(self, api_key: str, api_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"):
        ...
```

**自动探测逻辑（device=auto）：**

```python
def create_ocr_backend(device: str) -> OCRBackend:
    if device == "auto":
        # 1. 检查 vLLM 服务: GET http://localhost:8000/health
        # 2. 检查 Ollama 服务: GET http://localhost:11434/api/tags → 查找 glm-ocr
        # 3. 检查 torch + transformers 可用 + GPU
        # 4. Transformers CPU 模式
        # 5. 全部不可用: 抛出错误
    ...
```
