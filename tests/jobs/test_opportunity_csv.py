"""Reading a CSV of opportunities — plan 004 §4, §6, Phase 2.

The reader is pure: text in, rows and problems out, no database. What it knows
about the form is two constants, and the first two tests here are what keeps
those honest.
"""

from jobs.forms import OpportunityForm
from jobs.opportunity_csv import COLUMNS, REQUIRED, Problem, read

HEADER = "company,title,date"


def test_the_columns_are_the_forms_fields() -> None:
    """A new form field is a decision about the CSV too, so this breaks until it is made."""
    assert set(COLUMNS) == set(OpportunityForm().fields)


def test_the_required_columns_are_the_forms_required_fields() -> None:
    """The header check and the form agree on what a row cannot do without."""
    required = {name for name, field in OpportunityForm().fields.items() if field.required}

    assert required == REQUIRED


def test_a_row_is_keyed_by_its_header() -> None:
    """Values come back under the column names, in whatever order the file had them."""
    parsed = read("date,Title,COMPANY\n2026-09-24,Staff Engineer,Northwind\n")

    assert parsed.problems == ()
    assert parsed.rows[0].values == {
        "company": "Northwind",
        "title": "Staff Engineer",
        "date": "2026-09-24",
    }


def test_header_names_are_trimmed() -> None:
    """` company ` is `company`: spreadsheets pad cells, and nobody sees the spaces."""
    parsed = read(" company , title,date \nNorthwind,Staff Engineer,2026-09-24\n")

    assert parsed.problems == ()
    assert set(parsed.rows[0].values) == {"company", "title", "date"}


def test_a_byte_order_mark_is_not_part_of_the_first_header() -> None:
    """Excel's "CSV UTF-8" starts with one, and `company` must still be `company`."""
    parsed = read("﻿company,title,date\nNorthwind,Staff Engineer,2026-09-24\n")

    assert parsed.problems == ()
    assert parsed.rows[0].values["company"] == "Northwind"


def test_blank_lines_and_empty_rows_are_skipped() -> None:
    """Spreadsheets pad an export with rows of bare commas."""
    parsed = read(f"{HEADER}\n\nNorthwind,Staff Engineer,2026-09-24\n,,\n\n")

    assert parsed.problems == ()
    assert len(parsed.rows) == 1


def test_a_short_row_is_padded_with_blanks() -> None:
    """Trailing empty cells are often trimmed on export; missing is the same as empty."""
    parsed = read("company,title,date,source\nNorthwind,Staff Engineer,2026-09-24\n")

    assert parsed.problems == ()
    assert parsed.rows[0].values["source"] == ""


def test_a_missing_required_column_is_named() -> None:
    """No `date` header means no row can be imported, so it is said once, on the header."""
    parsed = read("company,title\nNorthwind,Staff Engineer\n")

    assert parsed.problems == (Problem(line=1, column="date", reason="required column is missing"),)


def test_an_unknown_column_is_named_rather_than_dropped() -> None:
    """A typo'd header would otherwise lose a whole column without a word (I6)."""
    parsed = read(f"{HEADER},sorce\nNorthwind,Staff Engineer,2026-09-24,LinkedIn\n")

    assert parsed.problems == (Problem(line=1, column="sorce", reason="unknown column"),)


def test_a_column_named_twice_is_a_problem() -> None:
    """Two `title` columns leave no way to tell which one was meant."""
    parsed = read(f"{HEADER},Title\nNorthwind,Staff Engineer,2026-09-24,Lead\n")

    assert parsed.problems == (Problem(line=1, column="title", reason="column appears twice"),)


def test_a_column_with_no_header_is_ignored_while_it_is_empty() -> None:
    """A trailing comma on every line makes one, and it holds nothing."""
    parsed = read(f"{HEADER},\nNorthwind,Staff Engineer,2026-09-24,\n")

    assert parsed.problems == ()
    assert set(parsed.rows[0].values) == {"company", "title", "date"}


def test_a_value_under_no_header_is_a_problem() -> None:
    """Data with no name cannot be put anywhere, and dropping it would be silent."""
    parsed = read(f"{HEADER},\nNorthwind,Staff Engineer,2026-09-24,stray\n")

    assert parsed.problems == (Problem(line=2, column="", reason="a value under no header"),)


def test_a_row_with_more_cells_than_the_header_is_a_problem() -> None:
    """An unquoted comma in a value shifts every cell after it."""
    parsed = read(f"{HEADER}\nNorthwind, Inc,Staff Engineer,2026-09-24\n")

    assert parsed.problems == (Problem(line=2, column="", reason="4 cells, but the header has 3"),)
    assert parsed.rows == ()


def test_a_quoted_cell_keeps_its_commas_and_newlines() -> None:
    """A pasted job ad has both."""
    parsed = read(
        f'{HEADER},job_description\nNorthwind,Staff Engineer,2026-09-24,"Rust, Go\n\nRemote"\n'
    )

    assert parsed.problems == ()
    assert parsed.rows[0].values["job_description"] == "Rust, Go\n\nRemote"


def test_a_row_is_numbered_by_the_line_it_starts_on() -> None:
    """A multi-line cell above must not shift the line a later problem is reported on."""
    text = (
        f"{HEADER},job_description\n"
        'Northwind,Staff Engineer,2026-09-24,"one\ntwo\nthree"\n'
        "Contoso,Backend Developer,2026-09-25,\n"
    )

    parsed = read(text)

    assert [row.line for row in parsed.rows] == [2, 5]


def test_an_empty_file_is_a_problem() -> None:
    """No header, nothing to check a row against."""
    assert read("").problems == (Problem(line=1, column="", reason="the file is empty"),)


def test_every_problem_is_reported_in_one_pass() -> None:
    """A fix-and-re-run loop costs one round, not one round per problem (I4)."""
    parsed = read("company,title,sorce\nNorthwind,Staff Engineer,LinkedIn,extra\n")

    assert len(parsed.problems) == 3


def test_a_problem_reads_as_a_place_and_a_reason() -> None:
    """What the command prints, one per line."""
    assert str(Problem(line=4, column="date", reason="Enter a valid date.")) == (
        "line 4, date: Enter a valid date."
    )
    assert str(Problem(line=2, column="", reason="4 cells, but the header has 3")) == (
        "line 2: 4 cells, but the header has 3"
    )
