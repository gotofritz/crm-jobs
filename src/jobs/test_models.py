"""Model defaults, constraints and deletion rules — plan 001 §6."""

import datetime as dt

import pytest
from django.db.models import ProtectedError
from django.db.utils import IntegrityError
from django.utils import timezone

from jobs.models import (
    GROUP_RANK,
    Company,
    Contact,
    Group,
    Opportunity,
    Sector,
    Source,
    State,
    Step,
)


@pytest.mark.usefixtures("db")
def test_company_needs_only_a_name() -> None:
    """Every Company field but the name is optional (§6)."""
    company = Company.objects.create(name="Initech")
    assert company.url == ""
    assert company.linkedin_url == ""
    assert company.head_office == ""
    assert company.sector is None


def test_company_name_is_unique(company: Company) -> None:
    """Typing an existing company must reuse it, so the name is the key (§6.9)."""
    with pytest.raises(IntegrityError):
        Company.objects.create(name=company.name)


def test_contact_name_is_not_unique(contact: Contact) -> None:
    """Two people can share a name and the app cannot tell them apart (§6.7)."""
    namesake = Contact.objects.create(name=contact.name)
    assert namesake.pk != contact.pk


@pytest.mark.usefixtures("db")
def test_sector_name_is_unique() -> None:
    """Sector is a picklist, so one row per spelling (§6.10)."""
    Sector.objects.create(name="Robotics")
    with pytest.raises(IntegrityError):
        Sector.objects.create(name="Robotics")


@pytest.mark.usefixtures("db")
def test_source_name_is_unique() -> None:
    """Source is a picklist, so one row per spelling (§6.10)."""
    Source.objects.create(name="Careers page")
    with pytest.raises(IntegrityError):
        Source.objects.create(name="Careers page")


def test_state_slug_is_unique(state: State) -> None:
    """The slug is the CSS hook, so it has to identify the state (§6.3)."""
    with pytest.raises(IntegrityError):
        State.objects.create(slug=state.slug, name="OTHER", group=Group.DUE, sort_order=99)


@pytest.mark.usefixtures("db")
def test_state_has_no_colour_field() -> None:
    """The model layer never names a colour — the boundary in §6.3."""
    field_names = {field.name for field in State._meta.get_fields()}
    forbidden = {"colour", "color", "bg", "background", "fg", "foreground", "hex", "palette"}
    assert not field_names & forbidden


def test_group_rank_puts_attention_above_due_above_complete() -> None:
    """Group ranking is a business rule next to the enum, not a table (§6.1)."""
    assert GROUP_RANK[Group.ATTENTION] > GROUP_RANK[Group.DUE] > GROUP_RANK[Group.COMPLETE]


def test_opportunity_defaults(opportunity: Opportunity) -> None:
    """A new opportunity is live, unattributed and uncommented (§6)."""
    assert opportunity.comments == ""
    assert opportunity.archived_at is None
    assert opportunity.source is None
    assert opportunity.contact is None
    assert opportunity.created_at is not None
    assert opportunity.updated_at is not None


def test_deleting_a_company_is_protected(opportunity: Opportunity) -> None:
    """Deleting a company must not silently take its opportunities (§6)."""
    with pytest.raises(ProtectedError):
        opportunity.company.delete()


def test_deleting_a_source_keeps_the_opportunity(opportunity: Opportunity) -> None:
    """Losing who referred you does not invalidate the application (§6)."""
    source = Source.objects.create(name="Careers page")
    opportunity.source = source
    opportunity.save()

    source.delete()
    opportunity.refresh_from_db()

    assert opportunity.source is None


def test_deleting_a_contact_keeps_the_opportunity(
    opportunity: Opportunity, contact: Contact
) -> None:
    """The same reasoning as the source: the opportunity outlives the person (§6)."""
    opportunity.contact = contact
    opportunity.save()

    contact.delete()
    opportunity.refresh_from_db()

    assert opportunity.contact is None


def test_step_defaults(opportunity: Opportunity, state: State) -> None:
    """A step defaults to the GAS app's wording, with no time and no contacts (§6)."""
    step = Step.objects.create(opportunity=opportunity, state=state, date=dt.date(2026, 1, 5))

    assert step.title == "Applied via site"
    assert step.time is None
    assert step.comments == ""
    assert list(step.contacts.all()) == []


def test_a_step_keeps_several_contacts(
    opportunity: Opportunity, state: State, contact: Contact
) -> None:
    """A technical interview often involves more than one person (§6.7)."""
    step = Step.objects.create(opportunity=opportunity, state=state, date=dt.date(2026, 1, 5))
    second = Contact.objects.create(name="Grace Hopper")
    step.contacts.add(contact, second)

    assert step.contacts.count() == 2


def test_deleting_an_opportunity_deletes_its_steps(opportunity: Opportunity, state: State) -> None:
    """A step has no meaning without its opportunity (§6)."""
    Step.objects.create(opportunity=opportunity, state=state, date=dt.date(2026, 1, 5))

    opportunity.delete()

    assert Step.objects.count() == 0


def test_deleting_a_state_in_use_is_protected(opportunity: Opportunity, state: State) -> None:
    """Deleting a state would strip the meaning off every step in it (§6)."""
    Step.objects.create(opportunity=opportunity, state=state, date=dt.date(2026, 1, 5))

    with pytest.raises(ProtectedError):
        state.delete()


def test_live_excludes_archived_opportunities(opportunity: Opportunity, company: Company) -> None:
    """The board shows live opportunities only (§6.5)."""
    archived = Opportunity.objects.create(
        company=company,
        title="Backend Engineer",
        date=dt.date(2026, 1, 2),
        archived_at=timezone.now(),
    )

    live = Opportunity.objects.live()

    assert list(live) == [opportunity]
    assert archived not in live


def test_archived_lists_only_archived_opportunities(
    opportunity: Opportunity, company: Company
) -> None:
    """Archiving is reversible and nothing is deleted, so both sides are queryable (§6.5)."""
    archived = Opportunity.objects.create(
        company=company,
        title="Backend Engineer",
        date=dt.date(2026, 1, 2),
        archived_at=timezone.now(),
    )

    assert list(Opportunity.objects.archived()) == [archived]
    assert opportunity not in Opportunity.objects.archived()


def test_models_are_readable_in_the_admin(opportunity: Opportunity, state: State) -> None:
    """The admin is the CRUD backdoor, so rows have to name themselves (§6.9)."""
    step = Step.objects.create(opportunity=opportunity, state=state, date=dt.date(2026, 1, 5))

    assert str(opportunity.company) == "Acme"
    assert str(opportunity) == "Staff Software Engineer at Acme"
    assert str(state) == "UNREMARKABLE"
    assert str(step) == "UNREMARKABLE on 2026-01-05"
