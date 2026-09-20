"""Changing a step's state re-renders its row — plan 001 §4.5, §6.3.

A value usually swaps itself and nothing else, which is the cheapest correct
swap. A step's state is not usually: the card's colour comes from `data-state`
on the card, and the card's place in the track comes from the state's group
(§4.5). Swap the value alone and both go stale — the card keeps the old colour
and stays where it was until the page is reloaded.

So a step's field answers with the row. The board still answers for itself when
the change moved rows about, which a state can also do.
"""

import datetime as dt
import re

import pytest
from django.test import Client

from jobs.models import Company, Note, Opportunity, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def track(opportunity: Opportunity) -> list[Step]:
    """Two steps whose order depends on their groups.

    `overdue` is ATTENTION and `unremarkable` is COMPLETE, so the first leads
    however the dates fall.
    """
    return [
        Step.objects.create(
            opportunity=opportunity,
            state=State.objects.get(slug=slug),
            date=dt.date.fromisoformat(day),
            title=slug,
        )
        for slug, day in (("overdue", "2026-02-10"), ("unremarkable", "2026-03-01"))
    ]


def cards(html: str) -> list[str]:
    """The `data-state` of each step card, in the order they render."""
    return re.findall(r'<article class="card card--step"\s*\n?\s*data-state="([^"]*)"', html)


def test_changing_a_state_answers_with_the_row(
    client: Client, track: list[Step], opportunity: Opportunity
) -> None:
    """Not with the value alone, which would leave the card around it untouched."""
    overdue = track[0]

    body = client.post(
        f"/steps/{overdue.pk}/field/state",
        {"state": State.objects.get(slug="unremarkable").pk},
        headers=HTMX,
    ).content.decode()

    assert f'id="opportunity-{opportunity.pk}"' in body


def test_the_card_takes_its_new_colour(client: Client, track: list[Step]) -> None:
    """`data-state` is on the card, not on the value inside it (§6.3)."""
    overdue = track[0]

    body = client.post(
        f"/steps/{overdue.pk}/field/state",
        {"state": State.objects.get(slug="ghosted").pk},
        headers=HTMX,
    ).content.decode()

    assert "ghosted" in cards(body)
    assert "overdue" not in cards(body)


def test_the_track_re_sorts(client: Client, track: list[Step]) -> None:
    """Demoting the leading step puts the other one in front (§4.5)."""
    overdue = track[0]

    before = client.get("/").content.decode()
    assert cards(before) == ["overdue", "unremarkable"]

    body = client.post(
        f"/steps/{overdue.pk}/field/state",
        {"state": State.objects.get(slug="ghosted").pk},
        headers=HTMX,
    ).content.decode()

    # Both COMPLETE now, so the later one leads — the inverted date rule (§4.5).
    assert cards(body) == ["unremarkable", "ghosted"]


def test_changing_a_step_date_re_sorts_too(client: Client, opportunity: Opportunity) -> None:
    """The date is the tie-break, so it moves cards inside a group as well."""
    for day in ("2026-02-01", "2026-03-01"):
        Step.objects.create(
            opportunity=opportunity,
            state=State.objects.get(slug="going-well"),
            date=dt.date.fromisoformat(day),
            title=day,
        )
    first = opportunity.ordered_steps[0]

    body = client.post(
        f"/steps/{first.pk}/field/date", {"date": "2026-01-01"}, headers=HTMX
    ).content.decode()

    assert body.index("2026-03-01") < body.index("2026-01-01")


def test_a_state_that_moves_the_row_still_answers_with_the_board(
    client: Client, track: list[Step], company: Company
) -> None:
    """The board outranks the row when the board is what changed (§4.5)."""
    other = Opportunity.objects.create(company=company, title="Other", date=dt.date(2026, 1, 6))
    Step.objects.create(
        opportunity=other, state=State.objects.get(slug="due"), date=dt.date(2026, 1, 9)
    )

    response = client.post(
        f"/steps/{track[0].pk}/field/state",
        {"state": State.objects.get(slug="ghosted").pk},
        headers=HTMX,
    )

    assert response.headers.get("HX-Retarget") == "#board"


# --- What must not get more expensive ---------------------------------------


def test_an_opportunity_value_still_swaps_itself(client: Client, opportunity: Opportunity) -> None:
    """Nothing about a title changes the row around it, so the row is not re-sent."""
    body = client.post(
        f"/opportunities/{opportunity.pk}/field/title", {"title": "Principal"}, headers=HTMX
    ).content.decode()

    assert f'id="opportunity-{opportunity.pk}"' not in body
    assert "Principal" in body


def test_a_note_still_swaps_itself(client: Client, opportunity: Opportunity) -> None:
    """A note has no bearing on the sort or on any card's colour."""
    note = Note.objects.create(opportunity=opportunity, body="first")

    body = client.post(
        f"/notes/{note.pk}/field/body", {"body": "second"}, headers=HTMX
    ).content.decode()

    assert f'id="opportunity-{opportunity.pk}"' not in body
    assert "second" in body
