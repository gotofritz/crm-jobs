"""`manage.py export_tsv <dir>` — write the board as one TSV per kind of row (plan 005)."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from jobs.transfer import TABLES, export_tables
from jobs.tsv import write_table


class Command(BaseCommand):
    """Export every opportunity, step, note, company and contact."""

    help = "Export the board to TSV files in a directory. Refuses to overwrite an earlier export."

    def add_arguments(self, parser: CommandParser) -> None:
        """The directory to write, and which database to read."""
        parser.add_argument("directory", type=Path, help="created if missing")
        parser.add_argument("--demo", action="store_true", help="read demo.sqlite3, not the board")

    def handle(self, *_args: Any, directory: Path, demo: bool, **_options: Any) -> None:
        """Write one file per table, or refuse if an export is already there."""
        taken = [f"{name}.tsv" for name in TABLES if (directory / f"{name}.tsv").exists()]
        if taken:
            message = f"{directory} already holds {', '.join(taken)}; export somewhere else"
            raise CommandError(message)

        directory.mkdir(parents=True, exist_ok=True)
        tables = export_tables(using="demo" if demo else "default")
        for name, rows in tables.items():
            columns = TABLES[name]
            write_table(
                directory / f"{name}.tsv",
                columns=[*columns.required, *columns.optional],
                rows=rows,
            )
            self.stdout.write(f"{name}.tsv: {len(rows)} rows")
