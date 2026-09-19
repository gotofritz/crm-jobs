"""Reading settings out of the environment — plan 001 §5.

Secrets and per-host values come from the environment, never from the repo
(AGENTS.md, "Data & Secrets"). These two readers are pure apart from the lookup
itself, so the parsing is tested without importing Django's settings.
"""

import os

TRUE_WORDS = frozenset({"1", "true", "yes", "on"})
FALSE_WORDS = frozenset({"0", "false", "no", "off"})


class AmbiguousFlagError(ValueError):
    """An environment variable meant as a flag that says neither yes nor no."""

    def __init__(self, name: str, raw: str) -> None:
        """Name the variable and what it said, since the process is about to stop."""
        super().__init__(f"{name}={raw!r} is neither true nor false")


class MissingSettingError(ValueError):
    """A setting with no safe default that the environment did not supply."""

    def __init__(self, name: str) -> None:
        """Name the variable, since the process is about to stop over it."""
        super().__init__(f"{name} must be set")


def as_required(name: str) -> str:
    """Read a value that has no safe default, refusing to carry on without it."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSettingError(name)
    return value


def as_bool(name: str, *, default: bool) -> bool:
    """Read a flag from the environment, refusing anything that is not yes or no."""
    word = os.environ.get(name, "").strip().lower()
    if not word:
        return default
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise AmbiguousFlagError(name, word)


def as_list(name: str, *, default: list[str] | None = None) -> list[str]:
    """Read a comma-separated list, dropping the blanks a trailing comma leaves."""
    items = [item.strip() for item in os.environ.get(name, "").split(",")]
    return [item for item in items if item] or list(default or [])
