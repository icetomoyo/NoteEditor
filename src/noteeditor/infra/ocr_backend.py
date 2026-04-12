"""OCR backend abstraction — Transformers / Ollama / vLLM / Zhipu API.

Provides a unified interface for GLM-OCR inference across different
runtime backends. Each backend handles model loading, image encoding,
and response parsing independently.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Protocol, runtime_checkable

import httpx
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRResponse:
    """Raw response from a single OCR inference call."""

    text: str
    is_formula: bool
    formula_latex: str | None
    raw_output: str


def _encode_image_base64(image: np.ndarray) -> str:
    """Encode a numpy RGB image as JPEG base64 string."""
    from PIL import Image as PILImage

    buf = BytesIO()
    PILImage.fromarray(image).save(buf, format="JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _is_formula_task(task: str) -> bool:
    """Check if the task prompt indicates formula recognition."""
    return "Formula" in task


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class OCRBackend(Protocol):
    """Unified interface for OCR inference backends."""

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        """Run OCR on a single cropped image region.

        Args:
            image: Cropped region image (H, W, 3), dtype uint8, RGB.
            task: Task prompt, e.g. "Text Recognition:", "Formula Recognition:".

        Returns:
            OCRResponse with recognized text.
        """
        ...

    def is_available(self) -> bool:
        """Check whether this backend is ready to serve requests."""
        ...


# ---------------------------------------------------------------------------
# Ollama Backend
# ---------------------------------------------------------------------------


@dataclass
class OllamaBackend:
    """Call local Ollama service for GLM-OCR inference."""

    base_url: str = "http://localhost:11434"
    model: str = "glm-ocr"

    def is_available(self) -> bool:
        """Check if Ollama is running and the model is pulled."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            if resp.status_code != 200:
                return False
            data = resp.json()
            models = data.get("models", [])
            return any(self.model in m.get("name", "") for m in models)
        except Exception:
            return False

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        """Run OCR via Ollama native API."""
        img_b64 = _encode_image_base64(image)

        payload = {
            "model": self.model,
            "prompt": task,
            "images": [img_b64],
            "stream": False,
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{self.base_url}/api/generate", json=payload)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama request failed: HTTP {resp.status_code} - {resp.text}"
            )

        body = resp.json()
        text = body.get("response", "").strip()
        is_formula = _is_formula_task(task)

        return OCRResponse(
            text=text,
            is_formula=is_formula,
            formula_latex=text if is_formula else None,
            raw_output=text,
        )


# ---------------------------------------------------------------------------
# vLLM Backend
# ---------------------------------------------------------------------------


@dataclass
class VLLMBackend:
    """Call local vLLM service (OpenAI-compatible API)."""

    base_url: str = "http://localhost:8000"
    model: str = "zai-org/GLM-OCR"

    def is_available(self) -> bool:
        """Check if vLLM server is running."""
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        """Run OCR via vLLM OpenAI-compatible API."""
        img_b64 = _encode_image_base64(image)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                        {"type": "text", "text": task},
                    ],
                },
            ],
            "max_tokens": 8192,
        }

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/chat/completions", json=payload,
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"vLLM request failed: HTTP {resp.status_code} - {resp.text}"
            )

        body = resp.json()
        text = body["choices"][0]["message"]["content"].strip()
        is_formula = _is_formula_task(task)

        return OCRResponse(
            text=text,
            is_formula=is_formula,
            formula_latex=text if is_formula else None,
            raw_output=text,
        )


# ---------------------------------------------------------------------------
# Zhipu API Backend
# ---------------------------------------------------------------------------

_ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


@dataclass
class ZhipuAPIBackend:
    """Call Zhipu BigModel cloud API for GLM-OCR inference."""

    api_key: str
    api_url: str = _ZHIPU_API_URL

    def is_available(self) -> bool:
        """Available if API key is non-empty."""
        return bool(self.api_key)

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        """Run OCR via Zhipu BigModel API."""
        img_b64 = _encode_image_base64(image)

        payload = {
            "model": "glm-4v-flash",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"{task} Return JSON with keys: text, confidence (0-1), "
                                "is_formula (bool). If formula, include formula_latex."
                            ),
                        },
                    ],
                },
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(self.api_url, json=payload, headers=headers)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Zhipu API request failed: HTTP {resp.status_code} - {resp.text}"
            )

        body = resp.json()
        content_str = body["choices"][0]["message"]["content"]

        try:
            data = json.loads(content_str)
            text = str(data.get("text", content_str))
            is_formula = bool(data.get("is_formula", False))
            formula_latex = str(data["formula_latex"]) if data.get("formula_latex") else None
        except (json.JSONDecodeError, TypeError):
            text = content_str.strip()
            is_formula = _is_formula_task(task)
            formula_latex = text if is_formula else None

        return OCRResponse(
            text=text,
            is_formula=is_formula,
            formula_latex=formula_latex,
            raw_output=content_str,
        )


# ---------------------------------------------------------------------------
# Transformers Backend
# ---------------------------------------------------------------------------


@dataclass
class TransformersBackend:
    """In-process HuggingFace Transformers inference for GLM-OCR."""

    model_id: str = "zai-org/GLM-OCR"
    _processor: Any = field(default=None, repr=False)
    _model: Any = field(default=None, repr=False)

    def is_available(self) -> bool:
        """Check if torch and transformers are importable."""
        try:
            import torch  # noqa: F401 # type: ignore[import-not-found]
            import transformers  # noqa: F401 # type: ignore[import-not-found]
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> None:
        """Lazy-load model and processor on first use."""
        if self._model is not None:
            return

        try:
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Transformers backend requires 'transformers' and 'torch'. "
                "Install with: pip install transformers torch"
            ) from exc

        logger.info("Loading GLM-OCR model: %s", self.model_id)
        self._processor = AutoProcessor.from_pretrained(self.model_id)  # type: ignore[no-untyped-call]
        self._model = AutoModelForImageTextToText.from_pretrained(
            self.model_id, torch_dtype="auto", device_map="auto",
        )
        logger.info("GLM-OCR model loaded successfully")

    def recognize(self, image: np.ndarray, task: str) -> OCRResponse:
        """Run OCR via Transformers in-process inference."""
        from PIL import Image as PILImage

        self._ensure_loaded()
        processor = self._processor
        model = self._model

        pil_image = PILImage.fromarray(image)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_image},
                    {"type": "text", "text": task},
                ],
            },
        ]

        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs.pop("token_type_ids", None)

        # Move inputs to model device
        device = model.device
        inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

        generated_ids = model.generate(**inputs, max_new_tokens=8192)

        # Decode only newly generated tokens
        input_len = inputs["input_ids"].shape[1]
        text = processor.decode(
            generated_ids[0][input_len:], skip_special_tokens=True,
        ).strip()

        is_formula = _is_formula_task(task)

        return OCRResponse(
            text=text,
            is_formula=is_formula,
            formula_latex=text if is_formula else None,
            raw_output=text,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_ocr_backend(
    device: str,
    *,
    api_key: str | None = None,
    ollama_url: str | None = None,
    vllm_url: str | None = None,
    model_id: str | None = None,
) -> OCRBackend:
    """Create an OCR backend based on the device setting.

    Args:
        device: One of "auto", "transformers", "ollama", "vllm", "api".
        api_key: Required for "api" device.
        ollama_url: Custom Ollama URL (default localhost:11434).
        vllm_url: Custom vLLM URL (default localhost:8000).
        model_id: Custom model ID for Transformers/vLLM.

    Returns:
        An OCRBackend instance.

    Raises:
        ValueError: For invalid device or missing api_key.
        RuntimeError: For "auto" when no backend is available.
    """
    if device == "ollama":
        return OllamaBackend(
            base_url=ollama_url or "http://localhost:11434",
            model=model_id or "glm-ocr",
        )

    if device == "vllm":
        return VLLMBackend(
            base_url=vllm_url or "http://localhost:8000",
            model=model_id or "zai-org/GLM-OCR",
        )

    if device == "transformers":
        return TransformersBackend(model_id=model_id or "zai-org/GLM-OCR")

    if device == "api":
        if not api_key:
            raise ValueError(
                "API key is required for 'api' device. "
                "Set ZHIPU_API_KEY environment variable or pass --api-key."
            )
        return ZhipuAPIBackend(api_key=api_key)

    # cpu/gpu are layout-level concepts; for OCR they map to Transformers
    if device in ("cpu", "gpu"):
        return TransformersBackend(model_id=model_id or "zai-org/GLM-OCR")

    if device == "auto":
        # Priority: vLLM → Ollama → Transformers(GPU) → Transformers(CPU)
        vllm = VLLMBackend(base_url=vllm_url or "http://localhost:8000")
        if vllm.is_available():
            logger.info("Auto-detected vLLM backend")
            return vllm

        ollama = OllamaBackend(base_url=ollama_url or "http://localhost:11434")
        if ollama.is_available():
            logger.info("Auto-detected Ollama backend")
            return ollama

        transformers = TransformersBackend(model_id=model_id or "zai-org/GLM-OCR")
        if transformers.is_available():
            logger.info("Auto-detected Transformers backend")
            return transformers

        raise RuntimeError(
            "No OCR backend available. Install one of:\n"
            "  - Ollama: ollama pull glm-ocr\n"
            "  - Transformers: pip install transformers torch\n"
            "  - vLLM: pip install vllm && vllm serve zai-org/GLM-OCR\n"
            "  - API: set ZHIPU_API_KEY environment variable"
        )

    raise ValueError(
        f"Invalid device '{device}'. "
        "Must be one of: auto, transformers, ollama, vllm, api, cpu, gpu"
    )
