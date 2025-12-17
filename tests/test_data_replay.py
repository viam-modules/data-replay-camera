# tests/test_data_replay.py

import os
import asyncio
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src/models"))
from data_replay import DataReplay

import logging
logger = logging.getLogger(__name__)



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
    def test_get_viam_env_credentials(self, monkeypatch, api_key, api_key_id, should_raise):
        monkeypatch.delenv("VIAM_API_KEY", raising=False)
        monkeypatch.delenv("VIAM_API_KEY_ID", raising=False)

        if api_key is not None:
            monkeypatch.setenv("VIAM_API_KEY", api_key)
        if api_key_id is not None:
            monkeypatch.setenv("VIAM_API_KEY_ID", api_key_id)

        if should_raise:
            with pytest.raises(ValueError, match="VIAM_API_KEY and VIAM_API_KEY_ID"):
                DataReplay._get_viam_env_credentials()
        else:
            k, kid = DataReplay._get_viam_env_credentials()
            assert k == api_key.strip()
            assert kid == api_key_id.strip()


class TestLocalEnv:
    """
    Local-only smoke tests: verify your local machine/.env is wired correctly.
    """

    @pytest.mark.local
    def test_local_env_or_dotenv_has_viam_credentials(self, load_dotenv_if_present):
        # No network: just asserts the env vars exist (and are non-empty after strip)
        DataReplay._get_viam_env_credentials()


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
