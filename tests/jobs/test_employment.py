"""Employment — who was where, when (plan 001 §6.7)."""

import datetime as dt

import pytest
from django.db.utils import IntegrityError

from jobs.models import Company, Contact, Employment, Opportunity

DAY = dt.date(2026, 3, 1)
BEFORE = dt.date(2026, 1, 1)
AFTER = dt.date(2026, 6, 1)


def test_a_stint_with_both_ends_set_covers_days_inside_it(
    company: Company, contact: Contact
) -> None:
    """Both bounds known: the day has to fall between them, inclusively."""
    stint = Employment.objects.create(
        contact=contact, company=company, started_on=BEFORE, ended_on=AFTER
    )

    assert list(Employment.objects.on(DAY)) == [stint]
    assert list(Employment.objects.on(BEFORE)) == [stint]
    assert list(Employment.objects.on(AFTER)) == [stint]
    assert list(Employment.objects.on(BEFORE - dt.timedelta(days=1))) == []
    assert list(Employment.objects.on(AFTER + dt.timedelta(days=1))) == []


def test_an_open_start_covers_every_day_up_to_the_end(company: Company, contact: Contact) -> None:
    """NULL started_on means the start was never established, not that there is none."""
    stint = Employment.objects.create(
        contact=contact, company=company, started_on=None, ended_on=DAY
    )

    assert list(Employment.objects.on(BEFORE)) == [stint]
    assert list(Employment.objects.on(DAY)) == [stint]
    assert list(Employment.objects.on(AFTER)) == []


def test_an_open_end_covers_every_day_from_the_start(company: Company, contact: Contact) -> None:
    """NULL ended_on means still there, or not known to have left."""
    stint = Employment.objects.create(
        contact=contact, company=company, started_on=DAY, ended_on=None
    )

    assert list(Employment.objects.on(BEFORE)) == []
    assert list(Employment.objects.on(DAY)) == [stint]
    assert list(Employment.objects.on(AFTER)) == [stint]


def test_a_stint_open_at_both_ends_covers_every_day(company: Company, contact: Contact) -> None:
    """Nothing is known about either end, so nothing rules any day out."""
    stint = Employment.objects.create(
        contact=contact, company=company, started_on=None, ended_on=None
    )

    assert list(Employment.objects.on(BEFORE)) == [stint]
    assert list(Employment.objects.on(DAY)) == [stint]
    assert list(Employment.objects.on(AFTER)) == [stint]


def test_overlapping_stints_are_allowed(company: Company, contact: Contact) -> None:
    """Advising, contracting and gardening leave are all real (§6.7)."""
    other = Company.objects.create(name="Initech")
    Employment.objects.create(contact=contact, company=company, started_on=BEFORE, ended_on=AFTER)
    Employment.objects.create(contact=contact, company=other, started_on=BEFORE, ended_on=None)

    assert Employment.objects.on(DAY).count() == 2


def test_an_exact_duplicate_stint_is_rejected(company: Company, contact: Contact) -> None:
    """Overlap is fine; the same stint recorded twice is not (§6.7)."""
    Employment.objects.create(contact=contact, company=company, started_on=BEFORE, ended_on=AFTER)

    with pytest.raises(IntegrityError):
        Employment.objects.create(
            contact=contact, company=company, started_on=BEFORE, ended_on=None
        )


def test_moving_a_contact_between_companies_keeps_their_opportunities(
    company: Company, contact: Contact, opportunity: Opportunity
) -> None:
    """A recruiter who moved still belongs to the old opportunity (§6.7)."""
    opportunity.contact = contact
    opportunity.save()
    Employment.objects.create(contact=contact, company=company, started_on=BEFORE, ended_on=DAY)

    new_employer = Company.objects.create(name="Initech")
    Employment.objects.create(contact=contact, company=new_employer, started_on=DAY, ended_on=None)

    opportunity.refresh_from_db()
    assert opportunity.contact == contact
    assert list(contact.opportunities.all()) == [opportunity]
    assert [stint.company for stint in Employment.objects.on(AFTER)] == [new_employer]


def test_deleting_a_contact_deletes_their_stints(company: Company, contact: Contact) -> None:
    """A stint has no meaning without the person it belongs to."""
    Employment.objects.create(contact=contact, company=company, started_on=BEFORE, ended_on=AFTER)

    contact.delete()

    assert Employment.objects.count() == 0


def test_a_stint_names_itself_by_its_person_and_company(company: Company, contact: Contact) -> None:
    """The admin lists stints, and "Employment object (3)" says nothing (§6.9)."""
    stint = Employment.objects.create(contact=contact, company=company, started_on=BEFORE)

    assert str(stint) == "Ada Lovelace at Acme"
