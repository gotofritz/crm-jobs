"""Reading and writing one TSV file — plan 005 §5.

Knows columns, rows and line numbers, and nothing about the ORM. The dialect is
`excel-tab`: a cell holding a tab, a newline or a quote is quoted, so a job ad
keeps its paragraphs and a note its `- ` bullets, and a spreadsheet reads it.

Reading never raises over the content. A bad header or a short row is a
`Problem`, so the import can report every one of them at once.
"""

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

DIALECT = "excel-tab"
ENCODING = "utf-8"
FALLBACK_ENCODING = "cp1252"


class Problem(NamedTuple):
    """Something wrong at a place in a file. `line` 0 means the file as a whole."""

    file: str
    line: int
    column: str
    message: str

    def __str__(self) -> str:
        """Print `file:line [column]: message`, the way a compiler would."""
        place = f"{self.file}:{self.line}" if self.line else self.file
        where = f" [{self.column}]" if self.column else ""
        return f"{place}{where}: {self.message}"


class Row(NamedTuple):
    """One data row, and the line it starts on (a quoted newline spans several)."""

    line: int
    values: dict[str, str]


@dataclass
class Table:
    """What was read from one file."""

    rows: list[Row] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    encoding: str = ENCODING


def write_table(path: Path, *, columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> None:
    """Write `rows` under a header of `columns`: UTF-8, no BOM, `\\n` line ends."""
    with path.open("w", encoding=ENCODING, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, dialect=DIALECT, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _decode(path: Path) -> tuple[str, str]:
    """The file's text and the encoding that read it, with a BOM dropped.

    A file that is not UTF-8 is read as cp1252, which is what a LibreOffice
    re-save on Windows produces; the caller is told so it can say so.
    """
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), ENCODING
    except UnicodeDecodeError:
        return raw.decode(FALLBACK_ENCODING, errors="replace"), FALLBACK_ENCODING


def read_table(path: Path, *, required: Sequence[str], optional: Sequence[str] = ()) -> Table:
    """Read `path` into rows keyed by column name.

    Columns are found by name, in any order. A `required` one that is missing,
    or a column in neither list, is a problem on line 1 and nothing below it is
    read: with the header wrong, every row would be wrong too. An `optional`
    column that is missing reads as empty.
    """
    text, encoding = _decode(path)
    table = Table(encoding=encoding)
    name = path.name
    reader = csv.reader(io.StringIO(text, newline=""), dialect=DIALECT)

    header = next(reader, None)
    if header is None:
        table.problems.append(Problem(name, 0, "", "file is empty"))
        return table

    known = {*required, *optional}
    table.problems.extend(
        Problem(name, 1, column, "required column is missing")
        for column in required
        if column not in header
    )
    table.problems.extend(
        Problem(name, 1, column, "unknown column") for column in header if column not in known
    )
    if table.problems:
        return table

    seen = reader.line_num
    for cells in reader:
        # `line_num` counts physical lines, so a row ends where the last one did
        # plus however many lines it spans; it starts on the line after.
        start, seen = seen + 1, reader.line_num
        if not cells:
            continue
        if len(cells) != len(header):
            table.problems.append(
                Problem(name, start, "", f"expected {len(header)} cells, found {len(cells)}")
            )
            continue
        values = dict.fromkeys(optional, "") | dict(zip(header, cells, strict=True))
        table.rows.append(Row(start, values))
    return table
