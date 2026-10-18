"""A new opportunity or step opens with today's date filled in (issue 27)."""

import datetime as dt

import pytest
from django.utils import timezone

from jobs.forms import OpportunityForm, StepForm
from jobs.models import Opportunity


@pytest.fixture
def today() -> dt.date:
    """The day the form should offer."""
    return timezone.localdate()


def test_new_opportunity_form_offers_today(today: dt.date) -> None:
    """A blank opportunity card is dated today."""
    assert OpportunityForm().initial["date"] == today


def test_new_step_form_offers_today(opportunity: Opportunity, today: dt.date) -> None:
    """A blank step card is dated today."""
    assert StepForm(opportunity=opportunity).initial["date"] == today


def test_new_opportunity_form_renders_today(today: dt.date) -> None:
    """The date input carries today as its value."""
    assert f'value="{today.isoformat()}"' in str(OpportunityForm()["date"])


def test_edit_keeps_the_stored_date(opportunity: Opportunity) -> None:
    """An edit shows the stored date, not today."""
    opportunity.date = dt.date(2020, 2, 3)
    opportunity.save()
    form = OpportunityForm(instance=opportunity)
    assert 'value="2020-02-03"' in str(form["date"])


def test_bound_form_does_not_override_posted_date() -> None:
    """A bound form shows what was posted."""
    form = OpportunityForm(data={"date": "2020-02-03"})
    assert 'value="2020-02-03"' in str(form["date"])
