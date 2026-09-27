"""Writing through the board's form into a chosen database — plan 004 §6, Phase 1.

`import_opportunities --demo` validates and saves every row through
`OpportunityForm`, and opens each row with `add_first_step`. Both must write
where they are told, or `--demo` would check a row against demo.sqlite3 and
create its company in the live database. These tests open both aliases so the
second one can be seen to stay empty.
"""

import datetime as dt

import pytest

from jobs.forms import OpportunityForm
from jobs.models import Company, Contact, Opportunity, Sector, Source, Step

BOTH = pytest.mark.django_db(databases=["default", "demo"])

ROW = {
    "company": "Northwind Analytics",
    "title": "Staff Engineer",
    "date": "2026-09-24",
    # Neither is a seeded picklist value, so each one is created by the save.
    "source": "Hacker News",
    "contact": "Maya Richardson",
    "company_sector": "Robotics",
}

# Each model, and the name the save above creates it by.
CREATED = [
    (Opportunity, "title", "Staff Engineer"),
    (Company, "name", "Northwind Analytics"),
    (Source, "name", "Hacker News"),
    (Sector, "name", "Robotics"),
    (Contact, "name", "Maya Richardson"),
]


@BOTH
def test_a_form_saved_into_demo_resolves_every_name_there() -> None:
    """Company, source, sector and contact all land beside the opportunity."""
    form = OpportunityForm(data=ROW, using="demo")
    assert form.is_valid(), form.errors

    form.save()

    for model, field, value in CREATED:
        assert model.objects.using("demo").filter(**{field: value}).exists(), model.__name__


@BOTH
def test_a_form_saved_into_demo_leaves_the_live_database_alone() -> None:
    """The failure `--demo` exists to prevent: a live row nobody asked for."""
    form = OpportunityForm(data=ROW, using="demo")
    assert form.is_valid(), form.errors

    form.save()

    for model, field, value in CREATED:
        assert not model.objects.using("default").filter(**{field: value}).exists(), model.__name__


@BOTH
def test_a_form_without_using_still_saves_to_the_live_database() -> None:
    """The board never passes `using`, so the default must be the old behaviour."""
    form = OpportunityForm(data=ROW)
    assert form.is_valid(), form.errors

    form.save()

    assert Opportunity.objects.using("default").count() == 1
    assert not Opportunity.objects.using("demo").exists()


@BOTH
def test_the_first_step_lands_in_the_opportunitys_own_database() -> None:
    """`add_first_step` follows the row it opens, with nothing passed."""
    company = Company.objects.using("demo").create(name="Contoso")
    contact = Contact.objects.using("demo").create(name="Alex Chen")
    opportunity = Opportunity.objects.using("demo").create(
        company=company, title="Backend Developer", date=dt.date(2026, 9, 25), contact=contact
    )

    step = opportunity.add_first_step()

    assert Step.objects.using("demo").get() == step
    assert list(step.contacts.all()) == [contact]
    assert not Step.objects.using("default").exists()
