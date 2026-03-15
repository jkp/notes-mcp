"""Ripgrep-based full-text search across the Markdown vault."""

import asyncio
import json
from collections import defaultdict
from pathlib import Path

import structlog

from notes_mcp.models import SearchHit

logger = structlog.get_logger()


class RipgrepSearcher:
    """Async wrapper around ripgrep for searching Markdown files."""

    def __init__(self, bin_path: str, vault_path: Path) -> None:
        self.bin = bin_path
        self.vault = vault_path

    async def search(
        self,
        query: str,
        path: str | None = None,
        limit: int = 20,
    ) -> list[SearchHit]:
        """Search for a query string across .md files.

        Args:
            query: Search text (regex supported by ripgrep)
            path: Optional subdirectory to scope the search
            limit: Maximum results to return

        Returns:
            List of SearchHit sorted by match count (descending).
        """
        search_path = self.vault
        if path:
            search_path = (self.vault / path).resolve()
            if not str(search_path).startswith(str(self.vault.resolve())):
                return []

        cmd = [
            self.bin,
            "--json",
            "--smart-case",
            "--glob", "*.md",
            "--max-filesize", "1M",
            "--max-count", "5",
            query,
            str(search_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
        except FileNotFoundError:
            logger.error("search.rg_not_found", bin=self.bin)
            return []

        if not stdout:
            return []

        # Parse JSON lines output and group by file
        file_matches: dict[str, list[dict[str, object]]] = defaultdict(list)
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "match":
                continue
            match_data = data["data"]
            file_path = match_data["path"]["text"]
            file_matches[file_path].append(match_data)

        # Build SearchHit results
        results: list[SearchHit] = []
        for file_path, matches in file_matches.items():
            try:
                rel_path = str(Path(file_path).relative_to(self.vault))
            except ValueError:
                continue

            first = matches[0]
            snippet = first["lines"]["text"].strip()
            line_number = first["line_number"]

            results.append(
                SearchHit(
                    path=rel_path,
                    line_number=line_number,
                    snippet=snippet[:200],
                    match_count=len(matches),
                )
            )

        # Sort by match count descending (simple relevance)
        results.sort(key=lambda h: h.match_count, reverse=True)
        return results[:limit]
