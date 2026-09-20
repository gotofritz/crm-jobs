"""Leaving a field commits it — plan 001 §7.

`hx-trigger` is a comma-separated list of events, so a selector with a comma
in it is not one spec but several. `blur from:find :is(input, select, textarea)`
became four: `submit`, a truncated `blur from:find :is(input`, and the literal
events `select` and `textarea)`.

That is why it looked like it worked. A text box fires `select` when its
contents are selected, so typing into one and leaving often saved — by the
accident of a stray trigger. A `<select>` element fires no such event, so a
step's state never saved at all.

`focusout` needs no selector: unlike `blur` it bubbles, so the form hears any
control inside it lose focus, and there is no comma to split on.
"""

import datetime as dt
import re

import pytest
from django.test import Client

from jobs.models import Note, Opportunity, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A step to open a value on."""
    return Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )


def trigger(html: str) -> str:
    """What the form listens for."""
    match = re.search(r'hx-trigger="([^"]*)"', html)

    assert match is not None, "the form listens for nothing"

    return match[1]


def specs(html: str) -> list[str]:
    """The trigger as htmx reads it: one spec per comma."""
    return [spec.strip() for spec in trigger(html).split(",")]


@pytest.mark.parametrize("field", ["title", "date", "company"])
def test_a_value_listens_for_exactly_two_things(
    client: Client, opportunity: Opportunity, field: str
) -> None:
    """Submitting it, and leaving it. Anything else is a comma that got loose."""
    html = client.get(
        f"/opportunities/{opportunity.pk}/field/{field}", headers=HTMX
    ).content.decode()

    assert specs(html) == ["submit", "focusout"]


def test_the_trigger_carries_no_selector(client: Client, opportunity: Opportunity) -> None:
    """A selector is where the stray commas came from; `focusout` bubbles, so none is needed."""
    html = client.get(f"/opportunities/{opportunity.pk}/field/title", headers=HTMX).content.decode()

    assert ":is(" not in trigger(html)
    assert "from:" not in trigger(html)


def test_a_state_listens_the_same_way(client: Client, step: Step) -> None:
    """The one that never fired: a `<select>` has no text to select."""
    html = client.get(f"/steps/{step.pk}/field/state", headers=HTMX).content.decode()

    assert specs(html) == ["submit", "focusout"]


def test_a_note_listens_the_same_way(client: Client, opportunity: Opportunity) -> None:
    """And the other one."""
    note = Note.objects.create(opportunity=opportunity, body="Applied on a whim")

    html = client.get(f"/notes/{note.pk}/field/body", headers=HTMX).content.decode()

    assert specs(html) == ["submit", "focusout"]


# --- The textarea has to fit on the card ------------------------------------


def rows_of(html: str) -> int:
    """How tall the textarea asks to be."""
    match = re.search(r'<textarea[^>]*\browsered=|<textarea[^>]*\brows="(\d+)"', html)

    assert match is not None, "the textarea states no height"

    return int(match[1])


def test_a_note_box_fits_the_card(client: Client, opportunity: Opportunity) -> None:
    """Django's default is ten rows, which runs off the bottom of an 18rem card."""
    note = Note.objects.create(opportunity=opportunity, body="Applied on a whim")

    html = client.get(f"/notes/{note.pk}/field/body", headers=HTMX).content.decode()

    assert rows_of(html) <= 4


def test_a_step_comment_box_fits_the_card(client: Client, step: Step) -> None:
    """A step card is narrower still."""
    html = client.get(f"/steps/{step.pk}/field/comments", headers=HTMX).content.decode()

    assert rows_of(html) <= 4


def test_the_ad_box_is_taller_but_still_bounded(client: Client, opportunity: Opportunity) -> None:
    """The pasted ad is 1870 characters in the sample export, so it gets more room (§4.8)."""
    html = client.get(
        f"/opportunities/{opportunity.pk}/field/job_description", headers=HTMX
    ).content.decode()

    assert 4 < rows_of(html) <= 8


def test_a_blank_note_gets_the_same_box(client: Client, opportunity: Opportunity) -> None:
    """Writing one and correcting one are the same shape."""
    html = client.get(f"/opportunities/{opportunity.pk}/notes/new", headers=HTMX).content.decode()

    assert rows_of(html) <= 4
