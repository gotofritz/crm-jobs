"""`manage.py import_opportunities` — add a CSV of opportunities to the board (plan 004 §7).

Thin on purpose: arguments, the refusals, and the report. The reading is in
`jobs.opportunity_csv` and the validating and writing in `jobs.importer`.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from jobs.importer import Imported, database_for, import_opportunities
from jobs.management.refusals import NoSuchExportError, UnseededDatabaseError
from jobs.models import State
from jobs.opportunity_csv import COLUMNS, REQUIRED, Problem, read


class NoFileError(CommandError):
    """No path and no `--template`: nothing to do, which is a mistake rather than a run."""

    def __init__(self) -> None:
        """Say what is missing, and the one way to run without it."""
        super().__init__("give a CSV file, - for stdin, or --template for the header row")


class BadRowsError(CommandError):
    """A file that cannot be imported as it stands. Nothing is written (I4)."""

    def __init__(self, problems: tuple[Problem, ...]) -> None:
        """List every one, so a single fix-and-re-run round clears them."""
        listed = "\n".join(f"  {problem}" for problem in problems)
        super().__init__(f"{len(problems)} problem(s), and nothing was written:\n{listed}")


class Command(BaseCommand):
    """Import opportunities from a CSV. See `docs/archive/004-import-opportunities-csv.md`."""

    help = "Add opportunities from a CSV file with a header row. --template prints the header."

    # Where `-` reads from. Not an argument: `call_command` passes a stream here
    # in tests, and on the command line it is the process's own stdin.
    stealth_options = ("stdin",)

    def add_arguments(self, parser: ArgumentParser) -> None:
        """One file, and flags for where it goes, whether it goes, and how to start one."""
        parser.add_argument("csv", nargs="?", help="the file to read, or - for stdin")
        parser.add_argument(
            "--demo",
            action="store_true",
            help="write to demo.sqlite3 instead of the live database",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="validate and report, writing nothing",
        )
        parser.add_argument(
            "--template",
            action="store_true",
            help="print the header row and exit",
        )

    def handle(self, *_args: Any, **options: Any) -> None:
        """Read, refuse if anything is wrong, then write and report."""
        if options["template"]:
            self.stdout.write(",".join(COLUMNS))
            return
        if options["csv"] is None:
            raise NoFileError

        text = self.text_of(options["csv"], stdin=options.get("stdin") or sys.stdin)

        using = database_for(demo=options["demo"])
        if not State.objects.using(using).exists():
            raise UnseededDatabaseError(using)

        parsed = read(text)
        if parsed.problems:
            # The rows that did fit are still validated, so one run reports the
            # header and the values together — unless a required column is
            # missing, when every row would repeat what the header already says.
            checked = ()
            if parsed.rows and parsed.rows[0].values.keys() >= REQUIRED:
                checked = import_opportunities(parsed.rows, using=using, dry_run=True).problems
            raise BadRowsError(parsed.problems + checked)

        imported = import_opportunities(parsed.rows, using=using, dry_run=options["dry_run"])
        if imported.problems:
            raise BadRowsError(imported.problems)
        self.report(imported, using=using, dry=options["dry_run"])

    def text_of(self, source: str, *, stdin: Any) -> str:
        """The file's text, or stdin's for `-`. A BOM is the reader's to strip."""
        if source == "-":
            return stdin.read()
        path = Path(source)
        if not path.is_file():
            raise NoSuchExportError(path)
        return path.read_text(encoding="utf-8")

    def report(self, imported: Imported, *, using: str, dry: bool) -> None:
        """Say what was created and what was already there, row by row."""
        did = "would create" if dry else "created"
        self.stdout.write(
            f"{did} {len(imported.created)}, skipped {len(imported.skipped)} "
            f"already on the board, in the {using} database"
        )
        for heading, entries in ((did, imported.created), ("skipped", imported.skipped)):
            if not entries:
                continue
            self.stdout.write(f"\n{heading}:")
            for entry in entries:
                self.stdout.write(f"  {entry}")
