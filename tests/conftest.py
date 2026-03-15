"""Shared test fixtures for notes-mcp tests."""

from pathlib import Path

import pytest


def make_note(
    title: str,
    para: str = "resources",
    tags: list[str] | None = None,
    body: str = "",
    related: list[str] | None = None,
    extra_frontmatter: dict[str, object] | None = None,
) -> str:
    """Generate a complete note with frontmatter."""
    lines = ["---"]
    lines.append(f"title: {title}")
    lines.append(f"para: {para}")
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    if related:
        lines.append("related:")
        for r in related:
            lines.append(f"  - {r}")
    lines.append("updated: '2026-03-14'")
    if extra_frontmatter:
        for k, v in extra_frontmatter.items():
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    if body:
        lines.append(body)
    return "\n".join(lines)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a temporary vault with PARA directories and sample notes."""
    root = tmp_path / "vault"

    # Create PARA directories
    for bucket in ["Projects", "Areas", "Resources", "Archive"]:
        (root / bucket).mkdir(parents=True)

    # Project note with outlinks
    (root / "Projects" / "web-redesign.md").write_text(
        make_note(
            title="Web Redesign",
            para="projects",
            tags=["web", "design"],
            body=(
                "## Summary\n"
                "Redesigning the company website.\n\n"
                "## Related\n"
                "See [[CSS Architecture]] for styling approach.\n"
                "Also check [[Design System]].\n"
            ),
            related=["[[CSS Architecture]]", "[[Design System]]"],
        )
    )

    # Area note
    (root / "Areas" / "health.md").write_text(
        make_note(
            title="Health Tracking",
            para="areas",
            tags=["health", "fitness"],
            body="## Notes\nDaily exercise log and nutrition tracking.\n",
        )
    )

    # Resource notes
    (root / "Resources" / "css-architecture.md").write_text(
        make_note(
            title="CSS Architecture",
            para="resources",
            tags=["css", "web", "architecture"],
            body=(
                "## BEM Methodology\n"
                "Block-Element-Modifier naming convention.\n\n"
                "Used in [[Web Redesign]] project.\n"
            ),
        )
    )

    (root / "Resources" / "design-system.md").write_text(
        make_note(
            title="Design System",
            para="resources",
            tags=["design", "ui", "components"],
            body="## Component Library\nReusable UI components.\n",
        )
    )

    (root / "Resources" / "python-async.md").write_text(
        make_note(
            title="Python Async Patterns",
            para="resources",
            tags=["python", "async", "programming"],
            body="## asyncio\nEvent loop and coroutines.\n",
        )
    )

    # Archive note
    (root / "Archive" / "old-project.md").write_text(
        make_note(
            title="Old Project",
            para="archive",
            tags=["legacy"],
            body="## Retrospective\nThis project was completed in 2024.\n",
        )
    )

    return root
