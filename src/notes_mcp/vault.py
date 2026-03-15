"""Filesystem operations on the Markdown vault."""

from datetime import date
from pathlib import Path

import structlog

from notes_mcp.frontmatter import parse_frontmatter, serialize_frontmatter
from notes_mcp.models import Note, NoteListEntry

logger = structlog.get_logger()


class PathSecurityError(Exception):
    """Raised when a path escapes the vault root."""


def _validate_path(vault: Path, rel_path: str) -> Path:
    """Resolve a relative path and ensure it stays within the vault."""
    full = (vault / rel_path).resolve()
    if not str(full).startswith(str(vault.resolve())):
        raise PathSecurityError(f"Path escapes vault: {rel_path}")
    return full


def read_note(vault: Path, rel_path: str) -> Note | None:
    """Read a note file and parse its frontmatter.

    Returns None if the file doesn't exist.
    """
    full = _validate_path(vault, rel_path)
    if not full.is_file():
        return None

    content = full.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    title = fm.title or full.stem

    return Note(
        path=rel_path,
        title=title,
        frontmatter=fm,
        content=body,
    )


def write_note(vault: Path, rel_path: str, content: str) -> Note:
    """Create or update a note file.

    Automatically sets the `updated` field in frontmatter.
    """
    full = _validate_path(vault, rel_path)
    full.parent.mkdir(parents=True, exist_ok=True)

    # Parse and update the `updated` field
    fm, body = parse_frontmatter(content)
    fm.updated = date.today().isoformat()
    final_content = serialize_frontmatter(fm, body)

    full.write_text(final_content, encoding="utf-8")
    logger.info("vault.write", path=rel_path)

    title = fm.title or full.stem
    return Note(path=rel_path, title=title, frontmatter=fm, content=body)


def list_notes(vault: Path, rel_path: str = "") -> list[NoteListEntry]:
    """List .md files in a directory with their metadata.

    Non-recursive: only lists files directly in the given directory.
    """
    target = _validate_path(vault, rel_path) if rel_path else vault
    if not target.is_dir():
        return []

    entries = []
    for f in sorted(target.glob("*.md")):
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            rel = str(f.relative_to(vault))
            entries.append(
                NoteListEntry(
                    path=rel,
                    title=fm.title or f.stem,
                    para=fm.para,
                    tags=fm.tags,
                    updated=fm.updated,
                )
            )
        except Exception:
            logger.warning("vault.list.skip", path=str(f), exc_info=True)

    return entries


def move_note(vault: Path, from_path: str, to_path: str) -> str:
    """Move a note file within the vault.

    Creates target directories as needed. Returns the new relative path.
    """
    src = _validate_path(vault, from_path)
    dst = _validate_path(vault, to_path)

    if not src.is_file():
        msg = f"Source note not found: {from_path}"
        raise FileNotFoundError(msg)

    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    logger.info("vault.move", from_path=from_path, to_path=to_path)

    return to_path
