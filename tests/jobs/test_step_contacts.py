"""Who a step was with — plan 001 §6.9, §4.4.

A step keeps several contacts and the form has always saved them, but the card
never printed them: they could be typed in and then never seen again. They are
a value on the card like any other, so they show when there are any, hide when
there are not, and edit by being clicked.

Reading them costs a prefetch. Without it the board asks the database once per
step, which is the one thing the board's query budget forbids (§4.5).
"""

import datetime as dt

import pytest
from django.test import Client
from pytest_django.fixtures import DjangoAssertNumQueries

from jobs.models import Company, Contact, Opportunity, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A step with two people on it."""
    saved = Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 2, 1),
        title="Second interview booked",
    )
    saved.contacts.set(
        [
            Contact.objects.create(name="Grace Hopper"),
            Contact.objects.create(name="Ada Lovelace"),
        ]
    )
    return saved


# --- The model ---------------------------------------------------------------


def test_a_step_names_its_contacts(step: Step) -> None:
    """One string, because that is what the card prints and the form takes back."""
    assert step.contact_names == "Ada Lovelace, Grace Hopper"


def test_the_names_are_in_a_settled_order(step: Step) -> None:
    """Alphabetical, so the card does not reshuffle when a step is re-saved."""
    step.contacts.add(Contact.objects.create(name="Alan Turing"))

    assert step.contact_names == "Ada Lovelace, Alan Turing, Grace Hopper"


def test_a_step_with_nobody_on_it_names_nobody(opportunity: Opportunity) -> None:
    """An empty string, which is what keeps the row off the card."""
    bare = Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )

    assert bare.contact_names == ""


# --- The card ----------------------------------------------------------------


@pytest.mark.usefixtures("step")
def test_the_card_prints_them(client: Client) -> None:
    """The bug: saved, and then never seen again."""
    html = client.get("/").content.decode()

    assert "<dt>Who</dt>" in html
    assert "Ada Lovelace, Grace Hopper" in html


def test_a_step_with_nobody_shows_no_row(client: Client, opportunity: Opportunity) -> None:
    """Empty optional fields stay off the card (§7)."""
    Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )

    assert "<dt>Who</dt>" not in client.get("/").content.decode()


def test_they_are_editable_where_they_are_shown(client: Client, step: Step) -> None:
    """A value on a card is a value on a card."""
    html = client.get("/").content.decode()

    assert f"/steps/{step.pk}/field/contacts" in html


def test_editing_them_in_place_saves_them(client: Client, step: Step) -> None:
    """Comma separated, each resolved the way a company is (§6.9)."""
    client.post(
        f"/steps/{step.pk}/field/contacts",
        {"contacts": "Ada Lovelace, Katherine Johnson"},
        headers=HTMX,
    )

    assert step.contact_names == "Ada Lovelace, Katherine Johnson"


def test_the_input_opens_on_the_names_already_there(client: Client, step: Step) -> None:
    """An edit is a correction, not a retype."""
    body = client.get(f"/steps/{step.pk}/field/contacts", headers=HTMX).content.decode()

    assert "Ada Lovelace, Grace Hopper" in body


# --- What it costs -----------------------------------------------------------


def test_the_board_still_costs_the_same_however_many_rows(
    company: Company, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """Printing the contacts must be a prefetch, not a query per step (§4.5)."""
    for index in range(3):
        row = Opportunity.objects.create(
            company=company, title=f"row {index}", date=dt.date(2026, 1, 5)
        )
        saved = Step.objects.create(
            opportunity=row, state=State.objects.get(slug="due"), date=dt.date(2026, 1, 1)
        )
        saved.contacts.add(Contact.objects.create(name=f"Person {index}"))

    with django_assert_num_queries(6):
        Client().get("/")


@pytest.mark.usefixtures("db")
def test_the_demo_board_shows_some() -> None:
    """`demo.py` exists to put every rendered case on the board (`jobs/demo.py`).

    A step's contacts became one of those, so a board seeded with none of them
    stops exercising the card it is meant to show.
    """
    from jobs.demo import seed_demo

    seed_demo()

    assert any(step.contact_names for step in Step.objects.all())
