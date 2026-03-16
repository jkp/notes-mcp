"""Tests for browsing tools: list_directory, path_exists, get_metadata."""

import os
from pathlib import Path

import pytest

from notes_mcp.vault import (
    PathSecurityError,
    list_directory,
    path_exists,
)

# Re-use the vault fixture from conftest.py


@pytest.fixture
def vault_with_hidden(vault: Path) -> Path:
    """Extend vault fixture with hidden dirs and a symlink escape."""
    # Hidden directory (like .obsidian)
    obsidian = vault / ".obsidian"
    obsidian.mkdir()
    (obsidian / "config.json").write_text('{"theme": "dark"}')

    # Hidden file at root
    (vault / ".DS_Store").write_text("")

    # Symlink pointing outside vault
    outside = vault.parent / "outside-vault"
    outside.mkdir()
    (outside / "secret.md").write_text("secret data")
    (vault / "escape-link").symlink_to(outside)

    return vault


class TestListDirectory:
    """Functional tests for list_directory."""

    def test_root_returns_para_dirs(self, vault: Path) -> None:
        entries = list_directory(vault, "")
        names = [e.name for e in entries]
        for bucket in ["Projects", "Areas", "Resources", "Archive"]:
            assert bucket in names

    def test_root_dirs_before_files(self, vault: Path) -> None:
        # Add a root-level .md file
        (vault / "inbox.md").write_text("---\ntitle: Inbox\n---\nStuff\n")
        entries = list_directory(vault, "")
        types = [e.type for e in entries]
        # All directories come before all files
        dir_indices = [i for i, t in enumerate(types) if t == "directory"]
        file_indices = [i for i, t in enumerate(types) if t == "file"]
        if dir_indices and file_indices:
            assert max(dir_indices) < min(file_indices)

    def test_resources_returns_md_files(self, vault: Path) -> None:
        entries = list_directory(vault, "Resources")
        names = [e.name for e in entries]
        assert "css-architecture.md" in names
        assert "design-system.md" in names
        assert "python-async.md" in names
        assert len(entries) == 3

    def test_includes_metadata_by_default(self, vault: Path) -> None:
        entries = list_directory(vault, "Resources")
        file_entries = [e for e in entries if e.type == "file"]
        assert all(e.frontmatter is not None for e in file_entries)

    def test_exclude_metadata(self, vault: Path) -> None:
        entries = list_directory(vault, "Resources", include_metadata=False)
        file_entries = [e for e in entries if e.type == "file"]
        assert all(e.frontmatter is None for e in file_entries)

    def test_recursive_populates_children(self, vault: Path) -> None:
        entries = list_directory(vault, "", recursive=True)
        dir_entries = [e for e in entries if e.type == "directory"]
        # At least one directory should have children
        has_children = any(e.children for e in dir_entries)
        assert has_children

    def test_skips_hidden_dirs(self, vault_with_hidden: Path) -> None:
        entries = list_directory(vault_with_hidden, "")
        names = [e.name for e in entries]
        assert ".obsidian" not in names
        assert ".DS_Store" not in names

    def test_skips_hidden_in_recursive(self, vault_with_hidden: Path) -> None:
        entries = list_directory(vault_with_hidden, "", recursive=True)
        all_names = _collect_all_names(entries)
        assert ".obsidian" not in all_names
        assert ".DS_Store" not in all_names

    def test_nonexistent_dir_returns_empty(self, vault: Path) -> None:
        entries = list_directory(vault, "nonexistent")
        assert entries == []

    def test_max_depth_respected(self, vault: Path) -> None:
        # Create deeply nested structure
        deep = vault / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "note.md").write_text("---\ntitle: Deep\n---\n")

        entries = list_directory(vault, "", recursive=True, max_depth=2)
        # At depth 2 we should not see entries beyond 2 levels deep
        all_paths = _collect_all_paths(entries)
        assert not any(p.count("/") > 2 for p in all_paths)

    def test_alphabetical_within_type(self, vault: Path) -> None:
        entries = list_directory(vault, "Resources")
        names = [e.name for e in entries]
        assert names == sorted(names)


class TestPathExists:
    """Functional tests for path_exists."""

    def test_existing_file(self, vault: Path) -> None:
        exists, kind = path_exists(vault, "Resources/css-architecture.md")
        assert exists is True
        assert kind == "file"

    def test_existing_directory(self, vault: Path) -> None:
        exists, kind = path_exists(vault, "Resources")
        assert exists is True
        assert kind == "directory"

    def test_nonexistent(self, vault: Path) -> None:
        exists, kind = path_exists(vault, "nonexistent/file.md")
        assert exists is False
        assert kind is None

    def test_rejects_hidden_path(self, vault_with_hidden: Path) -> None:
        exists, kind = path_exists(vault_with_hidden, ".obsidian")
        assert exists is False
        assert kind is None


class TestPathSecurity:
    """Security tests for path traversal, symlink escape, and hidden dirs."""

    def test_list_directory_parent_traversal(self, vault: Path) -> None:
        with pytest.raises(PathSecurityError):
            list_directory(vault, "../")

    def test_list_directory_deep_traversal(self, vault: Path) -> None:
        with pytest.raises(PathSecurityError):
            list_directory(vault, "../../etc")

    def test_list_directory_absolute_path(self, vault: Path) -> None:
        with pytest.raises(PathSecurityError):
            list_directory(vault, "/etc/passwd")

    def test_path_exists_traversal(self, vault: Path) -> None:
        with pytest.raises(PathSecurityError):
            path_exists(vault, "../../../etc/passwd")

    def test_path_exists_symlink_escape(self, vault_with_hidden: Path) -> None:
        with pytest.raises(PathSecurityError):
            path_exists(vault_with_hidden, "escape-link/secret.md")

    def test_list_directory_hidden_dir_returns_empty(
        self, vault_with_hidden: Path
    ) -> None:
        entries = list_directory(vault_with_hidden, ".obsidian")
        assert entries == []

    def test_get_metadata_traversal(self, vault: Path) -> None:
        # get_metadata uses vault.read_note which calls _validate_path
        from notes_mcp.vault import read_note

        with pytest.raises(PathSecurityError):
            read_note(vault, "../../../etc/passwd")

    def test_error_messages_exclude_vault_root(self, vault: Path) -> None:
        vault_str = str(vault.resolve())
        with pytest.raises(PathSecurityError) as exc_info:
            list_directory(vault, "../")
        assert vault_str not in str(exc_info.value)


def _collect_all_names(entries: list) -> list[str]:
    """Recursively collect all names from directory entries."""
    names = []
    for e in entries:
        names.append(e.name)
        if e.children:
            names.extend(_collect_all_names(e.children))
    return names


def _collect_all_paths(entries: list) -> list[str]:
    """Recursively collect all paths from directory entries."""
    paths = []
    for e in entries:
        paths.append(e.path)
        if e.children:
            paths.extend(_collect_all_paths(e.children))
    return paths
