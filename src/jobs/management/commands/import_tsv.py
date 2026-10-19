"""`manage.py import_tsv <dir>` — add what a directory of TSV files holds (plan 005)."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from jobs.transfer import TABLES, import_tables
from jobs.tsv import ENCODING, Problem, read_table


class Command(BaseCommand):
    """Create the rows the board lacks, all or nothing."""

    help = (
        "Import TSV files from a directory. Rows already on the board are skipped, "
        "never updated; one problem anywhere writes nothing."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """The directory to read, and how careful to be."""
        parser.add_argument("directory", type=Path)
        parser.add_argument("--demo", action="store_true", help="write demo.sqlite3, not the board")
        parser.add_argument(
            "--dry-run", action="store_true", help="do the import, report it, roll it back"
        )

    def handle(
        self, *_args: Any, directory: Path, demo: bool, dry_run: bool, **_options: Any
    ) -> None:
        """Read every file that is there, then import them together."""
        if not directory.is_dir():
            message = f"{directory} is not a directory"
            raise CommandError(message)
        present = [name for name in TABLES if (directory / f"{name}.tsv").is_file()]
        if not present:
            message = f"{directory} holds no .tsv files named {', '.join(TABLES)}"
            raise CommandError(message)

        tables = {}
        problems: list[Problem] = []
        for name in present:
            columns = TABLES[name]
            table = read_table(
                directory / f"{name}.tsv", required=columns.required, optional=columns.optional
            )
            problems.extend(table.problems)
            tables[name] = [(row.line, row.values) for row in table.rows]
            if table.encoding != ENCODING:
                self.stdout.write(f"{name}.tsv is not UTF-8; read as {table.encoding}")

        if not problems:
            report = import_tables(tables, using="demo" if demo else "default", dry_run=dry_run)
            problems = [
                Problem(f"{i.table}.tsv", i.line, i.column, i.message) for i in report.issues
            ]
        if problems:
            lines = "\n".join(f"  {problem}" for problem in problems)
            message = f"{len(problems)} problem(s), nothing was imported:\n{lines}"
            raise CommandError(message)

        for name in present:
            made, skipped = report.created[name], report.skipped[name]
            self.stdout.write(f"{name}: {made} created, {skipped} skipped")
        if dry_run:
            self.stdout.write("Dry run: nothing was written.")
