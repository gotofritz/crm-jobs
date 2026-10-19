"""Moving the board in and out as rows of text — plan 005 §6, phases 3 to 5.

`transfer.py` works on dicts of strings, so none of this touches a file; the
commands' own tests cover that.
"""

import datetime as dt

import pytest

from jobs.demo import seed_demo
from jobs.models import Company, Contact, Employment, Lead, Note, Opportunity, Source, State, Step
from jobs.transfer import TABLES, Report, export_tables, import_tables

BOTH = pytest.mark.django_db(databases=["default", "demo"])


def as_input(
    tables: dict[str, list[dict[str, str]]],
) -> dict[str, list[tuple[int, dict[str, str]]]]:
    """What the reader hands over: each row with the line it came from."""
    return {name: list(enumerate(rows, start=2)) for name, rows in tables.items()}


def counts(using: str = "default") -> dict[str, int]:
    """Rows per model, in one database."""
    return {
        model.__name__: model.objects.using(using).count()
        for model in (Company, Contact, Employment, Opportunity, Step, Note)
    }


MINIMAL = {
    "opportunities": [{"company": "Initech", "title": "Engineer", "date": "2026-03-02"}],
}


@pytest.mark.usefixtures("demo_board")
def test_export_has_a_table_per_kind_of_row_with_its_columns() -> None:
    """Every table, every column, in the order the spec names them."""
    Lead.objects.create(name="Hacker News", url="https://news.ycombinator.com")
    tables = export_tables()

    assert set(tables) == set(TABLES)
    for name, rows in tables.items():
        assert rows, name
        assert list(rows[0]) == [*TABLES[name].required, *TABLES[name].optional], name


@pytest.mark.usefixtures("demo_board")
def test_export_points_at_rows_by_natural_key_never_by_id() -> None:
    """A step names its opportunity by company, title and date."""
    step = export_tables()["steps"][0]

    assert step["opportunity_company"]
    assert step["opportunity_title"]
    assert dt.date.fromisoformat(step["opportunity_date"])
    assert State.objects.filter(slug=step["state"]).exists()


@pytest.mark.usefixtures("demo_board")
def test_export_is_the_same_twice() -> None:
    """Ordering is by key, not by whatever the database returned."""
    assert export_tables() == export_tables()


@pytest.mark.usefixtures("demo_board")
def test_an_archived_opportunity_is_exported_with_its_date() -> None:
    """Live rows leave the cell empty."""
    stamps = [row["archived_at"] for row in export_tables()["opportunities"]]

    assert len([stamp for stamp in stamps if stamp]) == 1
    assert "" in stamps


@BOTH
def test_a_round_trip_into_an_empty_database_exports_the_same_tables() -> None:
    """Demo board → export → import into an empty database → export (plan 005 §1)."""
    seed_demo()
    Lead.objects.create(name="Older", url="https://a.example", notes="- first")
    Lead.objects.create(name="Newer", url="https://b.example")
    first = export_tables()
    assert counts("demo")["Opportunity"] == 0

    report = import_tables(as_input(first), using="demo")

    assert report.issues == []
    assert export_tables(using="demo") == first


@BOTH
def test_import_with_using_writes_nowhere_else() -> None:
    """`--demo` must not touch the live database."""
    import_tables(as_input(MINIMAL), using="demo")

    assert counts("demo")["Opportunity"] == 1
    assert counts()["Opportunity"] == 0


@pytest.mark.django_db
def test_a_hand_written_row_creates_the_opportunity_and_its_names() -> None:
    """Only the three key columns are needed; a new source is created as the board would."""
    rows = {"opportunities": [{**MINIMAL["opportunities"][0], "source": "Hacker News"}]}

    report = import_tables(as_input(rows))

    assert report.issues == []
    assert report.created["opportunities"] == 1
    opportunity = Opportunity.objects.get(title="Engineer")
    assert opportunity.company.name == "Initech"
    assert opportunity.source == Source.objects.get(name="Hacker News")
    assert not opportunity.steps.exists()


@pytest.mark.django_db
def test_an_archived_row_is_imported_archived() -> None:
    """`archived_at` survives, so an export restores the archive too."""
    row = {**MINIMAL["opportunities"][0], "archived_at": "2025-12-01T00:00:00+00:00"}

    import_tables(as_input({"opportunities": [row]}))

    assert Opportunity.objects.archived().count() == 1


@pytest.mark.django_db
def test_existing_rows_are_skipped_and_never_updated() -> None:
    """A stale file must not undo an edit made on the board since."""
    import_tables(
        as_input({"opportunities": [{**MINIMAL["opportunities"][0], "job_description": "old"}]})
    )
    Opportunity.objects.update(job_description="edited on the board")

    report = import_tables(
        as_input({"opportunities": [{**MINIMAL["opportunities"][0], "job_description": "old"}]})
    )

    assert report.created["opportunities"] == 0
    assert report.skipped["opportunities"] == 1
    assert Opportunity.objects.get().job_description == "edited on the board"


@pytest.mark.usefixtures("demo_board")
def test_importing_the_same_tables_twice_creates_nothing_the_second_time() -> None:
    """Everything is skipped, rows of every kind."""
    tables = export_tables()
    before = counts()

    report = import_tables(as_input(tables))

    assert report.issues == []
    assert sum(report.created.values()) == 0
    assert counts() == before


@pytest.mark.django_db
def test_every_problem_is_reported_with_its_line_and_column_and_nothing_is_written() -> None:
    """All or nothing: the good row above the bad ones is not kept."""
    rows = [
        {"company": "Initech", "title": "Good", "date": "2026-03-02"},
        {"company": "Initech", "title": "Bad date", "date": "next week"},
        {"company": "", "title": "No company", "date": "2026-03-04"},
    ]

    report = import_tables(as_input({"opportunities": rows}))

    assert [(i.table, i.line, i.column) for i in report.issues] == [
        ("opportunities", 3, "date"),
        ("opportunities", 4, "company"),
    ]
    assert counts()["Opportunity"] == 0
    assert not Company.objects.filter(name="Initech").exists()


@pytest.mark.django_db
def test_an_unknown_state_slug_is_a_problem_not_a_new_state() -> None:
    """States need a group and a rank, which is a decision in code."""
    step = {
        "opportunity_company": "Initech",
        "opportunity_title": "Engineer",
        "opportunity_date": "2026-03-02",
        "state": "made-up",
        "date": "2026-03-03",
        "title": "Call",
    }

    report = import_tables(as_input({**MINIMAL, "steps": [step]}))

    assert [(i.table, i.column) for i in report.issues] == [("steps", "state")]
    assert not State.objects.filter(slug="made-up").exists()


@pytest.mark.django_db
def test_a_step_whose_opportunity_is_nowhere_is_a_problem() -> None:
    """Neither in the files nor already on the board."""
    step = {
        "opportunity_company": "Nobody",
        "opportunity_title": "Nothing",
        "opportunity_date": "2026-03-02",
        "state": "unremarkable",
        "date": "2026-03-03",
        "title": "Call",
    }

    report = import_tables(as_input({"steps": [step]}))

    assert [(i.table, i.line, i.column) for i in report.issues] == [
        ("steps", 2, "opportunity_title")
    ]


@pytest.mark.django_db
def test_steps_notes_and_contacts_arrive_with_their_opportunity() -> None:
    """The whole set, written by hand, ends up as the board shows it."""
    key = {
        "opportunity_company": "Initech",
        "opportunity_title": "Engineer",
        "opportunity_date": "2026-03-02",
    }
    tables = {
        **MINIMAL,
        "companies": [{"name": "Initech", "url": "https://initech.example", "sector": "Fintech"}],
        "contacts": [
            {"name": "Ada Lovelace", "company": "Initech", "started_on": "2024-01-01"},
            {"name": "Ada Lovelace", "company": "Analytical Engines"},
        ],
        "steps": [
            {
                **key,
                "state": "unremarkable",
                "date": "2026-03-03",
                "time": "14:30",
                "title": "Call",
                "contacts": "Ada Lovelace, Grace Hopper",
                "comments": "- went well",
            },
        ],
        "notes": [
            {**key, "created_at": "2026-03-04T09:00:00+00:00", "body": "Seems fine"},
        ],
    }

    report = import_tables(as_input(tables))

    assert report.issues == []
    opportunity = Opportunity.objects.get()
    assert opportunity.company.url == "https://initech.example"
    assert opportunity.company.sector is not None
    assert Employment.objects.count() == 2
    step = Step.objects.get()
    assert step.time == dt.time(14, 30)
    assert step.contact_names == "Ada Lovelace, Grace Hopper"
    assert Note.objects.get().created_at == dt.datetime(2026, 3, 4, 9, tzinfo=dt.UTC)


@BOTH
def test_a_dry_run_reports_what_a_real_run_would_and_writes_nothing() -> None:
    """It is the real import, rolled back, so the preview cannot differ."""
    seed_demo()
    tables = as_input(export_tables())

    preview = import_tables(tables, using="demo", dry_run=True)
    assert counts("demo")["Opportunity"] == 0
    real = import_tables(tables, using="demo")

    assert preview.created == real.created
    assert preview.issues == real.issues == []
    assert isinstance(real, Report)


@pytest.mark.django_db
def test_leads_are_exported_oldest_first_so_an_import_keeps_their_order() -> None:
    """The sources page lists newest first, which is by id; an import recreates that."""
    Lead.objects.create(name="Older", url="https://a.example")
    Lead.objects.create(name="Newer", url="https://b.example")

    assert [row["name"] for row in export_tables()["leads"]] == ["Older", "Newer"]


@pytest.mark.django_db
def test_a_lead_is_imported_once_and_a_bad_url_is_a_problem() -> None:
    """Keyed on name and link; validated by the sources page's own form."""
    rows = {"leads": [{"name": "HN", "url": "https://news.ycombinator.com", "notes": "daily"}]}

    first = import_tables(as_input(rows))
    second = import_tables(as_input(rows))
    bad = import_tables(as_input({"leads": [{"name": "X", "url": "nope", "notes": ""}]}))

    assert (first.created["leads"], second.skipped["leads"]) == (1, 1)
    assert [(i.table, i.line, i.column) for i in bad.issues] == [("leads", 2, "url")]
    assert Lead.objects.count() == 1
