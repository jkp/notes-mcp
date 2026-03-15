"""Wiki link parsing and backlink scanning."""

import asyncio
import json
import re
from pathlib import Path

import structlog

from notes_mcp.frontmatter import parse_frontmatter
from notes_mcp.models import LinkInfo

logger = structlog.get_logger()

# Matches [[Target]] and [[Target|Display Text]]
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def parse_outlinks(content: str) -> list[str]:
    """Extract all wiki link targets from note content."""
    return WIKI_LINK_RE.findall(content)


def resolve_link(vault: Path, link_text: str) -> str | None:
    """Resolve a wiki link target to a relative file path.

    Tries in order:
    1. Direct relative path (with .md appended if needed)
    2. Exact filename stem match (case-sensitive)
    3. Case-insensitive filename match
    4. None if not found
    """
    # 0. Direct path match (handles path-style links like "folder/note name")
    if "/" in link_text:
        direct = vault / link_text
        if direct.is_file():
            return link_text
        direct_md = vault / f"{link_text}.md"
        if direct_md.is_file():
            return f"{link_text}.md"

    # Search all .md files recursively
    candidates = list(vault.rglob("*.md"))

    # 1. Exact stem match
    for f in candidates:
        if f.stem == link_text:
            return str(f.relative_to(vault))

    # 2. Case-insensitive stem match
    lower = link_text.lower()
    for f in candidates:
        if f.stem.lower() == lower:
            return str(f.relative_to(vault))

    return None


def get_outlinks(vault: Path, rel_path: str) -> list[LinkInfo]:
    """Parse wiki links from a note and resolve them to files."""
    full = (vault / rel_path).resolve()
    if not full.is_file():
        return []

    content = full.read_text(encoding="utf-8")
    targets = parse_outlinks(content)

    results: list[LinkInfo] = []
    seen: set[str] = set()

    for target in targets:
        if target in seen:
            continue
        seen.add(target)

        resolved = resolve_link(vault, target)
        if resolved is None:
            results.append(LinkInfo(path="", title=target, snippet="(unresolved)"))
            continue

        # Read the linked note for title and snippet
        linked_path = vault / resolved
        try:
            linked_content = linked_path.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(linked_content)
            title = fm.title or linked_path.stem
            snippet = body.strip()[:200] if body.strip() else None
        except Exception:
            title = target
            snippet = None

        results.append(LinkInfo(path=resolved, title=title, snippet=snippet))

    return results


async def get_backlinks(
    vault: Path, rg_bin: str, rel_path: str
) -> list[LinkInfo]:
    """Find all notes that link TO a given note via wiki links.

    Uses ripgrep to search the entire vault for [[target]] references.
    """
    note_path = vault / rel_path
    if not note_path.is_file():
        return []

    note_stem = Path(rel_path).stem

    # Also check frontmatter title
    content = note_path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    title = fm.title

    # Build search targets
    targets = {re.escape(note_stem)}
    if title and title != note_stem:
        targets.add(re.escape(title))

    pattern = r"\[\[(" + "|".join(targets) + r")(\|[^\]]+)?\]\]"

    cmd = [
        rg_bin,
        "--json",
        "--glob", "*.md",
        "-i",
        pattern,
        str(vault),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError:
        logger.error("backlinks.rg_not_found", bin=rg_bin)
        return []

    if not stdout:
        return []

    # Parse results, deduplicate by file, exclude self
    seen_files: set[str] = set()
    results: list[LinkInfo] = []
    self_resolved = str(note_path.resolve())

    for line in stdout.decode("utf-8", errors="replace").splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("type") != "match":
            continue

        match_path = data["data"]["path"]["text"]
        if Path(match_path).resolve() == Path(self_resolved):
            continue

        if match_path in seen_files:
            continue
        seen_files.add(match_path)

        try:
            file_rel = str(Path(match_path).relative_to(vault))
        except ValueError:
            continue

        # Read the linking note for title
        try:
            linking_content = Path(match_path).read_text(encoding="utf-8")
            linking_fm, linking_body = parse_frontmatter(linking_content)
            linking_title = linking_fm.title or Path(match_path).stem
            snippet = data["data"]["lines"]["text"].strip()[:200]
        except Exception:
            linking_title = Path(match_path).stem
            snippet = None

        results.append(LinkInfo(path=file_rel, title=linking_title, snippet=snippet))

    return results
