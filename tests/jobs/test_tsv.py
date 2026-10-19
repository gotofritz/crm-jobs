"""Reading and writing one TSV file — plan 005 §5, phase 2.

No database: `tsv.py` knows columns and rows and line numbers, and nothing else.
"""

from pathlib import Path

from jobs.tsv import read_table, write_table

COLUMNS = ("name", "body")


def test_a_written_file_has_a_header_and_no_bom(tmp_path: Path) -> None:
    """UTF-8, tab separated, the header first and no byte order mark."""
    path = tmp_path / "x.tsv"

    write_table(path, columns=COLUMNS, rows=[{"name": "Zoë", "body": "hello"}])

    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8") == "name\tbody\nZoë\thello\n"


def test_tabs_newlines_and_quotes_survive_a_round_trip(tmp_path: Path) -> None:
    """Quoted the `excel-tab` way, so an ad keeps its paragraphs and its bullets."""
    path = tmp_path / "x.tsv"
    body = 'Line one\n- a "bullet"\twith a tab\n\nLine four'

    write_table(path, columns=COLUMNS, rows=[{"name": "n", "body": body}])
    table = read_table(path, required=COLUMNS)

    assert table.problems == []
    assert [row.values["body"] for row in table.rows] == [body]


def test_a_bom_is_dropped(tmp_path: Path) -> None:
    """A LibreOffice or Excel re-save puts one on the first header."""
    path = tmp_path / "x.tsv"
    path.write_bytes("﻿name\tbody\na\tb\n".encode())

    table = read_table(path, required=COLUMNS)

    assert table.problems == []
    assert table.rows[0].values == {"name": "a", "body": "b"}


def test_a_file_that_is_not_utf8_is_read_as_cp1252_and_said_so(tmp_path: Path) -> None:
    """A LibreOffice re-save on Windows is cp1252; reading it is better than refusing."""
    path = tmp_path / "x.tsv"
    path.write_bytes("name\tbody\ncaf\xe9\tb\n".encode("cp1252"))

    table = read_table(path, required=COLUMNS)

    assert table.rows[0].values["name"] == "café"
    assert table.encoding == "cp1252"


def test_utf8_is_reported_as_utf8(tmp_path: Path) -> None:
    """The fallback is reported only when it happened."""
    path = tmp_path / "x.tsv"
    write_table(path, columns=COLUMNS, rows=[])

    assert read_table(path, required=COLUMNS).encoding == "utf-8"


def test_rows_know_the_line_they_start_on(tmp_path: Path) -> None:
    """A quoted newline moves the next row down by more than one line."""
    path = tmp_path / "x.tsv"
    path.write_text('name\tbody\na\t"x\ny"\nb\tz\n', encoding="utf-8")

    table = read_table(path, required=COLUMNS)

    assert [row.line for row in table.rows] == [2, 4]


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    """A spreadsheet leaves a trailing empty line behind."""
    path = tmp_path / "x.tsv"
    path.write_text("name\tbody\n\na\tb\n\n", encoding="utf-8")

    table = read_table(path, required=COLUMNS)

    assert [row.line for row in table.rows] == [3]


def test_a_missing_required_column_is_a_problem_naming_it(tmp_path: Path) -> None:
    """The header is line 1, and nothing is read past a bad one."""
    path = tmp_path / "x.tsv"
    path.write_text("name\na\n", encoding="utf-8")

    table = read_table(path, required=COLUMNS)

    assert table.rows == []
    assert [(p.file, p.line, p.column) for p in table.problems] == [("x.tsv", 1, "body")]


def test_an_unknown_column_is_a_problem(tmp_path: Path) -> None:
    """A typo in a header must not quietly drop a whole column of data."""
    path = tmp_path / "x.tsv"
    path.write_text("name\tbody\tbogus\na\tb\tc\n", encoding="utf-8")

    table = read_table(path, required=COLUMNS)

    assert [(p.line, p.column) for p in table.problems] == [(1, "bogus")]


def test_optional_columns_may_be_absent_and_read_as_empty(tmp_path: Path) -> None:
    """A hand-written file need only carry what it has."""
    path = tmp_path / "x.tsv"
    path.write_text("name\na\n", encoding="utf-8")

    table = read_table(path, required=("name",), optional=("body",))

    assert table.problems == []
    assert table.rows[0].values == {"name": "a", "body": ""}


def test_columns_may_come_in_any_order(tmp_path: Path) -> None:
    """Columns are found by name, so a spreadsheet may rearrange them."""
    path = tmp_path / "x.tsv"
    path.write_text("body\tname\nb\ta\n", encoding="utf-8")

    table = read_table(path, required=COLUMNS)

    assert table.rows[0].values == {"name": "a", "body": "b"}


def test_a_row_with_the_wrong_number_of_cells_is_a_problem_with_its_line(tmp_path: Path) -> None:
    """Reported, and the rows around it are still read."""
    path = tmp_path / "x.tsv"
    path.write_text("name\tbody\na\tb\nonly\nc\td\n", encoding="utf-8")

    table = read_table(path, required=COLUMNS)

    assert [(p.line, p.column) for p in table.problems] == [(3, "")]
    assert [row.line for row in table.rows] == [2, 4]


def test_a_problem_prints_file_line_and_column(tmp_path: Path) -> None:
    """The report a person reads: where to look, and what is wrong."""
    path = tmp_path / "x.tsv"
    path.write_text("name\na\n", encoding="utf-8")

    problem = read_table(path, required=COLUMNS).problems[0]

    assert str(problem).startswith("x.tsv:1 [body]: ")
