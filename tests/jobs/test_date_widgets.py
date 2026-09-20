"""What a form renders has to be what the same form accepts.

`LANGUAGE_CODE` is `en-gb`, so Django localises a date on the way out as
`05/01/2026`. An `<input type="date">` only understands `YYYY-MM-DD`, so the
browser silently shows an empty box — and the field is required, which turns a
display bug into a card that cannot be saved at all.

The round trip is the test that catches it: render the form, read the value the
widget put in the box, post that value back, and it has to validate.
"""

import datetime as dt

import pytest
from django.forms import BaseForm

from jobs.forms import OpportunityForm, StepForm
from jobs.models import Opportunity, State, Step


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A step with both of its clock fields set."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 2, 1),
        time=dt.time(14, 30),
    )


def value_of(form: BaseForm, field: str) -> str:
    """What the widget actually put in the box."""
    import re

    rendered = str(form[field])
    match = re.search(r'value="([^"]*)"', rendered)

    assert match is not None, rendered

    return match[1]


def test_a_date_renders_in_the_only_format_the_input_accepts(
    opportunity: Opportunity,
) -> None:
    """`<input type="date">` understands ISO and nothing else."""
    assert value_of(OpportunityForm(instance=opportunity), "date") == "2026-01-05"


def test_a_narrowed_date_renders_the_same_way(opportunity: Opportunity) -> None:
    """Clicking the date on its own opens the same widget."""
    assert value_of(OpportunityForm(instance=opportunity, only="date"), "date") == "2026-01-05"


def test_a_step_date_renders_the_same_way(step: Step, opportunity: Opportunity) -> None:
    """A step card has one too."""
    assert value_of(StepForm(instance=step, opportunity=opportunity), "date") == "2026-02-01"


def test_a_step_time_renders_without_its_seconds(step: Step, opportunity: Opportunity) -> None:
    """`<input type="time">` shows hours and minutes; seconds are noise on a card."""
    assert value_of(StepForm(instance=step, opportunity=opportunity), "time") == "14:30"


def test_the_rendered_date_is_a_date_the_form_accepts(opportunity: Opportunity) -> None:
    """The round trip: what came out of the box goes back in unchanged.

    This passed while the bug was live, because `DATE_INPUT_FORMATS` for en-gb
    accepts the localised spelling too — the browser simply never sent it. It
    guards the other direction: the ISO format the widget now emits has to stay
    one the form will take back.
    """
    rendered = value_of(OpportunityForm(instance=opportunity), "date")

    form = OpportunityForm(
        data={"title": opportunity.title, "company": "Acme", "date": rendered},
        instance=opportunity,
    )

    assert form.is_valid(), form.errors
    assert form.save().date == dt.date(2026, 1, 5)


def test_the_rendered_step_clock_is_one_the_form_accepts(
    step: Step, opportunity: Opportunity
) -> None:
    """Same round trip for a step's date and time."""
    whole = StepForm(instance=step, opportunity=opportunity)

    form = StepForm(
        data={
            "state": step.state.pk,
            "date": value_of(whole, "date"),
            "time": value_of(whole, "time"),
            "title": step.title,
            "comments": "",
            "contacts": "",
        },
        instance=step,
        opportunity=opportunity,
    )

    assert form.is_valid(), form.errors
    saved = form.save()
    assert (saved.date, saved.time) == (dt.date(2026, 2, 1), dt.time(14, 30))
