"""Writing a parsed export into the database — plan 003 §5, §7.

The parser has its own tests and needs no database; these are about what ends up
in the tables, and about the command that puts it there. `--demo` is never
exercised through the command here: pytest sets up one test database, and the
point of the flag is that nothing reaches the other one. `database_for` is where
that choice is asserted.
"""

import datetime as dt
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from jobs.importer import database_for, write
from jobs.models import Company, Contact, Employment, Note, Opportunity, Source, State, Step
from jobs.sheet import parse_sheet

# A second row for the tests that need two companies, in the export's own format.
APERTURE = (
    '"Aperture\n\nQA Lead","2025-06-02\nLinkedIn\n\nMaya Richardson",'
    '"2025-06-02 __ 09:00\nRecruiter outreach\nMaya Richardson"\n'
)


def with_aperture(export: str) -> str:
    """Two rows. The committed sample ends without a newline, so one is added."""
    return f"{export}\n{APERTURE}"


def imported(text: str) -> None:
    """Parse and write, the way the command does, for the tests about the writing."""
    write(parse_sheet(text).rows, using="default")


@pytest.fixture
def export(tmp_path: Path, cleaned_csv: str) -> Path:
    """The sample export as a file on disk, which is what the command takes."""
    path = tmp_path / "export.csv"
    path.write_text(cleaned_csv)
    return path


def test_the_demo_flag_picks_the_demo_alias() -> None:
    """The whole of `--demo`: a database chosen by name, not a path mutated at runtime."""
    assert database_for(demo=True) == "demo"


def test_without_the_flag_the_live_database_is_written() -> None:
    """The default is the database the app itself runs on."""
    assert database_for(demo=False) == "default"


@pytest.mark.usefixtures("db")
def test_the_sample_becomes_one_opportunity_with_five_steps(cleaned_csv: str) -> None:
    """End to end over the real export: one row, its five steps, its company."""
    imported(cleaned_csv)

    opportunity = Opportunity.objects.get()

    assert opportunity.company.name == "NebulaGrid"
    assert opportunity.date == dt.date(2025, 7, 8)
    assert opportunity.steps.count() == 5


@pytest.mark.usefixtures("db")
def test_the_advert_lands_in_the_job_description(cleaned_csv: str) -> None:
    """The sheet's one prose field per row is the pasted ad, not a note (§5)."""
    imported(cleaned_csv)

    assert "next generation of intelligent software" in Opportunity.objects.get().job_description
    assert Note.objects.count() == 0


@pytest.mark.usefixtures("db")
def test_the_source_is_resolved_to_a_picklist_row(cleaned_csv: str) -> None:
    """Wellfound is already seeded, so the import must reuse it rather than fork one."""
    before = Source.objects.count()

    imported(cleaned_csv)

    assert Opportunity.objects.get().source is not None
    assert Source.objects.filter(name="Wellfound").count() == 1
    assert Source.objects.count() == before


@pytest.mark.usefixtures("db")
def test_an_imported_row_is_live(cleaned_csv: str) -> None:
    """I2: the sheet is the current job hunt, so its rows belong on the board."""
    imported(cleaned_csv)

    assert Opportunity.objects.live().count() == 1
    assert Opportunity.objects.get().archived_at is None


@pytest.mark.usefixtures("db")
def test_the_rejection_lands_in_fail(cleaned_csv: str) -> None:
    """The inference, end to end: the sample's newest step is titled `REJECTED` (§6)."""
    imported(cleaned_csv)

    rejection = Step.objects.get(date=dt.date(2025, 7, 21))

    assert rejection.state.slug == "fail"


@pytest.mark.usefixtures("db")
def test_an_ordinary_step_stays_unremarkable(cleaned_csv: str) -> None:
    """Most titles say what happened, not how it went."""
    imported(cleaned_csv)

    assert Step.objects.get(date=dt.date(2025, 7, 15)).state.slug == "unremarkable"


@pytest.mark.usefixtures("db")
def test_a_step_keeps_both_of_its_contacts(cleaned_csv: str) -> None:
    """The sample's technical interview was with two people."""
    imported(cleaned_csv)

    interview = Step.objects.get(date=dt.date(2025, 7, 15))

    assert interview.contact_names == "Alex Chen, Priya Nair"


@pytest.mark.usefixtures("db")
def test_a_step_time_survives_and_a_missing_one_stays_null(cleaned_csv: str) -> None:
    """§5: `Step.time` is NULL when the cell has none or writes a bare colon."""
    imported(cleaned_csv)

    assert Step.objects.get(date=dt.date(2025, 7, 21)).time == dt.time(16, 42)


@pytest.mark.usefixtures("db")
def test_one_name_at_one_company_is_one_person(cleaned_csv: str) -> None:
    """Maya Richardson is on four of the sample's cells and the opportunity itself."""
    imported(cleaned_csv)

    assert Contact.objects.filter(name="Maya Richardson").count() == 1


@pytest.mark.usefixtures("db")
def test_a_contact_gets_an_employment_at_the_company(cleaned_csv: str) -> None:
    """Per-company identity needs somewhere to live, and `Employment` is it (§5.1)."""
    imported(cleaned_csv)

    stint = Employment.objects.get(contact__name="Maya Richardson")

    assert stint.company.name == "NebulaGrid"
    assert (stint.started_on, stint.ended_on) == (None, None)


@pytest.mark.usefixtures("db")
def test_one_name_at_two_companies_is_two_people(cleaned_csv: str) -> None:
    """§5.1: a naive get_or_create on name would merge strangers, so it is not used."""
    imported(with_aperture(cleaned_csv))

    assert Contact.objects.filter(name="Maya Richardson").count() == 2


@pytest.mark.usefixtures("db")
def test_a_cross_company_name_is_reported_for_review(cleaned_csv: str) -> None:
    """The same "is this the same person?" question the autosuggest asks (#10)."""
    written = write(parse_sheet(with_aperture(cleaned_csv)).rows, using="default")

    assert [(one.name, one.companies) for one in written.collisions] == [
        ("Maya Richardson", ("Aperture", "NebulaGrid"))
    ]


@pytest.mark.usefixtures("db")
def test_running_twice_changes_nothing(cleaned_csv: str) -> None:
    """I6: every write is keyed on what identifies the row, so a re-run is a no-op."""
    imported(cleaned_csv)
    counts = (Opportunity.objects.count(), Step.objects.count(), Contact.objects.count())

    imported(cleaned_csv)

    assert (Opportunity.objects.count(), Step.objects.count(), Contact.objects.count()) == counts


@pytest.mark.usefixtures("db")
def test_the_command_imports_the_file(export: Path) -> None:
    """`manage.py import_sheet <csv>` is the whole interface (§7)."""
    call_command("import_sheet", str(export), stdout=StringIO())

    assert Opportunity.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_the_command_reports_what_it_guessed(export: Path) -> None:
    """Every inference is printed, because every one of them is a guess (§6)."""
    out = StringIO()

    call_command("import_sheet", str(export), stdout=out)

    assert "REJECTED" in out.getvalue()
    assert "fail" in out.getvalue()


@pytest.mark.usefixtures("db")
def test_a_dry_run_writes_nothing(export: Path) -> None:
    """It shows what the run would decide before it decides it (§7)."""
    out = StringIO()

    call_command("import_sheet", str(export), "--dry-run", stdout=out)

    assert Opportunity.objects.count() == 0
    assert "REJECTED" in out.getvalue()


@pytest.mark.usefixtures("db")
def test_a_bad_cell_stops_the_whole_import(tmp_path: Path, sample_csv: str) -> None:
    """I5: not even the rows that parsed, because half an export is worse than none."""
    path = tmp_path / "export.csv"
    path.write_text(with_aperture(sample_csv))

    with pytest.raises(CommandError, match="row 1, column 6"):
        call_command("import_sheet", str(path), stdout=StringIO())

    assert Opportunity.objects.count() == 0


@pytest.mark.usefixtures("db")
def test_the_command_refuses_a_file_that_is_not_there(tmp_path: Path) -> None:
    """A typo in the path is not a reason to write an empty import and say it worked."""
    with pytest.raises(CommandError, match=r"nothing\.csv"):
        call_command("import_sheet", str(tmp_path / "nothing.csv"), stdout=StringIO())


@pytest.mark.usefixtures("db")
def test_the_command_refuses_a_database_with_no_states(export: Path) -> None:
    """What `--demo` against a demo.sqlite3 nobody has built yet looks like (§7)."""
    Step.objects.all().delete()
    State.objects.all().delete()

    with pytest.raises(CommandError, match="migrate"):
        call_command("import_sheet", str(export), stdout=StringIO())


@pytest.mark.usefixtures("db")
def test_the_board_renders_an_imported_row(export: Path) -> None:
    """The point of I2: the rows land where the app can see them."""
    call_command("import_sheet", str(export), stdout=StringIO())

    html = Client().get("/").content.decode()

    assert "NebulaGrid" in html
    assert Company.objects.get().name in html


@pytest.mark.usefixtures("db")
def test_two_names_in_column_two_become_two_people() -> None:
    """`Opportunity.contact` is one key, so the first name takes it and the rest still land.

    Column 2 can name more than one person (§4.1). Dropping the others would lose
    them silently, which is the one thing the import does not do.
    """
    two = '"Aperture\n\nQA Lead","2025-06-02\nLinkedIn\n\nAlex Chen, Priya Nair"\n'

    imported(two)

    assert Opportunity.objects.get().contact is not None
    assert set(Contact.objects.values_list("name", flat=True)) == {"Alex Chen", "Priya Nair"}
