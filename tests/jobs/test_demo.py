"""The demo board — a dev convenience, and the one thing that writes rows nobody asked for.

`poe demo` rebuilds `demo.sqlite3` around `seed_demo`, so the rows never reach
the database anyone works in. What is left to check here is that the seed builds
a board worth looking at, that it does not stack a second one on the first, and
that the command will not run where DEBUG is off.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from pytest_django.fixtures import Settings

from jobs.demo import DEMO_COMPANIES, seed_demo
from jobs.models import Company, Contact, Opportunity, Step


def counts() -> tuple[int, int, int, int]:
    """The rows the demo writes."""
    return (
        Opportunity.objects.count(),
        Step.objects.count(),
        Company.objects.count(),
        Contact.objects.count(),
    )


@pytest.mark.usefixtures("db")
def test_seeding_builds_a_board() -> None:
    """Enough rows, and enough different states, to see whether the board works."""
    seed_demo()

    assert Opportunity.objects.live().count() == len(DEMO_COMPANIES) - 1
    assert Opportunity.objects.archived().count() == 1
    assert Step.objects.values("state").distinct().count() >= 6


@pytest.mark.usefixtures("db")
def test_one_row_runs_long_enough_to_scroll() -> None:
    """The sticky summary and per-row scroll in §7 only show on a row with steps to spare."""
    seed_demo()

    longest = max(row.steps.count() for row in Opportunity.objects.all())

    assert longest >= 6


@pytest.mark.usefixtures("db")
def test_seeding_twice_changes_nothing() -> None:
    """Every write is keyed on what identifies the row, so a second run is a no-op."""
    seed_demo()
    after_once = counts()

    seed_demo()

    assert counts() == after_once


@pytest.mark.usefixtures("db")
def test_the_command_seeds(settings: Settings) -> None:
    """`manage.py seed_demo` is the step `poe demo` runs after rebuilding the database.

    DEBUG is off under pytest, which is the same guard the VPS trips, so this has
    to turn it on to get at the command at all.
    """
    settings.DEBUG = True

    call_command("seed_demo")

    assert Opportunity.objects.count() == len(DEMO_COMPANIES)


@pytest.mark.usefixtures("db")
def test_the_command_refuses_to_run_in_production(settings: Settings) -> None:
    """Demo rows in the real database are exactly what the VPS does not want."""
    settings.DEBUG = False

    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo")

    assert not Opportunity.objects.exists()


def test_the_board_renders_the_demo(demo_board: list[Opportunity]) -> None:
    """The fixture exists so a test can look at a full board, not a two-row one."""
    html = Client().get("/").content.decode()

    for opportunity in demo_board:
        assert opportunity.title in html

    assert f"{len(demo_board)} live, 1 archived" in html
