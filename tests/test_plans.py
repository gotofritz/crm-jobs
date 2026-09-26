"""Plan filenames — the rule in AGENTS.md, "Plans"."""

import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLAN_DIRS = (PROJECT_ROOT / "docs" / "plans", PROJECT_ROOT / "docs" / "archive")
PLAN_NAME = re.compile(r"\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*\.md")


def plan_files() -> list[Path]:
    """Every plan, active or archived."""
    return [path for folder in PLAN_DIRS for path in sorted(folder.glob("*.md"))]


def test_plan_filenames_are_numbered_and_named() -> None:
    """`NNN-name-of-plan.md`, with no date or commit hash in front."""
    bad = [path.name for path in plan_files() if not PLAN_NAME.fullmatch(path.name)]
    assert bad == []


def test_plan_numbers_are_unique_across_active_and_archive() -> None:
    """Archiving keeps the number, so one number means one plan wherever it lives."""
    counts = Counter(path.name[:3] for path in plan_files())
    assert [number for number, seen in counts.items() if seen > 1] == []
