"""The picklists a fresh database ships with — plan 001 §6.1 and §6.10."""

import pytest

from jobs.models import Group, Sector, Source, State

SEEDED_STATES = [
    (1, Group.ATTENTION, "Error", "error"),
    (2, Group.ATTENTION, "Overdue", "overdue"),
    (3, Group.DUE, "Due", "due"),
    (4, Group.DUE, "Tentative", "tentative"),
    (5, Group.COMPLETE, "Accepted", "accepted"),
    (6, Group.COMPLETE, "Success", "success"),
    (7, Group.COMPLETE, "Bad Feeling", "bad-feeling"),
    (8, Group.COMPLETE, "Going Well", "going-well"),
    (9, Group.COMPLETE, "", "unremarkable"),
    (10, Group.COMPLETE, "Ghosted", "ghosted"),
    (11, Group.COMPLETE, "Fail", "fail"),
    (12, Group.COMPLETE, "Blacklist", "blacklist"),
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


@pytest.mark.usefixtures("db")
def test_no_state_name_reads_like_a_sheet_header() -> None:
    """`name` is printed on a card, so it is words, not the sheet's column label (§6.1).

    The key everything looks up and styles on is `slug`, which keeps the
    machine-readable form. A name that goes back to SCREAMING_SNAKE fails here.
    """
    named = [name for name in State.objects.values_list("name", flat=True) if name]

    assert [name for name in named if "_" in name] == []
    assert [name for name in named if name == name.upper()] == []


@pytest.mark.usefixtures("db")
def test_unremarkable_has_nothing_to_say() -> None:
    """The default state means nothing notable happened, so the card prints nothing (§6.6).

    Empty in the data rather than hidden in the template: what a state is called
    is the state's business, and the template only prints what it is given (§6.3).
    """
    assert State.objects.get(slug="unremarkable").name == ""
    assert State.objects.exclude(slug="unremarkable").filter(name="").count() == 0
