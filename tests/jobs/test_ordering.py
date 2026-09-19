"""Ordering rules ported from the GAS app — plan 001 §4.5.

Every rule is checked without a database — that is what the rules being pure
functions buys. The `in_board_order` and `in_archive_order` tests are the only
ones that need one (§6.3).
"""

import datetime as dt

import pytest
from django.utils import timezone
from pytest_django.fixtures import DjangoAssertNumQueries

from jobs.models import Company, Group, Opportunity, State, Step
from jobs.ordering import (
    GROUP_RANK,
    UNRANKED,
    group_rank,
    opportunity_sort_key,
    sort_steps,
    top_step,
)


def make_step(
    *,
    group: str,
    sort_order: int = 1,
    date: str = "2026-01-01",
    time: str | None = None,
    title: str = "",
) -> Step:
    """An unsaved step built from the four things §4.5 keys on."""
    return Step(
        state=State(
            slug=f"state-{sort_order}",
            name=f"STATE_{sort_order}",
            group=group,
            sort_order=sort_order,
        ),
        date=dt.date.fromisoformat(date),
        time=dt.time.fromisoformat(time) if time else None,
        title=title,
    )


def add_step(opportunity: Opportunity, *, slug: str, date: str) -> Step:
    """A saved step in one of the seeded states (§6.1)."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug=slug),
        date=dt.date.fromisoformat(date),
    )


def add_opportunity(company: Company, *, title: str) -> Opportunity:
    """A live opportunity, named so the assertions read as an order."""
    return Opportunity.objects.create(company=company, title=title, date=dt.date(2026, 1, 5))


def key_for(case: tuple[str, int, str]) -> tuple[int, int, int, float]:
    """The opportunity key for a top step given as (group, state position, date)."""
    group, sort_order, date = case
    return opportunity_sort_key(make_step(group=group, sort_order=sort_order, date=date))


def test_group_rank_puts_attention_above_due_above_complete() -> None:
    """§4.5 ranks the three groups 3, 2, 1."""
    assert GROUP_RANK[Group.ATTENTION] == 3
    assert GROUP_RANK[Group.DUE] == 2
    assert GROUP_RANK[Group.COMPLETE] == 1


def test_group_rank_covers_every_group() -> None:
    """Adding a group means deciding where it ranks, so drift has to fail loudly (§6.1)."""
    assert set(GROUP_RANK) == set(Group.values)


def test_an_unknown_group_is_unranked() -> None:
    """§4.5: anything else ranks -1, below every known group."""
    assert group_rank("MYSTERY") == UNRANKED


@pytest.mark.parametrize(
    ("unsorted", "expected"),
    [
        pytest.param(["COMPLETE", "ATTENTION", "DUE"], ["ATTENTION", "DUE", "COMPLETE"], id="all"),
        pytest.param(["DUE", "ATTENTION"], ["ATTENTION", "DUE"], id="attention over due"),
        pytest.param(["COMPLETE", "DUE"], ["DUE", "COMPLETE"], id="due over complete"),
        pytest.param(["MYSTERY", "COMPLETE"], ["COMPLETE", "MYSTERY"], id="known over unknown"),
    ],
)
def test_steps_sort_by_group_rank_descending(unsorted: list[str], expected: list[str]) -> None:
    """§4.5 rule 1 for steps: the most urgent group comes first."""
    steps = [make_step(group=group) for group in unsorted]

    assert [step.state.group for step in sort_steps(steps)] == expected


def test_steps_tie_break_on_timestamp_ascending() -> None:
    """§4.5 rule 2: inside a group, oldest first — the most overdue is the most urgent (§6.2)."""
    late = make_step(group=Group.DUE, date="2026-03-02")
    early = make_step(group=Group.DUE, date="2026-03-01")

    assert sort_steps([late, early]) == [early, late]


def test_complete_steps_tie_break_on_timestamp_descending() -> None:
    """§4.5 rule 2 inverted: nothing is pending, so newest-touched first (§6.2)."""
    old = make_step(group=Group.COMPLETE, date="2026-03-01")
    recent = make_step(group=Group.COMPLETE, date="2026-03-02")

    assert sort_steps([old, recent]) == [recent, old]


def test_steps_tie_break_on_the_time_as_well_as_the_date() -> None:
    """§4.5 keys on `date` + `time`, not on the date alone."""
    evening = make_step(group=Group.DUE, date="2026-03-01", time="18:00")
    morning = make_step(group=Group.DUE, date="2026-03-01", time="09:00")

    assert sort_steps([evening, morning]) == [morning, evening]


def test_a_step_with_no_time_counts_as_midnight() -> None:
    """The GAS app stored ':' for an empty time and parsed it as the start of the day (§4.5)."""
    timed = make_step(group=Group.DUE, date="2026-03-01", time="00:01")
    untimed = make_step(group=Group.DUE, date="2026-03-01")

    assert sort_steps([timed, untimed]) == [untimed, timed]


def test_steps_with_equal_timestamps_keep_their_input_order() -> None:
    """Nothing is left to sort on, so the sort is stable rather than arbitrary (§4.5)."""
    first = make_step(group=Group.DUE, date="2026-03-01", time="09:00", title="first")
    second = make_step(group=Group.DUE, date="2026-03-01", time="09:00", title="second")

    assert [step.title for step in sort_steps([first, second])] == ["first", "second"]
    assert [step.title for step in sort_steps([second, first])] == ["second", "first"]


def test_top_step_is_the_one_sorting_first() -> None:
    """An opportunity is keyed on the step §4.5 leaves at the front (§4.5, `Pool`)."""
    complete = make_step(group=Group.COMPLETE)
    attention = make_step(group=Group.ATTENTION)

    assert top_step([complete, attention]) is attention


def test_top_step_of_an_opportunity_with_no_steps_is_none() -> None:
    """Nothing has happened yet, and §4.5 rule 1 has a place for that."""
    assert top_step([]) is None


def test_an_opportunity_with_no_steps_sorts_before_every_other() -> None:
    """§4.5 rule 1 for opportunities: no steps sorts first."""
    assert opportunity_sort_key(None) < opportunity_sort_key(make_step(group=Group.ATTENTION))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param(
            (Group.ATTENTION, 9, "2026-06-01"),
            (Group.DUE, 1, "2026-01-01"),
            id="rule 2: group rank outranks position and date",
        ),
        pytest.param(
            (Group.COMPLETE, 5, "2026-01-01"),
            (Group.COMPLETE, 6, "2026-06-01"),
            id="rule 3: position breaks a group tie, ascending",
        ),
        pytest.param(
            (Group.DUE, 3, "2026-01-01"),
            (Group.DUE, 3, "2026-06-01"),
            id="rule 4: date breaks a position tie, ascending",
        ),
        pytest.param(
            (Group.COMPLETE, 5, "2026-06-01"),
            (Group.COMPLETE, 5, "2026-01-01"),
            id="rule 4 inverted: COMPLETE reads newest first",
        ),
        pytest.param(
            (Group.COMPLETE, 9, "2026-01-01"),
            ("MYSTERY", 1, "2026-01-01"),
            id="an unknown group sorts last",
        ),
    ],
)
def test_opportunity_sort_key_applies_each_rule_in_turn(
    first: tuple[str, int, str], second: tuple[str, int, str]
) -> None:
    """§4.5 for opportunities, one case per rule, keyed on the top step."""
    assert key_for(first) < key_for(second)


def test_in_board_order_applies_the_rules_end_to_end(company: Company) -> None:
    """The queryset method is the board's one ordering entry point (§4.5)."""
    add_opportunity(company, title="stepless")
    overdue = add_opportunity(company, title="overdue")
    add_step(overdue, slug="overdue", date="2026-02-01")
    due = add_opportunity(company, title="due")
    add_step(due, slug="due", date="2026-01-01")
    accepted = add_opportunity(company, title="accepted")
    add_step(accepted, slug="accepted", date="2026-01-01")
    ghosted = add_opportunity(company, title="ghosted")
    add_step(ghosted, slug="ghosted", date="2026-05-01")

    ordered = Opportunity.objects.live().in_board_order()

    assert [row.title for row in ordered] == ["stepless", "overdue", "due", "accepted", "ghosted"]


def test_in_board_order_keys_an_opportunity_on_its_top_step(company: Company) -> None:
    """The key is the step §4.5 sorts to the front, not the newest one (§4.5, `Pool`)."""
    calm = add_opportunity(company, title="calm")
    add_step(calm, slug="going-well", date="2026-06-01")
    alarmed = add_opportunity(company, title="alarmed")
    add_step(alarmed, slug="going-well", date="2026-06-02")
    add_step(alarmed, slug="error", date="2026-01-01")

    ordered = Opportunity.objects.live().in_board_order()

    assert [row.title for row in ordered] == ["alarmed", "calm"]


def test_in_board_order_loads_steps_and_states_up_front(
    company: Company, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """Prefetching is what stops the sort reaching back into the database per row (§4.5)."""
    for title in ("first", "second", "third"):
        opportunity = add_opportunity(company, title=title)
        add_step(opportunity, slug="due", date="2026-01-01")

    with django_assert_num_queries(3):
        assert [
            row.steps.all()[0].state.name for row in Opportunity.objects.live().in_board_order()
        ] == ["DUE", "DUE", "DUE"]


def test_in_archive_order_is_most_recently_archived_first(company: Company) -> None:
    """Urgency is meaningless once nothing is pending; which burst this was is not (§6.5)."""
    now = timezone.now()
    older = Opportunity.objects.create(
        company=company,
        title="older",
        date=dt.date(2026, 1, 2),
        archived_at=now - dt.timedelta(days=30),
    )
    newer = Opportunity.objects.create(
        company=company, title="newer", date=dt.date(2026, 1, 3), archived_at=now
    )

    assert list(Opportunity.objects.archived().in_archive_order()) == [newer, older]
