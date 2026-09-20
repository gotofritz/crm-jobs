"""`manage.py import_sheet` — read a CSV export of the old sheet in (plan 003 §7).

Thin on purpose: arguments, the refusals, and the report. The unpacking is in
`jobs.sheet` and the writing in `jobs.importer`.
"""

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from jobs.importer import Written, database_for, preview, write
from jobs.models import State
from jobs.sheet import Problem, parse_sheet


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


class BadCellsError(CommandError):
    """Cells that fit neither packing format. Nothing is written until they are fixed."""

    def __init__(self, problems: tuple[Problem, ...]) -> None:
        """List every one, so a single fix-and-re-export round clears them (§4.2)."""
        listed = "\n".join(f"  {problem}" for problem in problems)
        super().__init__(f"{len(problems)} cell(s) did not fit, and nothing was written:\n{listed}")


class Command(BaseCommand):
    """Import the historical sheet. See `docs/plans/003-import-the-sheet.md`."""

    help = "Import a CSV export of the old Google Sheet."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """One file, and two flags that decide where it goes and whether it goes at all."""
        parser.add_argument("csv", type=Path, help="the exported file")
        parser.add_argument(
            "--demo",
            action="store_true",
            help="write to demo.sqlite3 instead of the live database",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="parse, infer and report, writing nothing",
        )

    def handle(self, *_args: Any, **options: Any) -> None:
        """Parse, refuse if anything did not fit, then write and report."""
        path: Path = options["csv"]
        if not path.is_file():
            raise NoSuchExportError(path)

        using = database_for(demo=options["demo"])
        if not State.objects.using(using).exists():
            raise UnseededDatabaseError(using)

        parsed = parse_sheet(path.read_text())
        if parsed.problems:
            raise BadCellsError(parsed.problems)

        if options["dry_run"]:
            self.report(preview(parsed.rows, using=using), using=using, dry=True)
            return
        self.report(write(parsed.rows, using=using), using=using, dry=False)

    def report(self, written: Written, *, using: str, dry: bool) -> None:
        """Print what happened, and every guess, because every one of them is a guess (§6)."""
        did = "would write" if dry else "wrote"
        self.stdout.write(
            f"{did} {written.opportunities} opportunit(ies) "
            f"and {written.steps} step(s) to the {using} database"
        )

        self.stdout.write("\nstates inferred from step titles:")
        for inference in written.inferences:
            self.stdout.write(f"  {inference}")

        if not written.collisions:
            return
        self.stdout.write("\nnames at more than one company, to merge or keep apart by hand:")
        for collision in written.collisions:
            self.stdout.write(f"  {collision}")
