"""Tests for vault filesystem operations."""

from pathlib import Path

import pytest

from notes_mcp.vault import PathSecurityError, list_notes, move_note, read_note, write_note


class TestReadNote:
    def test_reads_existing_note(self, vault: Path) -> None:
        note = read_note(vault, "Projects/web-redesign.md")
        assert note is not None
        assert note.title == "Web Redesign"
        assert note.frontmatter.para == "projects"
        assert "web" in note.frontmatter.tags
        assert "Redesigning" in note.content

    def test_returns_none_for_missing(self, vault: Path) -> None:
        note = read_note(vault, "Projects/nonexistent.md")
        assert note is None

    def test_rejects_path_traversal(self, vault: Path) -> None:
        with pytest.raises(PathSecurityError):
            read_note(vault, "../../../etc/passwd")

    def test_uses_stem_as_title_fallback(self, vault: Path) -> None:
        # Create a note without a title in frontmatter
        (vault / "no-title.md").write_text("---\npara: resources\n---\nContent.\n")
        note = read_note(vault, "no-title.md")
        assert note is not None
        assert note.title == "no-title"


class TestWriteNote:
    def test_creates_new_note(self, vault: Path) -> None:
        content = "---\ntitle: New Note\n---\nHello world.\n"
        note = write_note(vault, "Projects/new-note.md", content)
        assert note.title == "New Note"
        assert note.frontmatter.updated is not None

        # Verify file was written
        assert (vault / "Projects" / "new-note.md").is_file()

    def test_creates_parent_directories(self, vault: Path) -> None:
        content = "---\ntitle: Deep Note\n---\nNested.\n"
        write_note(vault, "Projects/sub/deep/note.md", content)
        assert (vault / "Projects" / "sub" / "deep" / "note.md").is_file()

    def test_auto_sets_updated(self, vault: Path) -> None:
        content = "---\ntitle: Test\n---\nBody.\n"
        note = write_note(vault, "test.md", content)
        assert note.frontmatter.updated is not None

    def test_overwrites_existing(self, vault: Path) -> None:
        content = "---\ntitle: Updated\n---\nNew content.\n"
        note = write_note(vault, "Projects/web-redesign.md", content)
        assert note.title == "Updated"
        assert "New content" in note.content


class TestListNotes:
    def test_lists_notes_in_directory(self, vault: Path) -> None:
        entries = list_notes(vault, "Resources")
        assert len(entries) == 3
        titles = {e.title for e in entries}
        assert "CSS Architecture" in titles
        assert "Design System" in titles
        assert "Python Async Patterns" in titles

    def test_lists_with_metadata(self, vault: Path) -> None:
        entries = list_notes(vault, "Projects")
        assert len(entries) == 1
        entry = entries[0]
        assert entry.title == "Web Redesign"
        assert entry.para == "projects"
        assert "web" in entry.tags

    def test_empty_directory(self, vault: Path) -> None:
        (vault / "Empty").mkdir()
        entries = list_notes(vault, "Empty")
        assert entries == []

    def test_nonexistent_directory(self, vault: Path) -> None:
        entries = list_notes(vault, "Nonexistent")
        assert entries == []


class TestMoveNote:
    def test_moves_note(self, vault: Path) -> None:
        result = move_note(vault, "Areas/health.md", "Archive/health.md")
        assert result == "Archive/health.md"
        assert not (vault / "Areas" / "health.md").exists()
        assert (vault / "Archive" / "health.md").is_file()

    def test_creates_target_directory(self, vault: Path) -> None:
        move_note(vault, "Areas/health.md", "Archive/2024/health.md")
        assert (vault / "Archive" / "2024" / "health.md").is_file()

    def test_raises_for_missing_source(self, vault: Path) -> None:
        with pytest.raises(FileNotFoundError):
            move_note(vault, "nonexistent.md", "Archive/nonexistent.md")
