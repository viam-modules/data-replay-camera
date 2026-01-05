# tests/test_data_replay.py

import os
import asyncio
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src/models"))
from data_replay import DataReplay

from viam.proto.app.robot import ComponentConfig
from google.protobuf.struct_pb2 import Struct

import logging
logger = logging.getLogger(__name__)



# ----------------------------
# Helper functions for creating test configs
# ----------------------------
def make_config(name: str = "test-camera", **attrs) -> ComponentConfig:
    """Helper to create a ComponentConfig with given attributes."""
    cfg = ComponentConfig(name=name)
    if attrs:
        struct = Struct()
        for key, val in attrs.items():
            if isinstance(val, str):
                struct[key] = val
            elif isinstance(val, list):
                struct[key] = val
            else:
                struct[key] = val
        cfg.attributes.CopyFrom(struct)
    return cfg


# ----------------------------
# Shared fixture for LOCAL tests
# ----------------------------
@pytest.fixture
def load_dotenv_if_present():
    """
    Local-only helper: load .env from repo root if it exists.
    Does NOT print secrets.
    """
    dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    if dotenv_path.exists():
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=dotenv_path, override=False)


class TestEnvCredentialsUnit:
    """
    Unit tests: deterministic checks for env var parsing.
    Does NOT depend on your real .env.
    """

    @pytest.mark.parametrize(
        "api_key, api_key_id, should_raise",
        [
            ("abc", "id", False),
            ("  abc  ", "  id  ", False),
            ("", "id", True),
            ("abc", "", True),
            ("   ", "id", True),
            ("abc", "   ", True),
            (None, "id", True),
            ("abc", None, True),
            (None, None, True),
        ],
    )
    def test_get_viam_credentials_from_env(self, monkeypatch, api_key, api_key_id, should_raise):
        """Test that credentials are properly read from environment variables."""
        monkeypatch.delenv("VIAM_API_KEY", raising=False)
        monkeypatch.delenv("VIAM_API_KEY_ID", raising=False)

        if api_key is not None:
            monkeypatch.setenv("VIAM_API_KEY", api_key)
        if api_key_id is not None:
            monkeypatch.setenv("VIAM_API_KEY_ID", api_key_id)

        dr = DataReplay("test")
        if should_raise:
            with pytest.raises(ValueError, match="VIAM_API_KEY and VIAM_API_KEY_ID"):
                dr._get_viam_credentials()
        else:
            k, kid = dr._get_viam_credentials()
            assert k == api_key.strip()
            assert kid == api_key_id.strip()

    def test_config_credentials_override_env(self, monkeypatch):
        """Test that config-provided credentials take precedence over env vars."""
        # Set env vars
        monkeypatch.setenv("VIAM_API_KEY", "env_key")
        monkeypatch.setenv("VIAM_API_KEY_ID", "env_key_id")

        # Create instance with config credentials
        dr = DataReplay("test")
        dr.api_key = "config_key"
        dr.api_key_id = "config_key_id"

        k, kid = dr._get_viam_credentials()
        assert k == "config_key"
        assert kid == "config_key_id"

    def test_partial_config_credentials_falls_back_to_env(self, monkeypatch):
        """Test that both config credentials must be set to override env vars."""
        monkeypatch.setenv("VIAM_API_KEY", "env_key")
        monkeypatch.setenv("VIAM_API_KEY_ID", "env_key_id")

        # Only api_key set (no api_key_id)
        dr = DataReplay("test")
        dr.api_key = "config_key"
        dr.api_key_id = ""

        k, kid = dr._get_viam_credentials()
        assert k == "env_key"
        assert kid == "env_key_id"

        # Only api_key_id set (no api_key)
        dr2 = DataReplay("test")
        dr2.api_key = ""
        dr2.api_key_id = "config_key_id"

        k, kid = dr2._get_viam_credentials()
        assert k == "env_key"
        assert kid == "env_key_id"


class TestConfigValidation:
    """Tests for configuration attribute validation."""

    def test_validate_api_key_valid_string(self):
        """Test that api_key accepts valid strings."""
        config = make_config(api_key="test_key")
        DataReplay.validate_config(config)

    def test_validate_api_key_invalid_type(self):
        """Test that api_key rejects non-string types."""
        config = make_config(api_key=12345)
        with pytest.raises(TypeError, match="'api_key' must be a string"):
            DataReplay.validate_config(config)

    def test_validate_api_key_id_valid_string(self):
        """Test that api_key_id accepts valid strings."""
        config = make_config(api_key_id="test_key_id")
        DataReplay.validate_config(config)

    def test_validate_api_key_id_invalid_type(self):
        """Test that api_key_id rejects non-string types."""
        config = make_config(api_key_id=12345)
        with pytest.raises(TypeError, match="'api_key_id' must be a string"):
            DataReplay.validate_config(config)

    def test_validate_both_api_keys(self):
        """Test that both api_key and api_key_id can be provided together."""
        config = make_config(api_key="test_key", api_key_id="test_key_id")
        DataReplay.validate_config(config)


class TestReconfiguration:
    """Tests for component reconfiguration."""

    def test_reconfigure_api_key(self):
        """Test that api_key is properly reconfigured."""
        config = make_config(api_key="new_key")
        dr = DataReplay("test")
        dr.reconfigure(config, {})
        assert dr.api_key == "new_key"

    def test_reconfigure_api_key_id(self):
        """Test that api_key_id is properly reconfigured."""
        config = make_config(api_key_id="new_key_id")
        dr = DataReplay("test")
        dr.reconfigure(config, {})
        assert dr.api_key_id == "new_key_id"

    def test_reconfigure_both_api_keys(self):
        """Test that both api_key and api_key_id are properly reconfigured."""
        config = make_config(api_key="new_key", api_key_id="new_key_id")
        dr = DataReplay("test")
        dr.reconfigure(config, {})
        assert dr.api_key == "new_key"
        assert dr.api_key_id == "new_key_id"

    def test_reconfigure_without_api_keys(self):
        """Test that api keys default to empty strings when not provided."""
        config = make_config(dataset_id="test_dataset")
        dr = DataReplay("test")
        dr.reconfigure(config, {})
        assert dr.api_key == ""
        assert dr.api_key_id == ""

    def test_reconfigure_resets_previous_values(self):
        """Test that reconfiguration properly resets previous api_key values."""
        dr = DataReplay("test")
        dr.api_key = "old_key"
        dr.api_key_id = "old_key_id"

        config = make_config()
        dr.reconfigure(config, {})
        assert dr.api_key == ""
        assert dr.api_key_id == ""


class TestLocalEnv:
    """
    Local-only smoke tests: verify your local machine/.env is wired correctly.
    """

    @pytest.mark.local
    def test_local_env_or_dotenv_has_viam_credentials(self, load_dotenv_if_present):
        # No network: just asserts the env vars exist (and are non-empty after strip)
        dr = DataReplay("test")
        dr._get_viam_credentials()


class TestViamDatasetReadLocal:
    """
    Local-only integration test:
    Proves your key can read binary data IDs from the dataset you specify.
    """

    @pytest.mark.local
    @pytest.mark.asyncio
    async def test_can_list_binary_ids_from_dataset(self, load_dotenv_if_present):
        dataset_id = (os.getenv("VIAM_TEST_DATASET_ID") or "").strip()
        assert dataset_id, "Set VIAM_TEST_DATASET_ID in .env (repo root) to a dataset you can read"

        # Optional tags/labels (comma-separated)
        tags_raw = (os.getenv("VIAM_TEST_TAGS") or "").strip()
        labels_raw = (os.getenv("VIAM_TEST_LABELS") or "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        labels = [l.strip() for l in labels_raw.split(",") if l.strip()] if labels_raw else []

        dr = DataReplay("test")
        dr.dataset_id = dataset_id
        dr.tags = tags
        dr.labels = labels

        async def _run():
            await dr._ensure_connected()
            ids = await dr.get_binary_ids(dataset_id, tags, labels)
            logger.info("Fetched %d binary items", len(ids))

            assert len(ids) > 0, (
                f"Connected OK but got 0 items for dataset_id={dataset_id}. "
                f"Try removing VIAM_TEST_TAGS/VIAM_TEST_LABELS or confirm dataset has data."
            )

            first = ids[0]
            bid = getattr(getattr(first, "metadata", None), "binary_data_id", None)
            assert bid, "Got items but metadata.binary_data_id missing (unexpected response shape)"

        await asyncio.wait_for(_run(), timeout=45)
