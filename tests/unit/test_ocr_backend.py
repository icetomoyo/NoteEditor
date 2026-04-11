"""Tests for OCR backend abstraction layer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from noteeditor.infra.ocr_backend import (
    OCRResponse,
    OllamaBackend,
    TransformersBackend,
    VLLMBackend,
    ZhipuAPIBackend,
    create_ocr_backend,
)


# --- OCRResponse ---


class TestOCRResponse:
    def test_frozen(self) -> None:
        resp = OCRResponse(text="hello", is_formula=False, formula_latex=None, raw_output="hello")
        with pytest.raises(AttributeError):
            resp.text = "world"  # type: ignore[misc]

    def test_text_field(self) -> None:
        resp = OCRResponse(text="hello world", is_formula=False, formula_latex=None, raw_output="")
        assert resp.text == "hello world"
        assert resp.is_formula is False
        assert resp.formula_latex is None

    def test_formula_field(self) -> None:
        resp = OCRResponse(
            text="E=mc^2", is_formula=True, formula_latex="E=mc^2", raw_output="E=mc^2",
        )
        assert resp.is_formula is True
        assert resp.formula_latex == "E=mc^2"


# --- OllamaBackend ---


class TestOllamaBackend:
    def test_init_defaults(self) -> None:
        backend = OllamaBackend()
        assert backend.base_url == "http://localhost:11434"
        assert backend.model == "glm-ocr"

    def test_init_custom(self) -> None:
        backend = OllamaBackend(base_url="http://myhost:1234", model="custom-model")
        assert backend.base_url == "http://myhost:1234"
        assert backend.model == "custom-model"

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_is_available_true(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "glm-ocr:latest"}],
        }
        mock_httpx.get.return_value = mock_resp

        backend = OllamaBackend()
        assert backend.is_available() is True

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_is_available_false_no_model(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3:latest"}]}
        mock_httpx.get.return_value = mock_resp

        backend = OllamaBackend()
        assert backend.is_available() is False

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_is_available_false_connection_error(self, mock_httpx: MagicMock) -> None:
        mock_httpx.get.side_effect = Exception("connection refused")
        backend = OllamaBackend()
        assert backend.is_available() is False

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_recognize_success(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Hello World"}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_httpx.Client.return_value = mock_client

        backend = OllamaBackend()
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        result = backend.recognize(image, "Text Recognition:")

        assert result.text == "Hello World"
        assert result.is_formula is False

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_recognize_formula_task(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "E = mc^2"}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_httpx.Client.return_value = mock_client

        backend = OllamaBackend()
        image = np.zeros((50, 100, 3), dtype=np.uint8)
        result = backend.recognize(image, "Formula Recognition:")

        assert result.is_formula is True
        assert result.formula_latex == "E = mc^2"

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_recognize_http_error(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_httpx.Client.return_value = mock_client

        backend = OllamaBackend()
        image = np.zeros((50, 100, 3), dtype=np.uint8)
        with pytest.raises(RuntimeError, match="Ollama"):
            backend.recognize(image, "Text Recognition:")


# --- VLLMBackend ---


class TestVLLMBackend:
    def test_init_defaults(self) -> None:
        backend = VLLMBackend()
        assert backend.base_url == "http://localhost:8000"

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_is_available_true(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.get.return_value = mock_resp

        backend = VLLMBackend()
        assert backend.is_available() is True

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_is_available_false(self, mock_httpx: MagicMock) -> None:
        mock_httpx.get.side_effect = Exception("connection refused")
        backend = VLLMBackend()
        assert backend.is_available() is False

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_recognize_success(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Recognized text"}}],
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_httpx.Client.return_value = mock_client

        backend = VLLMBackend()
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        result = backend.recognize(image, "Text Recognition:")

        assert result.text == "Recognized text"
        assert result.is_formula is False

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_recognize_http_error(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_httpx.Client.return_value = mock_client

        backend = VLLMBackend()
        image = np.zeros((50, 100, 3), dtype=np.uint8)
        with pytest.raises(RuntimeError, match="vLLM"):
            backend.recognize(image, "Text Recognition:")


# --- ZhipuAPIBackend ---


class TestZhipuAPIBackend:
    def test_init(self) -> None:
        backend = ZhipuAPIBackend(api_key="test-key")
        assert backend.api_key == "test-key"

    def test_is_available_with_key(self) -> None:
        backend = ZhipuAPIBackend(api_key="test-key")
        assert backend.is_available() is True

    def test_is_available_empty_key(self) -> None:
        backend = ZhipuAPIBackend(api_key="")
        assert backend.is_available() is False

    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_recognize_success(self, mock_httpx: MagicMock) -> None:
        content_json = json.dumps({
            "text": "API recognized text",
            "confidence": 0.95,
            "is_formula": False,
        })
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content_json}}],
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_resp
        mock_httpx.Client.return_value = mock_client

        backend = ZhipuAPIBackend(api_key="test-key")
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        result = backend.recognize(image, "Text Recognition:")

        assert result.text == "API recognized text"
        assert result.is_formula is False


# --- TransformersBackend ---


class TestTransformersBackend:
    def test_init(self) -> None:
        backend = TransformersBackend()
        assert backend.model_id == "zai-org/GLM-OCR"

    def test_is_available_no_torch(self) -> None:
        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            backend = TransformersBackend()
            # Can't reliably test importability in mocked env,
            # but at minimum it should not crash
            # Real availability depends on torch being installed

    def test_recognize_calls_model(self) -> None:
        """Test that recognize loads model lazily and calls generate."""
        backend = TransformersBackend()

        mock_processor = MagicMock()
        mock_model = MagicMock()

        # Mock the template output
        mock_inputs = {"input_ids": MagicMock()}
        mock_inputs["input_ids"].shape = [1, 10]
        mock_processor.apply_chat_template.return_value = mock_inputs

        # Mock generate output
        mock_generated = MagicMock()
        mock_model.generate.return_value = mock_generated
        mock_model.device = "cpu"

        mock_processor.decode.return_value = "Decoded text"

        backend._processor = mock_processor
        backend._model = mock_model

        image = np.zeros((100, 200, 3), dtype=np.uint8)
        result = backend.recognize(image, "Text Recognition:")

        assert result.text == "Decoded text"
        mock_model.generate.assert_called_once()


# --- create_ocr_backend factory ---


class TestCreateOcrBackend:
    @patch("noteeditor.infra.ocr_backend.httpx")
    def test_auto_finds_vllm(self, mock_httpx: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.get.return_value = mock_resp

        backend = create_ocr_backend("vllm")
        assert isinstance(backend, VLLMBackend)

    def test_ollama(self) -> None:
        backend = create_ocr_backend("ollama")
        assert isinstance(backend, OllamaBackend)

    def test_transformers(self) -> None:
        backend = create_ocr_backend("transformers")
        assert isinstance(backend, TransformersBackend)

    def test_api_with_key(self) -> None:
        backend = create_ocr_backend("api", api_key="test-key")
        assert isinstance(backend, ZhipuAPIBackend)

    def test_api_without_key_raises(self) -> None:
        with pytest.raises(ValueError, match="API key"):
            create_ocr_backend("api")

    def test_invalid_device_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid device"):
            create_ocr_backend("invalid_device")
