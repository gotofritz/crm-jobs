"""Unpacking the old sheet's cells — plan 003 §4.1.

The parser is pure, so none of this needs the `db` fixture. Every cell shape
appears twice: once as the GAS code wrote it and once as the sample export
actually contains it (§4.1), because the importer has to accept both.
"""

import datetime as dt
from pathlib import Path

import pytest

from jobs.sheet import (
    CellError,
    ParsedStep,
    is_state_header,
    parse_body,
    parse_head,
    parse_sheet,
    parse_step,
)


def test_head_splits_the_observed_format() -> None:
    """Company, position and advert, separated by blank lines — what the export holds."""
    company, position, advert = parse_head("NebulaGrid\n\nStaff Engineer\n\nWe are looking")

    assert (company, position, advert) == ("NebulaGrid", "Staff Engineer", "We are looking")


def test_head_splits_the_code_format() -> None:
    """The GAS code packs company and position onto one line, separated by ` / `."""
    company, position, advert = parse_head("NebulaGrid / Staff Engineer\n\nWe are looking")

    assert (company, position, advert) == ("NebulaGrid", "Staff Engineer", "We are looking")


def test_head_keeps_a_multi_line_position() -> None:
    """The sheet's position carries a location and a salary line by convention (§4.1)."""
    _, position, _ = parse_head(
        "NebulaGrid\n\nStaff Engineer\nBased in Edinburgh, remote. £125k\n\nWe are looking"
    )

    assert position == "Staff Engineer\nBased in Edinburgh, remote. £125k"


def test_head_keeps_the_blank_lines_inside_an_advert() -> None:
    """The advert is the last block, so its own paragraphs must not split it further."""
    _, _, advert = parse_head("NebulaGrid\n\nStaff Engineer\n\nFirst para\n\nSecond para")

    assert advert == "First para\n\nSecond para"


def test_head_without_an_advert_parses() -> None:
    """A row nobody pasted an ad into is ordinary, not broken."""
    assert parse_head("NebulaGrid\n\nStaff Engineer") == ("NebulaGrid", "Staff Engineer", "")


def test_head_without_a_position_is_a_problem() -> None:
    """Guessing `[TBC]` the way the sheet did would hide a cell worth fixing (§4.2)."""
    with pytest.raises(CellError, match="position"):
        parse_head("NebulaGrid")


def test_head_without_a_company_is_a_problem() -> None:
    """A row has to name an employer; the sheet's `????` default is not imported."""
    with pytest.raises(CellError, match="company"):
        parse_head("\n\nStaff Engineer")


def test_body_splits_the_observed_format() -> None:
    """Date, source and contact — the export puts its blank line before the contact."""
    assert parse_body("2025-07-08\nWellfound\n\nMaya Richardson") == (
        dt.date(2025, 7, 8),
        "Wellfound",
        "Maya Richardson",
    )


def test_body_splits_the_code_format() -> None:
    """The GAS code puts the blank line after the date instead. Same three lines."""
    assert parse_body("2025-07-08\n\nWellfound\nMaya Richardson") == (
        dt.date(2025, 7, 8),
        "Wellfound",
        "Maya Richardson",
    )


def test_body_without_a_contact_parses() -> None:
    """Applying through a site leaves nobody to name, and that is not an error."""
    assert parse_body("2025-07-08\nWellfound") == (dt.date(2025, 7, 8), "Wellfound", "")


def test_body_joins_a_contact_that_runs_over_two_lines() -> None:
    """§4.1: date, source, and whatever remains joined as contact."""
    _, _, contact = parse_body("2025-07-08\nWellfound\n\nMaya Richardson\nAlex Chen")

    assert contact == "Maya Richardson, Alex Chen"


def test_body_whose_first_line_is_not_a_date_is_a_problem() -> None:
    """One of the three things §4.2 says to report rather than resolve."""
    with pytest.raises(CellError, match="date"):
        parse_body("sometime last July\nWellfound")


SAMPLE_STEP = "2025-07-21 __ 16:42\nREJECTED\nMaya Richardson\n\nThey moved on"


def test_step_splits_the_observed_format() -> None:
    """Date and time, then title and contact, then the comment. What the export holds."""
    step = parse_step(SAMPLE_STEP)

    assert step == ParsedStep(
        date=dt.date(2025, 7, 21),
        time=dt.time(16, 42),
        title="REJECTED",
        contacts=("Maya Richardson",),
        comments="They moved on",
    )


def test_step_splits_the_code_format() -> None:
    """The GAS code puts a blank line after the date line. Everything else matches."""
    assert parse_step(SAMPLE_STEP.replace(" __ 16:42\n", " __ 16:42\n\n")) == parse_step(
        SAMPLE_STEP
    )


def test_step_without_comments_parses() -> None:
    """A step ends after its contact line when there is nothing to say (§4.1)."""
    step = parse_step("2025-07-21 __ 16:42\nREJECTED\nMaya Richardson")

    assert step.comments == ""
    assert step.contacts == ("Maya Richardson",)


def test_step_keeps_both_of_two_contacts() -> None:
    """The sample's technical interview was with two people, written on one line."""
    step = parse_step("2025-07-15 __ 13:30\nTechnical interview\nAlex Chen, Priya Nair")

    assert step.contacts == ("Alex Chen", "Priya Nair")


def test_step_without_a_contact_parses() -> None:
    """Not every step is with somebody, and an empty contact is not a missing one."""
    step = parse_step("2025-07-21 __ 16:42\nApplied via site")

    assert step.contacts == ()


def test_step_reads_a_colon_as_no_time() -> None:
    """§4.10: the GAS app writes a bare `:` where it has no time."""
    assert parse_step("2025-07-21 __ :\nREJECTED").time is None


def test_step_without_a_time_parses() -> None:
    """A date on its own, with no separator after it at all."""
    assert parse_step("2025-07-21\nREJECTED").time is None


def test_step_whose_first_line_is_not_a_date_is_a_problem() -> None:
    """§4.2 reports it rather than dropping the step."""
    with pytest.raises(CellError, match="date"):
        parse_step("last Tuesday __ 16:42\nREJECTED")


def test_step_without_a_title_is_a_problem() -> None:
    """The sheet's `Applied via site` default is not guessed at on import."""
    with pytest.raises(CellError, match="title"):
        parse_step("2025-07-21 __ 16:42")


def test_the_malformed_sample_cell_is_a_problem() -> None:
    """§4.2's one bad cell: the blank line turns a contact into a comment.

    Reported rather than repaired. Matching it against the contacts already seen
    on the row would fix this cell and silently mangle a comment that names
    somebody, so the sheet is fixed and re-exported instead.
    """
    with pytest.raises(CellError, match="contact"):
        parse_step("2025-07-11 __ 10:05\nScheduling interview\n\nMaya Richardson")


def test_step_with_more_blocks_than_the_shape_allows_is_a_problem() -> None:
    """The third thing §4.2 reports. A step is a head block and a comment, no more."""
    with pytest.raises(CellError, match="blocks"):
        parse_step("2025-07-21 __ 16:42\nREJECTED\nMaya\n\nThey moved on\n\nand said so")


SAMPLE = Path(__file__).resolve().parents[2] / "clasp" / "Crm-clasp-2 - Sheet2.csv"

# The one bad cell in the sample (§4.2), and the fix the checklist asks for.
STRAY_BLANK = "Scheduling interview\n\nMaya Richardson"
FIXED = "Scheduling interview\nMaya Richardson"


@pytest.fixture(scope="session")
def sample_csv() -> str:
    """The one exported opportunity the packing rules were validated against (§4.1)."""
    return SAMPLE.read_text()


@pytest.fixture(scope="session")
def cleaned_csv(sample_csv: str) -> str:
    """The same export with §4.2's stray blank line taken out, as the checklist says."""
    return sample_csv.replace(STRAY_BLANK, FIXED)


def test_a_state_definition_row_is_recognised() -> None:
    """Row 1 holds `GROUP / NAME` from column 3 rightwards, and nothing in 1 and 2."""
    assert is_state_header(["", "", "DUE / DUE", "COMPLETE / GHOSTED"])


def test_an_opportunity_row_is_not_a_state_definition_row() -> None:
    """A head cell can hold ` / ` too, so the empty first two cells are what decides."""
    assert not is_state_header(["NebulaGrid / Staff Engineer", "2025-07-08\nWellfound"])


def test_the_cleaned_sample_parses_to_one_opportunity(cleaned_csv: str) -> None:
    """End to end over the real export, once its one bad cell is fixed."""
    parsed = parse_sheet(cleaned_csv)

    assert parsed.problems == ()
    assert len(parsed.rows) == 1
    assert parsed.rows[0].company == "NebulaGrid"
    assert parsed.rows[0].source == "Wellfound"
    assert parsed.rows[0].date == dt.date(2025, 7, 8)


def test_the_sample_steps_come_out_newest_first(cleaned_csv: str) -> None:
    """Column order is newest leftwards, so nothing needs to store a step's position."""
    dates = [step.date for step in parse_sheet(cleaned_csv).rows[0].steps]

    assert dates == sorted(dates, reverse=True)
    assert len(dates) == 5


def test_the_sample_carries_the_whole_job_ad(cleaned_csv: str) -> None:
    """1870 characters of pasted advert, which is what `job_description` is for."""
    advert = parse_sheet(cleaned_csv).rows[0].job_description

    assert advert.startswith("NebulaGrid is developing infrastructure")
    assert len(advert) > 1000


def test_the_sample_position_keeps_its_location_and_salary_line(cleaned_csv: str) -> None:
    """The sheet's position is more than a title, and it stays free text (#13)."""
    assert parse_sheet(cleaned_csv).rows[0].title == (
        "Staff Software Engineer - Distributed AI\nBased in Edinburgh, remote. £125k"
    )


def test_the_unfixed_sample_reports_its_one_bad_cell(sample_csv: str) -> None:
    """The export as committed still has §4.2's stray blank line in column 6."""
    parsed = parse_sheet(sample_csv)

    assert parsed.rows == ()
    assert len(parsed.problems) == 1
    assert (parsed.problems[0].row, parsed.problems[0].column) == (1, 6)


def test_a_state_definition_row_is_skipped() -> None:
    """A full-sheet export leads with one; the one-row sample has none."""
    parsed = parse_sheet(
        '"","","DUE / DUE"\n"NebulaGrid\n\nStaff Engineer","2025-07-08\nWellfound"\n'
    )

    assert [row.company for row in parsed.rows] == ["NebulaGrid"]


def test_a_blank_row_is_not_an_opportunity() -> None:
    """Exports carry trailing empty rows, and they are not worth reporting."""
    parsed = parse_sheet('"NebulaGrid\n\nStaff Engineer","2025-07-08\nWellfound"\n"",""\n')

    assert (len(parsed.rows), parsed.problems) == (1, ())


def test_one_bad_row_does_not_hide_the_next_one() -> None:
    """Every problem is collected in one pass, so one fix-and-re-export clears them."""
    parsed = parse_sheet(
        '"NebulaGrid","2025-07-08\nWellfound"\n"Aperture\n\nQA Lead","not a date\nWellfound"\n'
    )

    assert [(problem.row, problem.column) for problem in parsed.problems] == [(1, 1), (2, 2)]
