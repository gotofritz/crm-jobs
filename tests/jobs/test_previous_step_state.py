"""Adding a step can set the state of the step before it (issue 22).

"Previous" is the step shown at the extreme left of the track, which is
`top_step`. The pulldown is seeded with its current state, and choosing the same
state changes nothing.
"""

import datetime as dt

import pytest
from django.test import Client

from jobs.forms import StepForm
from jobs.models import Opportunity, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def previous(opportunity: Opportunity) -> Step:
    """The step the board judges the opportunity by."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 1, 6),
        title="Screen",
    )


def _post(client: Client, opportunity: Opportunity, **extra: object) -> None:
    client.post(
        f"/opportunities/{opportunity.pk}/steps/",
        {
            "state": State.objects.get(slug="due").pk,
            "date": "2026-02-01",
            "title": "Interview",
            **extra,
        },
        headers=HTMX,
    )


@pytest.mark.usefixtures("previous")
def test_the_blank_card_offers_the_previous_state(client: Client, opportunity: Opportunity) -> None:
    """The pulldown is there, and seeded with the state the step has now."""
    form = StepForm(opportunity=opportunity)

    assert form.fields["previous_state"].initial == State.objects.get(slug="due")
    body = client.get(f"/opportunities/{opportunity.pk}/steps/new", headers=HTMX).content.decode()
    assert 'name="previous_state"' in body


def test_a_first_step_has_no_previous(client: Client, opportunity: Opportunity) -> None:
    """Nothing to the left, so nothing to ask."""
    assert "previous_state" not in StepForm(opportunity=opportunity).fields
    body = client.get(f"/opportunities/{opportunity.pk}/steps/new", headers=HTMX).content.decode()
    assert "previous_state" not in body


def test_choosing_another_state_changes_the_previous_step(
    client: Client, opportunity: Opportunity, previous: Step
) -> None:
    """The top step moves to the chosen state; the new one keeps its own."""
    _post(client, opportunity, previous_state=State.objects.get(slug="unremarkable").pk)

    previous.refresh_from_db()
    assert previous.state.slug == "unremarkable"
    assert opportunity.steps.count() == 2


def test_choosing_the_same_state_changes_nothing(
    client: Client, opportunity: Opportunity, previous: Step
) -> None:
    """No write at all, not even one that happens to store the same value."""
    _post(client, opportunity, previous_state=previous.state.pk)

    assert Step.objects.filter(pk=previous.pk, state__slug="due").exists()
    assert opportunity.steps.count() == 2


def test_leaving_it_out_changes_nothing(
    client: Client, opportunity: Opportunity, previous: Step
) -> None:
    """A client that never sent the field must not blank the previous step."""
    _post(client, opportunity)

    previous.refresh_from_db()
    assert previous.state.slug == "due"


def test_editing_a_step_has_no_such_pulldown(previous: Step, opportunity: Opportunity) -> None:
    """Only a new step asks about the one before it."""
    form = StepForm(instance=previous, opportunity=opportunity)

    assert "previous_state" not in form.fields
