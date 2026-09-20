"""An opportunity starts with a step — plan 001 §4.4, carried over from the GAS app.

The rule is the model's, not a view's: "an opportunity has at least one step"
is a statement about the domain, and a second way of creating one must not be
able to skip it (AGENTS.md, "Boundaries").
"""

import datetime as dt

from jobs.models import DEFAULT_STEP_STATE, Company, Contact, Opportunity


def test_the_first_step_lands_in_the_default_state(opportunity: Opportunity) -> None:
    """A new opportunity is UNREMARKABLE, mid-pile rather than urgent (§6.6)."""
    step = opportunity.add_first_step()

    assert step.state.slug == DEFAULT_STEP_STATE


def test_the_first_step_takes_the_opportunity_date(opportunity: Opportunity) -> None:
    """The step is dated when the application went out, not when the row was typed (§4.4)."""
    step = opportunity.add_first_step()

    assert step.date == opportunity.date


def test_the_first_step_carries_the_default_title(opportunity: Opportunity) -> None:
    """The GAS app's default title, kept: Applied via site (§4.4)."""
    step = opportunity.add_first_step()

    assert step.title == "Applied via site"


def test_the_first_step_carries_the_opportunity_contact(company: Company, contact: Contact) -> None:
    """The contact on the opportunity is on its first step too (§4.4)."""
    opportunity = Opportunity.objects.create(
        company=company, title="Staff Engineer", date=dt.date(2026, 1, 5), contact=contact
    )

    step = opportunity.add_first_step()

    assert list(step.contacts.all()) == [contact]


def test_the_first_step_of_a_contactless_opportunity_has_no_contacts(
    opportunity: Opportunity,
) -> None:
    """A contact is optional, and an absent one leaves the step's list empty."""
    step = opportunity.add_first_step()

    assert list(step.contacts.all()) == []


def test_the_first_step_is_the_only_step(opportunity: Opportunity) -> None:
    """One step, so the row renders with something in its track from the start."""
    opportunity.add_first_step()

    assert opportunity.steps.count() == 1
