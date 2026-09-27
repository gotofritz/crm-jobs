"""`manage.py import_opportunities` — plan 004 §7, Phase 4.

The work is tested in `test_import_opportunities.py`; these are about the
command around it: its arguments, its refusals and its report. The sample file
in `fixtures/` doubles as a worked example of the format.
"""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from jobs.models import Company, Opportunity, State, Step
from jobs.opportunity_csv import COLUMNS

SAMPLE = Path(__file__).parent / "fixtures" / "opportunities.csv"


def run(*args: str, stdin: StringIO | None = None) -> str:
    """Call the command and return what it printed."""
    out = StringIO()
    options = {"stdin": stdin} if stdin is not None else {}
    call_command("import_opportunities", *args, stdout=out, **options)
    return out.getvalue()


def test_the_template_is_the_header_row() -> None:
    """`--template > new.csv` starts a file the command will accept."""
    assert run("--template") == ",".join(COLUMNS) + "\n"


def test_a_file_is_needed_without_the_template_flag() -> None:
    """Nothing to import is a mistake, not an empty run."""
    with pytest.raises(CommandError, match="file"):
        run()


@pytest.mark.usefixtures("db")
def test_the_sample_file_lands_on_the_board() -> None:
    """The worked example imports cleanly, and the report says so."""
    printed = run(str(SAMPLE))

    assert Opportunity.objects.count() == 2
    assert "created 2" in printed
    assert "line 2: Staff Engineer at Northwind Analytics, 2026-09-24" in printed
    assert "default database" in printed


@pytest.mark.usefixtures("db")
def test_a_second_run_lists_what_it_skipped() -> None:
    """A re-run is visibly a no-op (I5)."""
    run(str(SAMPLE))

    printed = run(str(SAMPLE))

    assert "created 0" in printed
    assert "skipped 2" in printed
    assert Opportunity.objects.count() == 2


@pytest.mark.usefixtures("db")
def test_a_dry_run_writes_nothing_and_says_what_it_would_do() -> None:
    """`--dry-run` costs nothing, so it can be run first every time."""
    printed = run(str(SAMPLE), "--dry-run")

    assert "would create 2" in printed
    assert "\nwould create:" in printed
    assert "\ncreated:" not in printed
    assert not Opportunity.objects.exists()
    assert not Company.objects.filter(name="Contoso").exists()


@pytest.mark.django_db(databases=["default", "demo"])
def test_the_demo_flag_writes_to_the_demo_database_only() -> None:
    """I8, from the command line."""
    printed = run(str(SAMPLE), "--demo")

    assert Opportunity.objects.using("demo").count() == 2
    assert not Opportunity.objects.using("default").exists()
    assert "demo database" in printed


@pytest.mark.usefixtures("db")
def test_stdin_is_read_when_the_path_is_a_dash() -> None:
    """So the command composes with whatever produced the file."""
    run("-", stdin=StringIO(SAMPLE.read_text()))

    assert Opportunity.objects.count() == 2


@pytest.mark.usefixtures("db")
def test_every_problem_is_printed_and_nothing_is_written(tmp_path: Path) -> None:
    """Structural and per-row problems alike, all in one error (I4)."""
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "company,title,date,sorce\nNorthwind,Staff Engineer,2026-09-24,\nContoso,,not a date,\n"
    )

    with pytest.raises(CommandError) as refused:
        run(str(bad))

    message = str(refused.value)
    assert "line 1, sorce: unknown column" in message
    assert "line 3, title:" in message
    assert "line 3, date:" in message
    assert not Opportunity.objects.exists()


@pytest.mark.usefixtures("db")
def test_a_missing_file_is_named(tmp_path: Path) -> None:
    """A typo in the path is not a reason to import nothing and say it worked."""
    with pytest.raises(CommandError, match=r"nothing\.csv"):
        run(str(tmp_path / "nothing.csv"))


@pytest.mark.usefixtures("db")
def test_a_database_with_no_states_is_refused() -> None:
    """Every created row needs `unremarkable` for its first step."""
    Step.objects.all().delete()
    State.objects.all().delete()

    with pytest.raises(CommandError, match="migrate"):
        run(str(SAMPLE))


@pytest.mark.usefixtures("db")
def test_a_missing_column_is_said_once_not_once_per_row(tmp_path: Path) -> None:
    """Without a `date` header every row lacks a date, and saying so per row is noise."""
    bad = tmp_path / "bad.csv"
    bad.write_text("company,title\nNorthwind,Staff Engineer\nContoso,Backend Developer\n")

    with pytest.raises(CommandError) as refused:
        run(str(bad))

    assert str(refused.value).count("date") == 1
