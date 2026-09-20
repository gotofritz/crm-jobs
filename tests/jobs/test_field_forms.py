"""A form narrowed to one field — the unit an in-place edit saves.

Clicking a job title edits the job title. Nothing else on the row is in the
request, so nothing else may be validated against it or written from it: a
whole-object form fed one field would reject the row for the five fields the
browser never sent.

The narrowing is a whitelist rather than a filter. `archived_at` is how the
archive works (§6.5) and the timestamps are the model's own, so neither is
reachable by naming it in a URL.
"""

import datetime as dt

import pytest

from jobs.forms import EDITABLE, NoteForm, OpportunityForm, StepForm
from jobs.models import Company, Note, Opportunity, State, Step


def test_a_narrowed_form_offers_only_that_field(opportunity: Opportunity) -> None:
    """One field in, one field out."""
    form = OpportunityForm(instance=opportunity, only="title")

    assert list(form.fields) == ["title"]


def test_a_narrowed_form_saves_that_field(opportunity: Opportunity) -> None:
    """The point of the exercise."""
    form = OpportunityForm(data={"title": "Principal Engineer"}, instance=opportunity, only="title")
    assert form.is_valid(), form.errors

    assert form.save().title == "Principal Engineer"


def test_a_narrowed_form_leaves_the_other_fields_alone(opportunity: Opportunity) -> None:
    """Editing the title must not blank the date the browser never sent."""
    before = opportunity.date

    form = OpportunityForm(data={"title": "Principal Engineer"}, instance=opportunity, only="title")
    assert form.is_valid(), form.errors

    assert form.save().date == before


def test_a_narrowed_form_does_not_touch_the_company(opportunity: Opportunity) -> None:
    """`company` is resolved in `save`, and an edit that does not include it must not run that."""
    form = OpportunityForm(data={"title": "Principal"}, instance=opportunity, only="title")
    assert form.is_valid(), form.errors
    form.save()

    assert Company.objects.count() == 1


def test_the_company_field_still_resolves_when_it_is_the_one_edited(
    opportunity: Opportunity,
) -> None:
    """Narrowing must not cost the free-text resolution (§6.9)."""
    form = OpportunityForm(
        data={"company": "Northwind Analytics"}, instance=opportunity, only="company"
    )
    assert form.is_valid(), form.errors

    assert form.save().company.name == "Northwind Analytics"


def test_the_source_field_still_resolves_when_it_is_the_one_edited(
    opportunity: Opportunity,
) -> None:
    """Same for the source, which is the other free-text picklist on the card."""
    form = OpportunityForm(data={"source": "Jobs board"}, instance=opportunity, only="source")
    assert form.is_valid(), form.errors

    saved = form.save()

    assert saved.source is not None
    assert saved.source.name == "Jobs board"


def test_a_company_detail_is_editable_on_its_own(opportunity: Opportunity) -> None:
    """With no drawer to edit them from, the four optional company fields live here."""
    form = OpportunityForm(
        data={"company_head_office": "Leeds"}, instance=opportunity, only="company_head_office"
    )
    assert form.is_valid(), form.errors
    form.save()
    opportunity.company.refresh_from_db()

    assert opportunity.company.head_office == "Leeds"


def test_a_narrowed_form_still_validates(opportunity: Opportunity) -> None:
    """A required field is still required when it is the only one on the form."""
    form = OpportunityForm(data={"title": ""}, instance=opportunity, only="title")

    assert not form.is_valid()
    assert "title" in form.errors


def test_a_step_field_is_editable_on_its_own(opportunity: Opportunity) -> None:
    """The same narrowing on a step, whose state is a choice rather than free text."""
    step = Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )

    form = StepForm(
        data={"state": State.objects.get(slug="success").pk},
        instance=step,
        opportunity=opportunity,
        only="state",
    )
    assert form.is_valid(), form.errors

    assert form.save().state.slug == "success"


def test_narrowing_a_step_does_not_clear_its_contacts(opportunity: Opportunity, contact) -> None:
    """`contacts` is written in `save` from free text, and an edit without it must not run that."""
    step = Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )
    step.contacts.add(contact)

    form = StepForm(
        data={"title": "Rescheduled"}, instance=step, opportunity=opportunity, only="title"
    )
    assert form.is_valid(), form.errors

    assert list(form.save().contacts.all()) == [contact]


def test_a_note_body_is_editable_on_its_own(opportunity: Opportunity) -> None:
    """A note has one field, so narrowing it changes nothing — and must still work."""
    note = Note.objects.create(opportunity=opportunity, body="first")

    form = NoteForm(data={"body": "second"}, instance=note, opportunity=opportunity, only="body")
    assert form.is_valid(), form.errors

    assert form.save().body == "second"


# --- The whitelist ---------------------------------------------------------


@pytest.mark.parametrize("field", ["archived_at", "created_at", "updated_at", "pk", "id"])
def test_the_archive_and_the_timestamps_are_not_editable_fields(field: str) -> None:
    """Archiving is its own action (§6.5), and a timestamp is the model's to set."""
    assert field not in EDITABLE[Opportunity]


@pytest.mark.parametrize("field", sorted(EDITABLE[Opportunity]))
def test_every_editable_field_can_be_narrowed_to(opportunity: Opportunity, field: str) -> None:
    """A name in the whitelist the form cannot build is a 500 waiting to happen.

    Narrowed rather than whole, because the two are not the same set: the pasted
    ad is editable on the board and still absent from the form used to create a
    row (§4.8).
    """
    assert list(OpportunityForm(instance=opportunity, only=field).fields) == [field]


def test_the_ad_is_on_the_whole_form(opportunity: Opportunity) -> None:
    """A card in edit mode shows every field it has, and the ad is one of them.

    It was left off while creating meant a small panel. Creating is a blank card
    in edit mode now, so leaving it off would make the one card that cannot be
    filled in completely.
    """
    assert "job_description" in OpportunityForm().fields
    assert "job_description" in OpportunityForm(instance=opportunity, only="job_description").fields


def test_a_field_outside_the_whitelist_is_refused(opportunity: Opportunity) -> None:
    """Narrowing to something unlisted raises rather than quietly editing it."""
    with pytest.raises(KeyError):
        OpportunityForm(instance=opportunity, only="archived_at")
