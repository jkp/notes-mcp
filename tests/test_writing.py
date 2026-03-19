"""Tests for note editing tools (edit_note, append_to_note)."""

import re
from pathlib import Path

import pytest

from notes_mcp.vault import read_note, write_note


class TestEditNote:
    def test_replaces_text_in_body(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        result = edit_note(vault, "Areas/health.md", "exercise log", "workout log")
        assert result.replacements == 1

        note = read_note(vault, "Areas/health.md")
        assert "workout log" in note.content
        assert "exercise log" not in note.content

    def test_errors_on_ambiguous_match(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        # Write a note with duplicate text
        write_note(
            vault,
            "test-dup.md",
            "---\ntitle: Dup\n---\nfoo bar\nfoo bar\n",
        )

        with pytest.raises(ValueError, match="ambiguous"):
            edit_note(vault, "test-dup.md", "foo bar", "baz")

    def test_replace_all(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        write_note(
            vault,
            "test-dup.md",
            "---\ntitle: Dup\n---\nfoo bar\nfoo bar\n",
        )

        result = edit_note(vault, "test-dup.md", "foo bar", "baz", replace_all=True)
        assert result.replacements == 2

        note = read_note(vault, "test-dup.md")
        assert "foo bar" not in note.content
        assert note.content.count("baz") == 2

    def test_errors_on_not_found(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        with pytest.raises(ValueError, match="not found"):
            edit_note(vault, "Areas/health.md", "nonexistent text", "replacement")

    def test_errors_on_missing_note(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        with pytest.raises(FileNotFoundError):
            edit_note(vault, "missing.md", "old", "new")

    def test_preserves_frontmatter(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        edit_note(vault, "Areas/health.md", "exercise log", "workout log")

        note = read_note(vault, "Areas/health.md")
        assert note.frontmatter.title == "Health Tracking"
        assert note.frontmatter.para == "areas"
        assert "health" in note.frontmatter.tags

    def test_updates_updated_field(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        edit_note(vault, "Areas/health.md", "exercise log", "workout log")

        note = read_note(vault, "Areas/health.md")
        assert note.frontmatter.updated is not None

    def test_multiline_replacement(self, vault: Path) -> None:
        from notes_mcp.vault import edit_note

        write_note(
            vault,
            "test-multi.md",
            "---\ntitle: Multi\n---\nline one\nline two\nline three\n",
        )

        edit_note(vault, "test-multi.md", "line one\nline two", "replaced lines")

        note = read_note(vault, "test-multi.md")
        assert "replaced lines" in note.content
        assert "line one" not in note.content
        assert "line three" in note.content


class TestAppendToNote:
    def test_appends_to_end(self, vault: Path) -> None:
        from notes_mcp.vault import append_to_note

        append_to_note(vault, "Areas/health.md", "- New entry")

        note = read_note(vault, "Areas/health.md")
        assert note.content.rstrip().endswith("- New entry")

    def test_appends_under_heading(self, vault: Path) -> None:
        from notes_mcp.vault import append_to_note

        append_to_note(vault, "Areas/health.md", "- New entry", heading="## Notes")

        note = read_note(vault, "Areas/health.md")
        # Content should be after "## Notes" section content
        lines = note.content.split("\n")
        notes_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Notes")
        # Find "- New entry" — should be after the Notes heading
        entry_idx = next(i for i, l in enumerate(lines) if "- New entry" in l)
        assert entry_idx > notes_idx

    def test_appends_before_next_heading(self, vault: Path) -> None:
        from notes_mcp.vault import append_to_note

        write_note(
            vault,
            "test-sections.md",
            "---\ntitle: Sections\n---\n## First\nContent 1\n\n## Second\nContent 2\n",
        )

        append_to_note(vault, "test-sections.md", "- Added item", heading="## First")

        note = read_note(vault, "test-sections.md")
        lines = note.content.split("\n")
        added_idx = next(i for i, l in enumerate(lines) if "- Added item" in l)
        second_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Second")
        assert added_idx < second_idx

    def test_creates_heading_if_missing(self, vault: Path) -> None:
        from notes_mcp.vault import append_to_note

        append_to_note(vault, "Areas/health.md", "- Log entry", heading="## Log")

        note = read_note(vault, "Areas/health.md")
        assert "## Log" in note.content
        assert "- Log entry" in note.content

    def test_errors_on_missing_note(self, vault: Path) -> None:
        from notes_mcp.vault import append_to_note

        with pytest.raises(FileNotFoundError):
            append_to_note(vault, "missing.md", "content")

    def test_updates_updated_field(self, vault: Path) -> None:
        from notes_mcp.vault import append_to_note

        append_to_note(vault, "Areas/health.md", "- New entry")

        note = read_note(vault, "Areas/health.md")
        assert note.frontmatter.updated is not None

    def test_respects_heading_hierarchy(self, vault: Path) -> None:
        """Appending under ## should stop at the next ## or #, not ###."""
        from notes_mcp.vault import append_to_note

        write_note(
            vault,
            "test-hier.md",
            "---\ntitle: Hier\n---\n## Section\nContent\n\n### Sub\nSub content\n\n## Next\nMore\n",
        )

        append_to_note(vault, "test-hier.md", "- Appended", heading="## Section")

        note = read_note(vault, "test-hier.md")
        lines = note.content.split("\n")
        appended_idx = next(i for i, l in enumerate(lines) if "- Appended" in l)
        next_idx = next(i for i, l in enumerate(lines) if l.strip() == "## Next")
        # Appended should be after ### Sub content but before ## Next
        assert appended_idx < next_idx
