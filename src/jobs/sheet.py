"""Unpacking a CSV export of the old Google Sheet — plan 003 §4.

Pure, and it stays that way: nothing here imports the ORM. The sheet packed
several fields into one rich-text cell per column, and this module turns that
text back into values. Writing them is the management command's job.

Two packing formats exist and both are accepted — the one the GAS code wrote,
and the one the sample export actually contains (§4.1). Anything matching
neither is reported rather than guessed at (§4.2).
"""

import csv
import datetime as dt
from dataclasses import dataclass
from io import StringIO

# The GAS code's separator between a company and the position on one line.
HEAD_JOIN = " / "

# A blank line. Every cell in the sheet is blocks of lines separated by one.
BLOCK = "\n\n"

# What a step cell puts between its date and its time.
STEP_JOIN = " __ "

# What the GAS app writes when it has no time for a step (§4.10).
EMPTY_TIME = ":"

# Longest single-line comment on a step with no contact that is still worth
# asking about (§4.2). Arbitrary, and only ever used to report.
NAME_LENGTH = 60


class CellError(ValueError):
    """A cell that does not fit either packing format.

    Caught rather than allowed out of the parse: the importer reports every bad
    cell in one pass, so one fix-and-re-export round clears them all (§4.2). The
    subclasses carry their own wording, because the message is the report.
    """


class MissingFieldError(CellError):
    """A cell that left out something the shape requires."""

    def __init__(self, field: str) -> None:
        """Name what is missing, since that is what goes in the report."""
        super().__init__(f"no {field}")


class NotADateError(CellError):
    """A cell whose first line is not a date — §4.2's second reportable shape."""

    def __init__(self, raw: str) -> None:
        """Quote what was there instead, so the cell is findable."""
        super().__init__(f"{raw!r} is not a date")


class NotATimeError(CellError):
    """A step whose date line carries something that is not a time."""

    def __init__(self, raw: str) -> None:
        """Quote what was there instead, so the cell is findable."""
        super().__init__(f"{raw!r} is not a time")


class TooManyBlocksError(CellError):
    """A step cell with more blocks than the shape allows — §4.2's third."""

    def __init__(self, count: int) -> None:
        """Count them, because the fix is deciding which block belongs where."""
        super().__init__(f"{count} blocks, and a step holds at most two")


class StrayContactError(CellError):
    """A step with nobody on it whose comment reads like a name — §4.2's first."""

    def __init__(self, comments: str) -> None:
        """Quote the comment, which is what a human has to look at."""
        super().__init__(f"no contact, and a comment of {comments!r} that reads like one")


def parse_head(cell: str) -> tuple[str, str, str]:
    """Split column 1 into company, position and the pasted advert (§4.1).

    The two formats differ only in how the first block is packed: the code
    writes `company " / " position`, the export writes them as two blocks. What
    follows is the advert, blank lines and all, so the split is bounded.
    """
    blocks = cell.split(BLOCK, 2)
    if HEAD_JOIN in blocks[0]:
        company, position = blocks[0].split(HEAD_JOIN, 1)
        advert = BLOCK.join(blocks[1:])
    else:
        company = blocks[0]
        position = blocks[1] if len(blocks) > 1 else ""
        advert = blocks[2] if len(blocks) > 2 else ""

    if not company.strip():
        raise MissingFieldError("company")
    if not position.strip():
        raise MissingFieldError("position")
    return company.strip(), position.strip(), advert.strip()


def a_date(raw: str) -> dt.date:
    """Read a date the sheet wrote, refusing anything that is not one (§4.2)."""
    try:
        return dt.date.fromisoformat(raw.strip())
    except ValueError as wrong:
        raise NotADateError(raw.strip()) from wrong


def parse_body(cell: str) -> tuple[dt.date, str, str]:
    """Split column 2 into date, source and contact (§4.1).

    The two formats put their blank line in different places, so the blank lines
    are dropped and the order of what is left carries the meaning. Anything past
    the source is the contact, joined the way a step's contacts are written.
    """
    lines = [line.strip() for line in cell.splitlines() if line.strip()]
    if not lines:
        raise MissingFieldError("date")
    return a_date(lines[0]), lines[1] if len(lines) > 1 else "", ", ".join(lines[2:])


@dataclass(frozen=True)
class ParsedStep:
    """One step cell, unpacked. The state is not in here — a CSV cannot carry it (§6)."""

    date: dt.date
    time: dt.time | None
    title: str
    contacts: tuple[str, ...]
    comments: str


def a_time(raw: str) -> dt.time | None:
    """Read the time beside a step's date, treating the GAS app's bare `:` as none."""
    word = raw.strip()
    if not word or word == EMPTY_TIME:
        return None
    try:
        return dt.time.fromisoformat(word)
    except ValueError as wrong:
        raise NotATimeError(word) from wrong


def parse_step(cell: str) -> ParsedStep:
    """Unpack one of columns 3 and rightwards into a step (§4.1).

    Unlike the advert in column 1, a step's comment is not allowed to run to
    several blocks: §4.2 lists that as a cell to report, because a step whose
    comment has grown paragraphs is more likely to be two steps in one cell.
    """
    first, _, rest = cell.partition("\n")
    day, _, clock = first.partition(STEP_JOIN)

    blocks = rest.lstrip("\n").split(BLOCK)
    if len(blocks) > 2:
        raise TooManyBlocksError(len(blocks))

    lines = [line.strip() for line in blocks[0].splitlines() if line.strip()]
    if not lines:
        raise MissingFieldError("title")
    comments = blocks[1].strip() if len(blocks) > 1 else ""
    contacts = tuple(names for line in lines[1:] for names in split_names(line))

    if not contacts and looks_like_a_stray_contact(comments):
        raise StrayContactError(comments)

    return ParsedStep(
        date=a_date(day),
        time=a_time(clock),
        title=lines[0],
        contacts=contacts,
        comments=comments,
    )


def split_names(raw: str) -> list[str]:
    """Split the comma-separated names a step cell writes on one line."""
    return [name for name in (part.strip() for part in raw.split(",")) if name]


def looks_like_a_stray_contact(comments: str) -> bool:
    """Whether a comment on a step with nobody on it is likely a misplaced contact.

    §4.2's first reportable shape. The length is a prompt for a human, not an
    inference: this only ever reports, and a false positive costs one look at a
    cell, while acting on it would silently mangle a comment naming somebody.
    """
    return bool(comments) and "\n" not in comments and len(comments) <= NAME_LENGTH


@dataclass(frozen=True)
class Problem:
    """A cell that did not fit, named the way a spreadsheet names it (§4.2)."""

    row: int
    column: int
    reason: str

    def __str__(self) -> str:
        """Say where and why, which is the whole of the report."""
        return f"row {self.row}, column {self.column}: {self.reason}"


@dataclass(frozen=True)
class ParsedRow:
    """One sheet row, unpacked into the fields the model keeps (§5)."""

    company: str
    title: str
    job_description: str
    date: dt.date
    source: str
    contact: str
    steps: tuple[ParsedStep, ...]


@dataclass(frozen=True)
class Parsed:
    """What a whole export came to: the rows that fit, and every cell that did not."""

    rows: tuple[ParsedRow, ...]
    problems: tuple[Problem, ...]


def is_state_header(cells: list[str]) -> bool:
    """Whether this is row 1, which defines the sheet's states rather than an opportunity.

    Columns 1 and 2 are empty there and nowhere else, which is what decides it: a
    head cell in the code's format holds ` / ` too (§4.1).
    """
    head, body = [*cells, "", ""][:2]
    return not head.strip() and not body.strip() and any(HEAD_JOIN in cell for cell in cells[2:])


def parse_row(cells: list[str], number: int) -> tuple[ParsedRow | None, list[Problem]]:
    """Unpack one row, collecting what did not fit rather than stopping at the first.

    A row with any bad cell yields no row at all. Half an opportunity is worse
    than none: the fix is one edit in the sheet and another export (§4.2).
    """
    problems: list[Problem] = []
    head: tuple[str, str, str] | None = None
    body: tuple[dt.date, str, str] | None = None
    steps: list[ParsedStep] = []

    try:
        head = parse_head(cells[0])
    except CellError as bad:
        problems.append(Problem(number, 1, str(bad)))
    try:
        body = parse_body(cells[1] if len(cells) > 1 else "")
    except CellError as bad:
        problems.append(Problem(number, 2, str(bad)))

    for offset, cell in enumerate(cells[2:], start=3):
        if not cell.strip():
            continue
        try:
            steps.append(parse_step(cell))
        except CellError as bad:
            problems.append(Problem(number, offset, str(bad)))

    if problems or head is None or body is None:
        return None, problems
    return ParsedRow(
        company=head[0],
        title=head[1],
        job_description=head[2],
        date=body[0],
        source=body[1],
        contact=body[2],
        steps=tuple(steps),
    ), []


def parse_sheet(text: str) -> Parsed:
    """Unpack a whole CSV export (§4).

    Rows are numbered as the file has them, starting at 1, so a reported problem
    is findable in the spreadsheet without counting.
    """
    rows: list[ParsedRow] = []
    problems: list[Problem] = []

    for number, cells in enumerate(csv.reader(StringIO(text)), start=1):
        if not any(cell.strip() for cell in cells) or is_state_header(cells):
            continue
        row, bad = parse_row(cells, number)
        problems.extend(bad)
        if row is not None:
            rows.append(row)

    return Parsed(rows=tuple(rows), problems=tuple(problems))
