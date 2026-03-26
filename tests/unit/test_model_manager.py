"""Tests for infra/model_manager.py - Model loading and verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from noteeditor.infra.model_manager import ModelManager


class TestModelManager:
    """Tests for ModelManager dataclass."""

    def test_create_model_manager(self) -> None:
        """ModelManager can be instantiated with defaults."""
        mgr = ModelManager(models_dir=Path("/tmp/models"))
        assert mgr.models_dir == Path("/tmp/models")
        assert mgr.device == "auto"

    def test_is_frozen(self) -> None:
        """ModelManager is immutable (frozen dataclass)."""
        mgr = ModelManager(models_dir=Path("/tmp/models"))
        with pytest.raises(AttributeError):
            mgr.device = "cpu"  # type: ignore[misc]

    def test_custom_device(self) -> None:
        """ModelManager accepts custom device setting."""
        mgr = ModelManager(models_dir=Path("/tmp/models"), device="cpu")
        assert mgr.device == "cpu"


class TestGetLayoutModel:
    """Tests for get_layout_model()."""

    def test_missing_model_raises_file_not_found(self, tmp_path: Path) -> None:
        """Missing model file raises FileNotFoundError with instructions."""
        mgr = ModelManager(models_dir=tmp_path, device="cpu")
        with pytest.raises(FileNotFoundError, match="Layout model not found"):
            mgr.get_layout_model()

    def test_missing_model_error_contains_download_url(self, tmp_path: Path) -> None:
        """Error message includes HuggingFace download URL."""
        mgr = ModelManager(models_dir=tmp_path, device="cpu")
        with pytest.raises(FileNotFoundError, match="huggingface"):
            mgr.get_layout_model()

    def test_missing_model_error_contains_target_path(self, tmp_path: Path) -> None:
        """Error message includes the expected model file path."""
        mgr = ModelManager(models_dir=tmp_path, device="cpu")
        with pytest.raises(FileNotFoundError, match="pp_doclayout_v3.onnx"):
            mgr.get_layout_model()

    def test_loads_existing_model(self, tmp_path: Path) -> None:
        """Existing model file creates an InferenceSession."""
        (tmp_path / "pp_doclayout_v3.onnx").write_bytes(b"fake onnx data")
        mgr = ModelManager(models_dir=tmp_path, device="cpu")

        with patch("noteeditor.infra.model_manager.ort.InferenceSession") as mock_cls:
            mock_session = MagicMock()
            mock_session.get_providers.return_value = ["CPUExecutionProvider"]
            mock_cls.return_value = mock_session

            result = mgr.get_layout_model()

        assert result is mock_session
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["providers"] == ["CPUExecutionProvider"]

    def test_load_failure_raises_runtime_error(self, tmp_path: Path) -> None:
        """ONNX load failure raises RuntimeError."""
        (tmp_path / "pp_doclayout_v3.onnx").write_bytes(b"invalid onnx")
        mgr = ModelManager(models_dir=tmp_path, device="cpu")

        with patch(
            "noteeditor.infra.model_manager.ort.InferenceSession",
            side_effect=Exception("corrupt model"),
        ), pytest.raises(RuntimeError, match="Failed to load"):
            mgr.get_layout_model()


class TestResolveProviders:
    """Tests for _resolve_providers()."""

    def test_cpu_device(self, tmp_path: Path) -> None:
        """device='cpu' returns CPUExecutionProvider only."""
        mgr = ModelManager(models_dir=tmp_path, device="cpu")
        providers = mgr._resolve_providers()
        assert providers == ["CPUExecutionProvider"]

    def test_gpu_device(self, tmp_path: Path) -> None:
        """device='gpu' returns CUDA with CPU fallback."""
        mgr = ModelManager(models_dir=tmp_path, device="gpu")
        providers = mgr._resolve_providers()
        assert providers[0] == "CUDAExecutionProvider"
        assert "CPUExecutionProvider" in providers

    def test_auto_device_with_cuda(self, tmp_path: Path) -> None:
        """device='auto' selects CUDA when available."""
        mgr = ModelManager(models_dir=tmp_path, device="auto")
        with patch(
            "noteeditor.infra.model_manager.ort.get_available_providers",
            return_value=["CUDAExecutionProvider", "CPUExecutionProvider"],
        ):
            providers = mgr._resolve_providers()
        assert providers[0] == "CUDAExecutionProvider"
        assert "CPUExecutionProvider" in providers

    def test_auto_device_without_cuda(self, tmp_path: Path) -> None:
        """device='auto' falls back to CPU when CUDA unavailable."""
        mgr = ModelManager(models_dir=tmp_path, device="auto")
        with patch(
            "noteeditor.infra.model_manager.ort.get_available_providers",
            return_value=["CPUExecutionProvider"],
        ):
            providers = mgr._resolve_providers()
        assert providers == ["CPUExecutionProvider"]

    def test_invalid_device_raises_value_error(self, tmp_path: Path) -> None:
        """Invalid device string raises ValueError."""
        mgr = ModelManager(models_dir=tmp_path, device="tpu")
        with pytest.raises(ValueError, match="Invalid device"):
            mgr._resolve_providers()
