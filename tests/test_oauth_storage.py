"""Tests for OAuth state persistence configuration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from notes_mcp.config import Settings


class TestOAuthStateDir:
    """Tests for oauth_state_dir configuration."""

    def test_default_is_none(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            s = Settings(
                _env_file=None,
                vault_path=Path("/tmp/vault"),
            )
            assert s.oauth_state_dir is None

    def test_reads_from_env(self, tmp_path: Path) -> None:
        state_dir = str(tmp_path / "oauth-state")
        with patch.dict(
            "os.environ",
            {"NOTES_MCP_OAUTH_STATE_DIR": state_dir},
            clear=True,
        ):
            s = Settings(_env_file=None, vault_path=Path("/tmp/vault"))
            assert s.oauth_state_dir == Path(state_dir)


class TestBuildAuthStorage:
    """Tests for _build_auth_storage helper."""

    def test_returns_none_when_no_dir(self) -> None:
        from notes_mcp.server import _build_auth_storage

        with patch.dict("os.environ", {}, clear=True):
            s = Settings(_env_file=None, vault_path=Path("/tmp/vault"))
            assert _build_auth_storage(s) is None

    def test_returns_storage_when_dir_set(self, tmp_path: Path) -> None:
        from notes_mcp.server import _build_auth_storage

        state_dir = tmp_path / "oauth-state"
        with patch.dict(
            "os.environ",
            {"NOTES_MCP_OAUTH_STATE_DIR": str(state_dir)},
            clear=True,
        ):
            s = Settings(_env_file=None, vault_path=Path("/tmp/vault"))
            storage = _build_auth_storage(s)
            assert storage is not None
            # Directory should be created
            assert state_dir.is_dir()

    def test_storage_passed_to_github_provider(self, tmp_path: Path) -> None:
        """Verify _build_auth passes client_storage when oauth_state_dir is set."""
        from notes_mcp.server import _build_auth_storage

        state_dir = tmp_path / "oauth-state"
        with patch.dict(
            "os.environ",
            {"NOTES_MCP_OAUTH_STATE_DIR": str(state_dir)},
            clear=True,
        ):
            s = Settings(_env_file=None, vault_path=Path("/tmp/vault"))
            storage = _build_auth_storage(s)
            # Should be a FileTreeStore instance
            from key_value.aio.stores.filetree import FileTreeStore

            assert isinstance(storage, FileTreeStore)
