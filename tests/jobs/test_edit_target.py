"""Edit mode has to leave its own target on the page — plan 001 §7.

Edit, Done and Cancel all swap `#opportunity-<id>` with `outerHTML`. So
whatever Edit puts there has to carry that id, or the element the next click
aims at is gone and htmx raises a target error instead of doing anything.

The card is not that element — the row is. Opening a card for editing therefore
re-renders the row around it, which is also what keeps the steps and the ad on
screen while the summary is being edited.
"""

import datetime as dt

import pytest
from django.test import Client

from jobs.models import Opportunity, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A saved step to open."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 2, 1),
        title="Second interview booked",
    )


def test_opening_a_summary_keeps_the_row_id(client: Client, opportunity: Opportunity) -> None:
    """Done and Cancel aim at it, so it has to survive Edit."""
    body = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert f'id="opportunity-{opportunity.pk}"' in body


def test_opening_a_summary_keeps_its_steps_on_screen(client: Client, step: Step) -> None:
    """Editing the summary is not a reason for the rest of the row to disappear."""
    body = client.get(f"/opportunities/{step.opportunity.pk}/edit", headers=HTMX).content.decode()

    assert "opportunity__track" in body
    assert "Second interview booked" in body


def test_opening_a_step_keeps_the_row_id(client: Client, step: Step) -> None:
    """A step card's controls aim at the row too."""
    body = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()

    assert f'id="opportunity-{step.opportunity.pk}"' in body


def test_opening_a_step_opens_only_that_step(
    client: Client, step: Step, opportunity: Opportunity
) -> None:
    """The other cards in the track stay as they are."""
    other = Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="ghosted"), date=dt.date(2026, 3, 1)
    )

    body = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()

    assert body.count("card__edit") == 1
    assert f"/steps/{other.pk}/edit" in body


def test_saving_a_summary_gives_the_row_back(client: Client, opportunity: Opportunity) -> None:
    """Otherwise the row is replaced by a bare card and the next click has no target."""
    body = client.post(
        f"/opportunities/{opportunity.pk}/edit",
        {"title": "Principal", "company": "Acme", "date": "2026-01-05"},
        headers=HTMX,
    ).content.decode()

    assert f'id="opportunity-{opportunity.pk}"' in body


def test_an_invalid_summary_gives_the_row_back(client: Client, opportunity: Opportunity) -> None:
    """A failed Done has to leave a target for the next attempt."""
    body = client.post(
        f"/opportunities/{opportunity.pk}/edit",
        {"title": "", "company": "Acme", "date": "2026-01-05"},
        headers=HTMX,
    ).content.decode()

    assert f'id="opportunity-{opportunity.pk}"' in body
    assert "This field is required." in body


def test_saving_a_step_gives_the_row_back(client: Client, step: Step) -> None:
    """Same for a step card."""
    body = client.post(
        f"/steps/{step.pk}/edit",
        {
            "state": step.state.pk,
            "date": "2026-02-01",
            "title": "Done",
            "time": "",
            "comments": "",
            "contacts": "",
        },
        headers=HTMX,
    ).content.decode()

    assert f'id="opportunity-{step.opportunity.pk}"' in body


def test_the_ad_is_not_shown_twice_while_editing(client: Client, opportunity: Opportunity) -> None:
    """It is a field on the form in edit mode, so its own block stands down."""
    opportunity.job_description = "Python, Django, Postgres."
    opportunity.save()

    body = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert "opportunity__description" not in body


def test_a_note_has_no_card_edit_mode(client: Client, opportunity: Opportunity) -> None:
    """Edit is for the fields an empty value hides, and a note has no such field.

    It has one, which is the note, and clicking it edits it. Answering this with
    an edit-mode summary card built from a `NoteForm` renders a card with no
    inputs on it at all, so it is a 404 instead.
    """
    from jobs.models import Note

    note = Note.objects.create(opportunity=opportunity, body="Recruiter called")

    assert client.get(f"/notes/{note.pk}/edit", headers=HTMX).status_code == 404
    assert client.post(f"/notes/{note.pk}/edit", {"body": "x"}, headers=HTMX).status_code == 404


# --- The form is the card ---------------------------------------------------


def test_the_summary_form_is_inside_the_summary_card(
    client: Client, opportunity: Opportunity
) -> None:
    """The form mimics the card because it is in it, not beside it.

    `.card--summary` is what carries `flex: 0 0 var(--summary-width)`, so a form
    nested in it takes the card's width. A form that replaced the card instead
    would be laid out by the row and span the board.
    """
    import re

    body = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()
    card = re.search(r'<article class="card card--summary".*?</article>', body, re.DOTALL)

    assert card is not None
    assert "card__edit" in card[0]


def test_the_step_form_is_inside_the_step_card(client: Client, step: Step) -> None:
    """Same for a step: `.card--step` is what gives it its width."""
    import re

    body = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()
    card = re.search(r'<article class="card card--step".*?</article>', body, re.DOTALL)

    assert card is not None
    assert "card__edit" in card[0]


def test_editing_leaves_the_row_its_two_blocks(client: Client, step: Step) -> None:
    """A row being edited is still a row: a summary, and the steps beside it (§7)."""
    body = client.get(f"/opportunities/{step.opportunity.pk}/edit", headers=HTMX).content.decode()

    assert body.index("card--summary") < body.index("opportunity__steps")
