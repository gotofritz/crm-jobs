"""`export_tsv` and `import_tsv` — plan 005 §6, phases 3 to 5.

The commands only read arguments, touch files and print the report; what is
imported and why is `test_transfer.py`'s business.
"""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from jobs.demo import seed_demo
from jobs.models import Company, Opportunity
from jobs.transfer import TABLES

BOTH = pytest.mark.django_db(databases=["default", "demo"])


def run(command: str, *args: str) -> str:
    """Run a command and return what it printed."""
    out = StringIO()
    call_command(command, *args, stdout=out)
    return out.getvalue()


def write(folder: Path, name: str, text: str) -> None:
    """Drop one hand-written file into a folder."""
    (folder / f"{name}.tsv").write_text(text, encoding="utf-8")


@pytest.mark.usefixtures("demo_board")
def test_export_writes_one_file_per_table(tmp_path: Path) -> None:
    """In a directory it creates, each with a header row."""
    target = tmp_path / "backup"

    run("export_tsv", str(target))

    assert sorted(path.name for path in target.iterdir()) == sorted(f"{n}.tsv" for n in TABLES)
    header = (target / "steps.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert header.split("\t")[:3] == [
        "opportunity_company",
        "opportunity_title",
        "opportunity_date",
    ]


@pytest.mark.usefixtures("demo_board")
def test_export_refuses_to_overwrite_a_previous_one(tmp_path: Path) -> None:
    """A backup directory is not silently replaced."""
    run("export_tsv", str(tmp_path))

    with pytest.raises(CommandError, match="already"):
        run("export_tsv", str(tmp_path))


@BOTH
def test_export_demo_reads_the_demo_database(tmp_path: Path) -> None:
    """The default database is empty here, so any rows came from `demo`."""
    seed_demo()
    assert Opportunity.objects.using("demo").count() == 0

    run("export_tsv", str(tmp_path), "--demo")

    assert Opportunity.objects.count() > 0
    assert Opportunity.objects.using("demo").count() == 0


@BOTH
def test_the_files_round_trip_byte_for_byte(tmp_path: Path) -> None:
    """Export, import into an empty database, export again: the same files (plan 005 §1)."""
    seed_demo()
    first, second = tmp_path / "first", tmp_path / "second"
    run("export_tsv", str(first))

    report = run("import_tsv", str(first), "--demo")
    run("export_tsv", str(second), "--demo")

    assert "created" in report
    for name in TABLES:
        assert (first / f"{name}.tsv").read_bytes() == (second / f"{name}.tsv").read_bytes(), name


@pytest.mark.django_db
def test_import_reads_a_directory_with_only_the_files_it_has(tmp_path: Path) -> None:
    """A hand-written `opportunities.tsv` is all that is needed."""
    write(tmp_path, "opportunities", "company\ttitle\tdate\nInitech\tEngineer\t2026-03-02\n")

    output = run("import_tsv", str(tmp_path))

    assert Opportunity.objects.get().title == "Engineer"
    assert "opportunities: 1 created, 0 skipped" in output


@pytest.mark.django_db
def test_a_second_import_reports_everything_skipped(tmp_path: Path) -> None:
    """The report says what was skipped as well as what was made."""
    write(tmp_path, "opportunities", "company\ttitle\tdate\nInitech\tEngineer\t2026-03-02\n")
    run("import_tsv", str(tmp_path))

    output = run("import_tsv", str(tmp_path))

    assert "opportunities: 0 created, 1 skipped" in output


@pytest.mark.django_db
def test_dry_run_prints_the_report_and_writes_nothing(tmp_path: Path) -> None:
    """The preview is the real import, rolled back."""
    write(tmp_path, "opportunities", "company\ttitle\tdate\nInitech\tEngineer\t2026-03-02\n")

    output = run("import_tsv", str(tmp_path), "--dry-run")

    assert "opportunities: 1 created" in output
    assert "dry run" in output.lower()
    assert not Company.objects.exists()


@pytest.mark.django_db
def test_every_problem_is_listed_with_file_line_and_column(tmp_path: Path) -> None:
    """One failure, all the problems, and nothing written."""
    write(
        tmp_path,
        "opportunities",
        "company\ttitle\tdate\nInitech\tGood\t2026-03-02\nInitech\tBad\tnot-a-date\n",
    )
    write(
        tmp_path,
        "notes",
        "opportunity_company\topportunity_title\topportunity_date\tbody\n"
        "Initech\tGood\t2026-03-02\tfine\nInitech\tMissing\t2026-03-02\tlost\n",
    )

    with pytest.raises(CommandError) as raised:
        run("import_tsv", str(tmp_path))

    message = str(raised.value)
    assert "opportunities.tsv:3 [date]" in message
    assert "notes.tsv:3 [opportunity_title]" in message
    assert not Opportunity.objects.exists()


@pytest.mark.django_db
def test_a_bad_header_stops_before_anything_is_imported(tmp_path: Path) -> None:
    """With the columns wrong every row would be, so only the header is reported."""
    write(tmp_path, "opportunities", "company\ttitle\nInitech\tEngineer\n")

    with pytest.raises(CommandError, match=r"opportunities.tsv:1 \[date\]: required column"):
        run("import_tsv", str(tmp_path))

    assert not Opportunity.objects.exists()


@pytest.mark.django_db
def test_a_cp1252_file_is_read_and_said_so(tmp_path: Path) -> None:
    """A LibreOffice re-save on Windows must not be refused."""
    (tmp_path / "opportunities.tsv").write_bytes(
        "company\ttitle\tdate\nCaf\xe9 Ltd\tEngineer\t2026-03-02\n".encode("cp1252")
    )

    output = run("import_tsv", str(tmp_path))

    assert Company.objects.get().name == "Café Ltd"
    assert "opportunities.tsv is not UTF-8" in output


@pytest.mark.django_db
def test_a_directory_with_no_tsv_files_is_an_error(tmp_path: Path) -> None:
    """Typing the wrong path should not look like a successful empty import."""
    with pytest.raises(CommandError, match=r"no \.tsv files"):
        run("import_tsv", str(tmp_path))


@pytest.mark.django_db
def test_a_directory_that_does_not_exist_is_an_error(tmp_path: Path) -> None:
    """Said plainly rather than as a traceback."""
    with pytest.raises(CommandError, match="not a directory"):
        run("import_tsv", str(tmp_path / "nope"))
