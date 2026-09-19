"""The picklists a fresh database ships with — plan 001 §6.1 and §6.10."""

import pytest

from jobs.models import Group, Sector, Source, State

SEEDED_STATES = [
    (1, Group.ATTENTION, "ERROR", "error"),
    (2, Group.ATTENTION, "OVERDUE", "overdue"),
    (3, Group.DUE, "DUE", "due"),
    (4, Group.DUE, "TENTATIVE", "tentative"),
    (5, Group.COMPLETE, "ACCEPTED", "accepted"),
    (6, Group.COMPLETE, "SUCCESS", "success"),
    (7, Group.COMPLETE, "BAD_FEELING", "bad-feeling"),
    (8, Group.COMPLETE, "GOING_WELL", "going-well"),
    (9, Group.COMPLETE, "UNREMARKABLE", "unremarkable"),
    (10, Group.COMPLETE, "GHOSTED", "ghosted"),
    (11, Group.COMPLETE, "FAIL", "fail"),
    (12, Group.COMPLETE, "BLACKLIST", "blacklist"),
]


@pytest.mark.usefixtures("db")
def test_the_twelve_states_are_seeded_in_sheet_order() -> None:
    """Taken from the live sheet header row, in column order (§6.1)."""
    seeded = [
        (state.sort_order, state.group, state.name, state.slug)
        for state in State.objects.order_by("sort_order")
    ]

    assert seeded == SEEDED_STATES


@pytest.mark.usefixtures("db")
def test_a_new_opportunity_can_land_in_unremarkable() -> None:
    """DEFAULT_STEP_STATE is UNREMARKABLE, ninth of twelve (§6.6)."""
    state = State.objects.get(slug="unremarkable")

    assert state.group == Group.COMPLETE
    assert state.sort_order == 9


@pytest.mark.usefixtures("db")
def test_starter_sources_are_seeded() -> None:
    """A picklist, not a fixed vocabulary — new ones are typed in (§6.10)."""
    names = set(Source.objects.values_list("name", flat=True))

    assert {"LinkedIn", "Wellfound", "Referral", "Direct", "Recruiter"} <= names


@pytest.mark.usefixtures("db")
def test_starter_sectors_are_seeded() -> None:
    """The sectors listed in §6.10, extended by typing."""
    names = set(Sector.objects.values_list("name", flat=True))

    assert {"AI / ML", "Fintech", "SaaS", "Government / public sector", "Other"} <= names
    assert Sector.objects.count() == 18
