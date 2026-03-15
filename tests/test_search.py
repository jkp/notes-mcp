"""Tests for ripgrep-based search."""

import shutil
from pathlib import Path

import pytest

from notes_mcp.search import RipgrepSearcher


@pytest.fixture
def rg_bin() -> str:
    """Find the ripgrep binary."""
    rg = shutil.which("rg")
    if rg is None:
        pytest.skip("ripgrep not installed")
    return rg


@pytest.fixture
def search(vault: Path, rg_bin: str) -> RipgrepSearcher:
    return RipgrepSearcher(bin_path=rg_bin, vault_path=vault)


class TestRipgrepSearcher:
    async def test_finds_matching_notes(self, search: RipgrepSearcher) -> None:
        results = await search.search("Redesign")
        assert len(results) >= 1
        paths = [r.path for r in results]
        assert any("web-redesign" in p for p in paths)

    async def test_returns_snippets(self, search: RipgrepSearcher) -> None:
        results = await search.search("exercise")
        assert len(results) >= 1
        assert any("exercise" in r.snippet.lower() for r in results)

    async def test_scoped_to_subdirectory(self, search: RipgrepSearcher) -> None:
        results = await search.search("architecture", path="Resources")
        paths = [r.path for r in results]
        assert all(p.startswith("Resources/") for p in paths)

    async def test_respects_limit(self, search: RipgrepSearcher) -> None:
        results = await search.search("title", limit=2)
        assert len(results) <= 2

    async def test_no_matches_returns_empty(self, search: RipgrepSearcher) -> None:
        results = await search.search("xyznonexistentterm123")
        assert results == []

    async def test_sorted_by_match_count(self, search: RipgrepSearcher) -> None:
        results = await search.search("web")
        if len(results) >= 2:
            assert results[0].match_count >= results[1].match_count
