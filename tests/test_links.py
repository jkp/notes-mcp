"""Tests for wiki link parsing and backlink scanning."""

import shutil
from pathlib import Path

import pytest

from notes_mcp.links import get_backlinks, get_outlinks, parse_outlinks, resolve_link


class TestParseOutlinks:
    def test_extracts_simple_links(self) -> None:
        content = "Check [[Note A]] and [[Note B]] for details."
        links = parse_outlinks(content)
        assert links == ["Note A", "Note B"]

    def test_handles_display_text(self) -> None:
        content = "See [[Target Note|display text]] for more."
        links = parse_outlinks(content)
        assert links == ["Target Note"]

    def test_no_links_returns_empty(self) -> None:
        content = "No wiki links here."
        assert parse_outlinks(content) == []

    def test_multiple_links_same_line(self) -> None:
        content = "[[A]] and [[B]] and [[C]]"
        assert parse_outlinks(content) == ["A", "B", "C"]


class TestResolveLink:
    def test_exact_stem_match(self, vault: Path) -> None:
        result = resolve_link(vault, "css-architecture")
        assert result == "Resources/css-architecture.md"

    def test_case_insensitive_match(self, vault: Path) -> None:
        result = resolve_link(vault, "CSS-Architecture")
        assert result is not None
        assert "css-architecture" in result.lower()

    def test_unresolved_returns_none(self, vault: Path) -> None:
        result = resolve_link(vault, "nonexistent-note")
        assert result is None


class TestGetOutlinks:
    def test_resolves_outlinks(self, vault: Path) -> None:
        results = get_outlinks(vault, "Projects/web-redesign.md")
        titles = [r.title for r in results]
        assert "CSS Architecture" in titles
        assert "Design System" in titles

    def test_unresolved_links_marked(self, vault: Path) -> None:
        # Create a note with an unresolvable link
        (vault / "test-broken.md").write_text(
            "---\ntitle: Test\n---\nSee [[Nonexistent Note]].\n"
        )
        results = get_outlinks(vault, "test-broken.md")
        assert len(results) == 1
        assert results[0].path == ""
        assert results[0].snippet == "(unresolved)"

    def test_missing_note_returns_empty(self, vault: Path) -> None:
        results = get_outlinks(vault, "nonexistent.md")
        assert results == []


@pytest.fixture
def rg_bin() -> str:
    rg = shutil.which("rg")
    if rg is None:
        pytest.skip("ripgrep not installed")
    return rg


class TestGetBacklinks:
    async def test_finds_backlinks_by_stem(self, vault: Path, rg_bin: str) -> None:
        results = await get_backlinks(vault, rg_bin, "Resources/css-architecture.md")
        paths = [r.path for r in results]
        assert any("web-redesign" in p for p in paths)

    async def test_finds_backlinks_by_title(self, vault: Path, rg_bin: str) -> None:
        results = await get_backlinks(vault, rg_bin, "Resources/design-system.md")
        paths = [r.path for r in results]
        assert any("web-redesign" in p for p in paths)

    async def test_excludes_self(self, vault: Path, rg_bin: str) -> None:
        results = await get_backlinks(vault, rg_bin, "Resources/css-architecture.md")
        paths = [r.path for r in results]
        assert "Resources/css-architecture.md" not in paths

    async def test_no_backlinks_returns_empty(self, vault: Path, rg_bin: str) -> None:
        results = await get_backlinks(vault, rg_bin, "Areas/health.md")
        assert results == []
