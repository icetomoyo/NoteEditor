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
    embedded_images: list[EmbeddedResource]  # PDF 中嵌入的原始图片
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

### 1.2 LayoutRegion / LayoutResult（models/layout.py）

```python
class RegionLabel(str, Enum):
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
    mode: Literal["visual", "editable"]
    dpi: int                         # 默认 300
    device: Literal["auto", "gpu", "cpu", "api"]
    retry_pages: set[int] | None     # 重试指定页码
    force: bool                       # 忽略 checkpoint
    verbose: bool
    models_dir: Path                  # 模型存放目录
    fonts_dir: Path                   # 字体目录
    checkpoint_path: Path             # checkpoint 文件路径
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

PP-DocLayout-V3 输出标签到 `RegionLabel` 的映射关系，维护在模块内部常量中。

**运行时适配：**
- GPU: `onnxruntime.InferenceSession(providers=["CUDAExecutionProvider"])`
- CPU: `onnxruntime.InferenceSession(providers=["CPUExecutionProvider"])`
- 由 `infra/model_manager.py` 根据配置选择 provider

### 2.3 Stage: OCR（stages/ocr.py）

**输入：** `PageImage`, `LayoutResult` (过滤 label ∈ {TITLE, BODY_TEXT, EQUATION, CODE_BLOCK})
**输出：** `list[OCRResult]`

**处理流程：**

```
1. 从 LayoutResult 中筛选文字类区域:
   labels = {TITLE, BODY_TEXT, EQUATION, CODE_BLOCK}
2. 对每个文字区域:
   a. 根据 bbox 从 PageImage.image 裁切区域图像
   b. 适当扩展 bbox 边界 (padding=10px, 防止文字被截断)
   c. 运行 GLM-OCR 推理:
      - 输入: 裁切后的区域图像
      - 输出: 文本内容 + 是否公式 + LaTeX 内容
   d. 构造 OCRResult (frozen dataclass)
3. 返回 OCRResult 列表
```

**公式处理：**
- GLM-OCR 输出中标记为公式的文本，`is_formula=True`
- `formula_latex` 存储原始 LaTeX 字符串
- PPTX Builder 阶段负责将 LaTeX 渲染为图片

**云端 API 模式：**
- `device=api` 时，调用 Zhipu BigModel API 代替本地推理
- 需要环境变量 `ZHIPU_API_KEY`
- API 请求/响应格式在实现阶段定义

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
   - 合并所有文字类区域的 bbox 为 mask (白色=文字区域, 黑色=背景)
   - mask 尺寸与 PageImage.image 相同
2. 判断背景复杂度:
   a. 取 mask 黑色区域 (背景区域) 的像素
   b. 计算颜色标准差:
      - std < 15: 简单背景 (纯色或近似纯色)
      - 15 <= std < 50: 渐变背景
      - std >= 50: 复杂背景 (图案/照片)
3. 根据复杂度选择策略:
   - 简单背景: 用背景区域的颜色中值填充 mask 白色区域
   - 渐变背景: 对背景区域做渐变拟合，用拟合结果填充
   - 复杂背景: 运行 LaMA Inpainting，以 mask 为输入
4. 返回干净背景图像
```

### 2.7 Stage: Builder（stages/builder.py）

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

**字号估算算法：**
```
font_size_pt ≈ bbox_height_px * (72 / dpi) * 0.8
# 乘以 0.8 是因为文字通常不占满整个 bbox（有行间距等）
```

**字体颜色采样：**
```
从 PageImage.image 中取 bbox 顶部中间区域的像素颜色作为字体颜色近似值
```

**LaTeX 渲染为图片：**
- 使用 matplotlib 或 latex2png 将 LaTeX 字符串渲染为 PNG
- 渲染尺寸根据 bbox 大小缩放
- 添加到幻灯片作为图片

## 3. 基础设施详细设计

### 3.1 Model Manager（infra/model_manager.py）

**职责：** 模型文件的下载、校验、加载。

```python
class ModelManager:
    def __init__(self, models_dir: Path, device: str)

    def ensure_model(self, model_name: str) -> Path:
        """确保模型已下载，返回模型文件路径。"""

    def load_onnx_session(self, model_name: str) -> InferenceSession:
        """加载 ONNX 推理会话。"""

    def _download_model(self, model_name: str) -> Path:
        """从指定 URL 下载模型文件。"""

    def _verify_checksum(self, file_path: Path, expected: str) -> bool:
        """校验模型文件 SHA256。"""
```

**模型注册表（硬编码在模块中）：**

```python
MODEL_REGISTRY = {
    "pp_doclayout_v3": {
        "url": "TODO",           # 模型下载地址
        "filename": "pp_doclayout_v3.onnx",
        "checksum_sha256": "TODO",
    },
    "glm_ocr": {
        "url": "TODO",
        "filename": "glm_ocr.onnx",
        "checksum_sha256": "TODO",
    },
    "lama": {
        "url": "TODO",
        "filename": "lama.onnx",
        "checksum_sha256": "TODO",
    },
}
```

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
