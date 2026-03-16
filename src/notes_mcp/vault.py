"""Filesystem operations on the Markdown vault."""

from datetime import date
from pathlib import Path

import structlog

from notes_mcp.frontmatter import parse_frontmatter, serialize_frontmatter
from notes_mcp.models import DirectoryEntry, Note, NoteListEntry

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


def _is_hidden(name: str) -> bool:
    """Check if a file/directory name is hidden (starts with '.')."""
    return name.startswith(".")


def _has_hidden_component(rel_path: str) -> bool:
    """Check if any component of a relative path is hidden."""
    return any(_is_hidden(part) for part in Path(rel_path).parts)


def list_directory(
    vault: Path,
    rel_path: str = "",
    recursive: bool = False,
    include_metadata: bool = True,
    max_depth: int = 10,
) -> list[DirectoryEntry]:
    """List files and directories in a vault path.

    Returns sorted entries (directories first, then files, alphabetical).
    Skips hidden entries. Returns empty list for non-existent or hidden dirs.
    Raises PathSecurityError if path escapes vault.
    """
    # Validate path first (raises on traversal) before hidden check
    target = _validate_path(vault, rel_path) if rel_path else vault

    if rel_path and _has_hidden_component(rel_path):
        return []

    if not target.is_dir():
        return []

    return _list_dir_recursive(vault, target, recursive, include_metadata, max_depth, 0)


def _list_dir_recursive(
    vault: Path,
    target: Path,
    recursive: bool,
    include_metadata: bool,
    max_depth: int,
    current_depth: int,
) -> list[DirectoryEntry]:
    """Internal recursive directory listing."""
    dirs: list[DirectoryEntry] = []
    files: list[DirectoryEntry] = []

    for item in sorted(target.iterdir()):
        if _is_hidden(item.name):
            continue
        # Skip symlinks that escape the vault
        if item.is_symlink():
            try:
                resolved = item.resolve()
                if not str(resolved).startswith(str(vault.resolve())):
                    continue
            except OSError:
                continue

        rel = str(item.relative_to(vault))

        if item.is_dir():
            children = None
            if recursive and current_depth < max_depth:
                children = _list_dir_recursive(
                    vault, item, recursive, include_metadata, max_depth, current_depth + 1
                )
            dirs.append(
                DirectoryEntry(path=rel, name=item.name, type="directory", children=children)
            )
        elif item.is_file() and item.suffix == ".md":
            fm = None
            if include_metadata:
                try:
                    content = item.read_text(encoding="utf-8")
                    fm, _ = parse_frontmatter(content)
                except Exception:
                    logger.warning("vault.list_directory.skip", path=rel, exc_info=True)
            files.append(
                DirectoryEntry(path=rel, name=item.name, type="file", frontmatter=fm)
            )

    return dirs + files


def path_exists(vault: Path, rel_path: str) -> tuple[bool, str | None]:
    """Check if a path exists within the vault.

    Returns (exists, type) where type is 'file' or 'directory'.
    Raises PathSecurityError if path escapes vault.
    Rejects hidden paths.
    """
    # Validate path first (raises on traversal) before hidden check
    full = _validate_path(vault, rel_path)

    if _has_hidden_component(rel_path):
        return (False, None)

    if full.is_file():
        return (True, "file")
    if full.is_dir():
        return (True, "directory")
    return (False, None)


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
