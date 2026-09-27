"""Reading a CSV of opportunities into rows — plan 004 §4, §6.

Pure: text in, rows and problems out. No ORM, no forms. Whether a value is a
valid date or URL is the form's question and is asked later, in
`jobs.importer`; this only answers whether the file has a shape a form can be
fed from — a header naming known columns, and rows that fit under it.

Problems are collected, not raised, so one run reports all of them (I4).
"""

import csv
import io
from dataclasses import dataclass

# Every field `OpportunityForm` takes, in the order `--template` prints them.
# A test pins this to the form, so a new field is a decision about the CSV too.
COLUMNS = (
    "company",
    "title",
    "date",
    "source",
    "contact",
    "job_description",
    "company_url",
    "company_linkedin_url",
    "company_head_office",
    "company_sector",
)

# The form's required fields, pinned the same way. A file without one of these
# headers cannot produce a single valid row, so it is refused on the header.
REQUIRED = frozenset({"company", "title", "date"})


@dataclass(frozen=True)
class Problem:
    """Something in the file that stops it being imported, and where it is.

    `column` is a header name, or empty when the problem belongs to the whole
    line. It is not `sheet.Problem`: that one names a column by number, because
    the old sheet had no header to name it by.
    """

    line: int
    column: str
    reason: str

    def __str__(self) -> str:
        """Say where and why, which is the whole of the report."""
        where = f"line {self.line}, {self.column}" if self.column else f"line {self.line}"
        return f"{where}: {self.reason}"


@dataclass(frozen=True)
class Row:
    """One opportunity's cells, keyed by column, and the line it starts on."""

    line: int
    values: dict[str, str]


@dataclass(frozen=True)
class Parsed:
    """Everything a file held, and everything wrong with it."""

    rows: tuple[Row, ...]
    problems: tuple[Problem, ...]


def header_problems(names: list[str]) -> list[Problem]:
    """Unknown and repeated names, then any required one that is missing.

    An empty name is not a problem here: a trailing comma makes one, and what
    matters is only whether anything is ever written under it (`read_row`).
    """
    problems = []
    seen: set[str] = set()
    for name in names:
        if not name:
            continue
        if name not in COLUMNS:
            problems.append(Problem(line=1, column=name, reason="unknown column"))
        elif name in seen:
            problems.append(Problem(line=1, column=name, reason="column appears twice"))
        seen.add(name)

    problems.extend(
        Problem(line=1, column=name, reason="required column is missing")
        for name in COLUMNS
        if name in REQUIRED and name not in seen
    )
    return problems


def read_row(cells: list[str], *, names: list[str], line: int) -> Row | Problem:
    """Key one record's cells by the header, padding a short one with blanks."""
    if len(cells) > len(names):
        return Problem(
            line=line, column="", reason=f"{len(cells)} cells, but the header has {len(names)}"
        )

    padded = cells + [""] * (len(names) - len(cells))
    if any(value.strip() for name, value in zip(names, padded, strict=True) if not name):
        return Problem(line=line, column="", reason="a value under no header")
    return Row(
        line=line, values={name: value for name, value in zip(names, padded, strict=True) if name}
    )


def read(text: str) -> Parsed:
    """Split a CSV's text into rows keyed by its header, and the problems found on the way.

    Rows are numbered by the physical line they start on, so a pasted ad
    spanning several lines does not shift the line a later problem is reported
    on. A record that is blank in every cell is skipped: spreadsheets pad their
    exports with them.
    """
    records = csv.reader(io.StringIO(text.removeprefix("﻿"), newline=""))
    header = next(records, None)
    if header is None:
        return Parsed(rows=(), problems=(Problem(line=1, column="", reason="the file is empty"),))

    names = [name.strip().lower() for name in header]
    problems = header_problems(names)
    rows = []
    ended_on = records.line_num
    for cells in records:
        line, ended_on = ended_on + 1, records.line_num
        if not any(cell.strip() for cell in cells):
            continue
        read_as = read_row(cells, names=names, line=line)
        if isinstance(read_as, Problem):
            problems.append(read_as)
        else:
            rows.append(read_as)

    return Parsed(rows=tuple(rows), problems=tuple(problems))
