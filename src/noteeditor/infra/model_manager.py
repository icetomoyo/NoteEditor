"""Model manager - load layout model and create OCR backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import onnxruntime as ort  # type: ignore[import-untyped]

from noteeditor.infra.ocr_backend import OCRBackend, create_ocr_backend

_LAYOUT_MODEL_FILENAME = "pp_doclayout_v3.onnx"
_LAYOUT_MODEL_URL = (
    "https://huggingface.co/alex-dinh/PP-DocLayoutV3-ONNX/"
    "resolve/main/pp_doclayout_v3.onnx"
)


@dataclass(frozen=True)
class ModelManager:
    """Load layout model (ONNX) and create OCR backend."""

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

    def create_ocr_backend(self) -> OCRBackend:
        """Create an OCR backend based on the device setting.

        Raises:
            ValueError: For invalid device or missing API key when device=api.
            RuntimeError: For device=auto when no backend is available.
        """
        api_key = os.environ.get("ZHIPU_API_KEY")
        return create_ocr_backend(self.device, api_key=api_key)

    def _resolve_providers(self) -> list[str]:
        """Resolve ONNX Runtime execution providers for layout model.

        Raises:
            ValueError: If device is not one of 'auto', 'cpu', 'gpu',
                or any OCR-specific device.
        """
        # Layout model always uses ONNX, map device to providers
        device = self.device

        # OCR-specific devices default to auto for layout ONNX
        if device in ("transformers", "ollama", "vllm", "api"):
            device = "auto"

        if device == "cpu":
            return ["CPUExecutionProvider"]
        if device == "gpu":
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device == "auto":
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            return ["CPUExecutionProvider"]
        raise ValueError(
            f"Invalid device '{self.device}'. "
            "Must be one of: auto, transformers, ollama, vllm, api, cpu, gpu."
        )
