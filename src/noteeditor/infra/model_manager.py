"""Model manager - load and verify ONNX models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import onnxruntime as ort  # type: ignore[import-untyped]

_LAYOUT_MODEL_FILENAME = "pp_doclayout_v3.onnx"
_LAYOUT_MODEL_URL = (
    "https://huggingface.co/alex-dinh/PP-DocLayoutV3-ONNX/"
    "resolve/main/pp_doclayout_v3.onnx"
)

_OCR_MODEL_FILENAME = "glm_ocr.onnx"
_OCR_MODEL_URL = (
    "https://huggingface.co/THUDM/glm-ocr/"
    "resolve/main/glm_ocr.onnx"
)


@dataclass(frozen=True)
class ModelManager:
    """Load and verify ONNX models for inference."""

    models_dir: Path
    device: str = "auto"

    def get_layout_model(self) -> ort.InferenceSession:
        """Load the PP-DocLayout-V3 layout detection model.

        Raises:
            FileNotFoundError: If the model file does not exist.
                Message includes download URL and target path.
            RuntimeError: If the model file exists but fails to load.
        """
        model_path = self.models_dir / _LAYOUT_MODEL_FILENAME
        if not model_path.exists():
            msg = (
                f"Layout model not found at {model_path}. "
                f"Please download it from {_LAYOUT_MODEL_URL} "
                f"and place it in {self.models_dir}."
            )
            raise FileNotFoundError(msg)

        providers = self._resolve_providers()
        try:
            return ort.InferenceSession(str(model_path), providers=providers)
        except Exception as exc:
            raise RuntimeError(f"Failed to load layout model from {model_path}: {exc}") from exc

    def get_ocr_model(self) -> ort.InferenceSession:
        """Load the GLM-OCR text recognition model.

        Raises:
            FileNotFoundError: If the model file does not exist.
                Message includes download URL and target path.
            RuntimeError: If the model file exists but fails to load.
        """
        model_path = self.models_dir / _OCR_MODEL_FILENAME
        if not model_path.exists():
            msg = (
                f"OCR model not found at {model_path}. "
                f"Please download it from {_OCR_MODEL_URL} "
                f"and place it in {self.models_dir}."
            )
            raise FileNotFoundError(msg)

        providers = self._resolve_providers()
        try:
            return ort.InferenceSession(str(model_path), providers=providers)
        except Exception as exc:
            raise RuntimeError(f"Failed to load OCR model from {model_path}: {exc}") from exc

    def _resolve_providers(self) -> list[str]:
        """Resolve ONNX Runtime execution providers based on device setting.

        Raises:
            ValueError: If device is not one of 'auto', 'cpu', 'gpu'.
        """
        if self.device == "cpu":
            return ["CPUExecutionProvider"]
        if self.device == "gpu":
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if self.device == "auto":
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            return ["CPUExecutionProvider"]
        raise ValueError(
            f"Invalid device '{self.device}'. Must be 'auto', 'cpu', or 'gpu'."
        )
