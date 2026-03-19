"""Filesystem operations on the Markdown vault."""

from datetime import date
from pathlib import Path

import structlog

from notes_mcp.frontmatter import parse_frontmatter, serialize_frontmatter
from notes_mcp.models import DirectoryEntry, EditResult, Note, NoteListEntry

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


def edit_note(
    vault: Path,
    rel_path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
) -> EditResult:
    """Search and replace text in a note's body, preserving frontmatter.

    Raises:
        FileNotFoundError: Note doesn't exist.
        ValueError: old_text not found, or ambiguous (multiple matches without replace_all).
    """
    full = _validate_path(vault, rel_path)
    if not full.is_file():
        msg = f"Note not found: {rel_path}"
        raise FileNotFoundError(msg)

    raw = full.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    count = body.count(old_text)
    if count == 0:
        msg = f"Text not found in note body: {old_text[:50]!r}"
        raise ValueError(msg)
    if count > 1 and not replace_all:
        msg = f"Text is ambiguous ({count} occurrences). Use replace_all=True to replace all."
        raise ValueError(msg)

    if replace_all:
        new_body = body.replace(old_text, new_text)
    else:
        new_body = body.replace(old_text, new_text, 1)

    fm.updated = date.today().isoformat()
    final = serialize_frontmatter(fm, new_body)
    full.write_text(final, encoding="utf-8")
    logger.info("vault.edit", path=rel_path, replacements=count)

    title = fm.title or full.stem
    return EditResult(path=rel_path, title=title, updated=fm.updated, replacements=count)


def append_to_note(
    vault: Path,
    rel_path: str,
    content: str,
    heading: str | None = None,
) -> Note:
    """Append content to a note, optionally under a specific heading.

    If heading is provided, inserts before the next heading of the same
    or higher level. If the heading doesn't exist, creates it at the end.

    Raises:
        FileNotFoundError: Note doesn't exist.
    """
    full = _validate_path(vault, rel_path)
    if not full.is_file():
        msg = f"Note not found: {rel_path}"
        raise FileNotFoundError(msg)

    raw = full.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    if heading is None:
        # Simple append to end
        if body and not body.endswith("\n"):
            body += "\n"
        body += content + "\n"
    else:
        body = _insert_under_heading(body, heading, content)

    fm.updated = date.today().isoformat()
    final = serialize_frontmatter(fm, body)
    full.write_text(final, encoding="utf-8")
    logger.info("vault.append", path=rel_path, heading=heading)

    title = fm.title or full.stem
    return Note(path=rel_path, title=title, frontmatter=fm, content=body)


def _insert_under_heading(body: str, heading: str, content: str) -> str:
    """Insert content under a heading, before the next same-or-higher level heading."""
    lines = body.split("\n")
    heading_stripped = heading.strip()

    # Determine heading level (count leading #)
    level = len(heading_stripped) - len(heading_stripped.lstrip("#"))

    # Find the target heading
    target_idx = None
    for i, line in enumerate(lines):
        if line.strip() == heading_stripped:
            target_idx = i
            break

    if target_idx is None:
        # Heading doesn't exist — create at end
        if body and not body.endswith("\n"):
            body += "\n"
        return body + f"\n{heading_stripped}\n{content}\n"

    # Find the end of this section (next heading of same or higher level)
    insert_idx = len(lines)
    for i in range(target_idx + 1, len(lines)):
        line = lines[i]
        if line.startswith("#"):
            line_level = len(line) - len(line.lstrip("#"))
            if line_level <= level:
                insert_idx = i
                break

    # Insert content before the next heading, with a blank line
    insert_line = content
    # Ensure blank line before if previous line has content
    if insert_idx > 0 and lines[insert_idx - 1].strip():
        insert_line = "\n" + insert_line

    lines.insert(insert_idx, insert_line)
    return "\n".join(lines)


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
