"""Every box says what it is — plan 001 §7.

Reported after typing a company into the job title. The two sit one above the
other at the top of the summary card with no label between them, because the
card's heading is a title and a company rather than a list of facts — so an
empty box there is two empty boxes and nothing to tell them apart.

A placeholder only shows while a box is empty, which covers writing a row but
not correcting one. So the inputs carry `aria-label` as well: nothing here
renders a `<label for=…>`, the `<dt>` beside a field is not one, and a box with
neither is unnamed to a screen reader whether it is empty or not.
"""

import datetime as dt
import re

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
    """A step to open for editing."""
    return Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )


def boxes(html: str) -> dict[str, str]:
    """Every text box on the form, by field name, as rendered."""
    found = re.findall(r"<(?:input|textarea)\b[^>]*>", html)
    named = {}
    for tag in found:
        name = re.search(r'name="([^"]+)"', tag)
        kind = re.search(r'type="([^"]+)"', tag)
        if name and kind and kind[1] in {"hidden", "date", "time"}:
            continue
        if name:
            named[name[1]] = tag
    return named


def attr(tag: str, name: str) -> str:
    """One attribute off a rendered tag."""
    match = re.search(rf'{name}="([^"]*)"', tag)

    return match[1] if match else ""


def test_every_box_on_a_card_says_what_it_is(client: Client, opportunity: Opportunity) -> None:
    """A box with no placeholder is a box you have to guess at."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    for name, tag in boxes(html).items():
        assert attr(tag, "placeholder"), name


def test_no_two_boxes_read_the_same(client: Client, opportunity: Opportunity) -> None:
    """Two boxes with one hint is the bug again with extra steps."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()
    hints = [attr(tag, "placeholder") for tag in boxes(html).values()]

    assert len(set(hints)) == len(hints), hints


def test_the_title_and_the_company_cannot_be_confused(
    client: Client, opportunity: Opportunity
) -> None:
    """The pair that was mixed up: no label between them, so the hint has to carry it."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()
    found = boxes(html)

    assert "job" in attr(found["title"], "placeholder").lower()
    assert "company" in attr(found["company"], "placeholder").lower()


def test_every_box_is_named_to_a_screen_reader(client: Client, opportunity: Opportunity) -> None:
    """Nothing renders a `<label for=…>`, and a `<dt>` beside a field is not one."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    for name, tag in boxes(html).items():
        assert attr(tag, "aria-label"), name


def test_a_step_says_what_its_boxes_are(client: Client, step: Step) -> None:
    """A step card is narrower and its boxes are smaller, so it needs this more."""
    html = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()

    for name, tag in boxes(html).items():
        assert attr(tag, "placeholder"), name
        assert attr(tag, "aria-label"), name


def test_a_note_says_what_it_is(client: Client, opportunity: Opportunity) -> None:
    """One box on its own, with nothing around it to explain it."""
    html = client.get(f"/opportunities/{opportunity.pk}/notes/new", headers=HTMX).content.decode()

    assert attr(boxes(html)["body"], "placeholder")


def test_a_single_value_carries_its_hint_too(client: Client, opportunity: Opportunity) -> None:
    """Clicking one value opens one box with nothing else on screen to name it."""
    html = client.get(
        f"/opportunities/{opportunity.pk}/field/company", headers=HTMX
    ).content.decode()

    assert "company" in attr(boxes(html)["company"], "placeholder").lower()


@pytest.mark.usefixtures("db")
def test_a_blank_row_carries_them(client: Client) -> None:
    """Where it matters most: every box on it is empty, so every hint is showing."""
    html = client.get("/opportunities/new", headers=HTMX).content.decode()

    for name, tag in boxes(html).items():
        assert attr(tag, "placeholder"), name


def test_a_hint_is_not_just_the_label_again(client: Client, opportunity: Opportunity) -> None:
    """Where a `<dt>` already names the field, the hint is worth more as an example."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()
    found = boxes(html)

    assert attr(found["company_url"], "placeholder").startswith("https://")
