"""Shared fixtures for the jobs tests."""

import datetime as dt

import pytest

from jobs.models import Company, Contact, Opportunity, State


@pytest.fixture
def company(db: None) -> Company:
    """A company with nothing filled in but its name."""
    return Company.objects.create(name="Acme")


@pytest.fixture
def contact(db: None) -> Contact:
    """A person to hang employments and steps off."""
    return Contact.objects.create(name="Ada Lovelace")


@pytest.fixture
def state(db: None) -> State:
    """The seeded state a new opportunity's first step lands in (§6.6)."""
    return State.objects.get(slug="unremarkable")


@pytest.fixture
def opportunity(company: Company) -> Opportunity:
    """A live opportunity at the fixture company."""
    return Opportunity.objects.create(
        company=company,
        title="Staff Software Engineer",
        date=dt.date(2026, 1, 5),
    )
