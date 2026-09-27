"""Validating and writing CSV rows through the board's form — plan 004 §3, Phase 3.

Rows are built with the real reader, so each test reads like the file it is
about. Everything here is on the `default` alias except the one test that is
about keeping off it.
"""

import datetime as dt

import pytest
from django.test import Client

from jobs.importer import Entry, import_opportunities
from jobs.models import Company, Opportunity, Sector, Step
from jobs.opportunity_csv import Problem, Row, read

HEADER = "company,title,date,source,contact,company_url,company_sector"
NORTHWIND = "Northwind Analytics,Staff Engineer,2026-09-24,LinkedIn,Maya Richardson,,"
CONTOSO = "Contoso,Backend Developer,25/09/2026,Referral,,,"


def rows(*lines: str, header: str = HEADER) -> tuple[Row, ...]:
    """A file's rows, read the way the command reads them, refusing a malformed one."""
    parsed = read("\n".join([header, *lines]) + "\n")
    assert parsed.problems == ()
    return parsed.rows


@pytest.mark.usefixtures("db")
def test_each_row_becomes_an_opportunity_at_its_company() -> None:
    """The example in §4, in the tables."""
    imported = import_opportunities(rows(NORTHWIND, CONTOSO), using="default")

    assert imported.problems == ()
    assert len(imported.created) == 2
    northwind = Opportunity.objects.get(company__name="Northwind Analytics")
    assert northwind.title == "Staff Engineer"
    assert northwind.date == dt.date(2026, 9, 24)
    assert northwind.source is not None
    assert northwind.source.name == "LinkedIn"


@pytest.mark.usefixtures("db")
def test_each_opportunity_opens_with_a_first_step_carrying_its_contact() -> None:
    """I3: the same first step the board gives a new row."""
    import_opportunities(rows(NORTHWIND), using="default")

    step = Step.objects.get()
    assert step.state.slug == "unremarkable"
    assert step.date == dt.date(2026, 9, 24)
    assert step.contact_names == "Maya Richardson"


@pytest.mark.usefixtures("db")
def test_an_imported_row_is_live_and_on_the_board() -> None:
    """I7: nothing is archived on the way in."""
    import_opportunities(rows(NORTHWIND), using="default")

    assert Opportunity.objects.get().archived_at is None
    assert "Northwind Analytics" in Client().get("/").content.decode()


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize(
    ("line", "column"),
    [
        ("Northwind Analytics,Staff Engineer,not a date,,,,", "date"),
        ("Northwind Analytics,Staff Engineer,2026-09-24,,,not a url,", "company_url"),
        ("Northwind Analytics,,2026-09-24,,,,", "title"),
        (",Staff Engineer,2026-09-24,,,,", "company"),
    ],
)
def test_a_bad_value_is_reported_by_line_and_column(line: str, column: str) -> None:
    """The form's own message, placed where the file can be fixed."""
    imported = import_opportunities(rows(CONTOSO, line), using="default")

    assert [(problem.line, problem.column) for problem in imported.problems] == [(3, column)]


@pytest.mark.usefixtures("db")
def test_one_bad_row_writes_nothing_at_all() -> None:
    """I4: not the good rows, and not the companies they would have created."""
    imported = import_opportunities(
        rows(NORTHWIND, "Contoso,Backend Developer,not a date,,,,"), using="default"
    )

    assert imported.created == ()
    assert not Opportunity.objects.exists()
    assert not Company.objects.exists()


@pytest.mark.usefixtures("db")
def test_a_second_run_creates_nothing_and_skips_every_row() -> None:
    """I5: re-running a file is visibly a no-op."""
    import_opportunities(rows(NORTHWIND, CONTOSO), using="default")

    again = import_opportunities(rows(NORTHWIND, CONTOSO), using="default")

    assert again.created == ()
    assert len(again.skipped) == 2
    assert Opportunity.objects.count() == 2


@pytest.mark.usefixtures("db")
def test_an_existing_row_is_skipped_not_updated() -> None:
    """A stale file must not revert what was edited on the board since (I5)."""
    import_opportunities(rows(NORTHWIND), using="default")
    Opportunity.objects.update(job_description="edited on the board")

    import_opportunities(
        rows(NORTHWIND + ",an old ad", header=f"{HEADER},job_description"), using="default"
    )

    assert Opportunity.objects.get().job_description == "edited on the board"


@pytest.mark.usefixtures("db")
def test_an_existing_row_matches_its_company_whatever_the_case() -> None:
    """The key is the company, not its spelling in this file."""
    import_opportunities(rows(NORTHWIND), using="default")

    again = import_opportunities(rows(NORTHWIND.replace("Northwind", "NORTHWIND")), using="default")

    assert len(again.skipped) == 1


@pytest.mark.usefixtures("db")
def test_the_same_row_twice_in_one_file_is_a_problem() -> None:
    """The file is contradicting itself, which is not the same as a re-run."""
    imported = import_opportunities(rows(NORTHWIND, CONTOSO, NORTHWIND), using="default")

    assert imported.problems == (
        Problem(line=4, column="", reason="same company, title and date as line 2"),
    )
    assert not Opportunity.objects.exists()


@pytest.mark.usefixtures("db")
def test_a_sector_in_another_case_finds_the_stored_one() -> None:
    """`FINTECH` is the seeded `Fintech`, not a second sector (§6.9 of plan 001)."""
    before = Sector.objects.count()

    import_opportunities(rows(NORTHWIND + "FINTECH"), using="default")

    assert Sector.objects.count() == before
    assert Company.objects.get().sector == Sector.objects.get(name="Fintech")


@pytest.mark.usefixtures("db")
def test_a_blank_detail_leaves_what_the_company_has() -> None:
    """A CSV never clears a company's URL by leaving the cell empty."""
    Company.objects.create(name="Northwind Analytics", url="https://northwind.example")

    import_opportunities(rows(NORTHWIND), using="default")

    assert Company.objects.get().url == "https://northwind.example"


@pytest.mark.usefixtures("db")
def test_a_british_date_is_read_day_first() -> None:
    """`LANGUAGE_CODE` is en-gb, so 25/09/2026 is the 25th of September."""
    import_opportunities(rows(CONTOSO), using="default")

    assert Opportunity.objects.get().date == dt.date(2026, 9, 25)


@pytest.mark.usefixtures("db")
def test_an_american_date_is_refused_rather_than_misread() -> None:
    """09/26/2026 has no 26th month, so it cannot be quietly read as something else."""
    imported = import_opportunities(rows(CONTOSO.replace("25/09", "09/26")), using="default")

    assert [problem.column for problem in imported.problems] == ["date"]


@pytest.mark.usefixtures("db")
def test_a_dry_run_says_what_a_real_run_would_and_writes_nothing() -> None:
    """Worked out by doing it and rolling it back, so the two cannot differ."""
    import_opportunities(rows(CONTOSO), using="default")
    companies = Company.objects.count()

    dry = import_opportunities(rows(NORTHWIND, CONTOSO), using="default", dry_run=True)

    assert (len(dry.created), len(dry.skipped)) == (1, 1)
    assert Opportunity.objects.count() == 1
    assert Company.objects.count() == companies


@pytest.mark.django_db(databases=["default", "demo"])
def test_an_import_into_demo_leaves_the_live_database_alone() -> None:
    """I8, end to end."""
    import_opportunities(rows(NORTHWIND), using="demo")

    assert Opportunity.objects.using("demo").count() == 1
    assert Step.objects.using("demo").count() == 1
    assert not Opportunity.objects.using("default").exists()
    assert not Company.objects.using("default").exists()


def test_a_row_reads_as_its_line_title_company_and_date() -> None:
    """What the command lists for each created and skipped row."""
    entry = Entry(line=2, company="Contoso", title="Backend Developer", date=dt.date(2026, 9, 25))

    assert str(entry) == "line 2: Backend Developer at Contoso, 2026-09-25"
