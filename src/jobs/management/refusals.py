"""Refusals both import commands make before they touch anything — plans 003 and 004.

Here rather than in either command, so neither imports the other, and rather
than in `jobs.importer`, because a `CommandError` belongs to the command line,
not to the layer that writes rows.
"""

from pathlib import Path

from django.core.management.base import CommandError


class NoSuchExportError(CommandError):
    """A path that is not there. A typo is not a reason to import nothing quietly."""

    def __init__(self, path: Path) -> None:
        """Name the file, since that is the thing to fix."""
        super().__init__(f"{path} is not a file")


class UnseededDatabaseError(CommandError):
    """A database with no states in it, which every step needs one of.

    What `--demo` against a demo.sqlite3 nobody has built yet looks like. Said
    up front rather than as a foreign key failure half way through.
    """

    def __init__(self, alias: str) -> None:
        """Name the database and the way out of it."""
        super().__init__(f"the {alias} database has no states — run migrate on it first")
