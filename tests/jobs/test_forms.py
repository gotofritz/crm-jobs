"""The forms — plan 001 §6.9, and the boundary in AGENTS.md.

Every picklist on these forms is a text input: typing a name is what creates
the row, so there are no management screens to keep in step. `State` is the one
exception and the tests say why.
"""

import datetime as dt

import pytest

from jobs.forms import JobDescriptionForm, NoteForm, OpportunityForm, StepForm
from jobs.models import Company, Contact, Opportunity, Sector, Source, State, Step


def opportunity_data(**overrides: str) -> dict[str, str]:
    """The least an opportunity form will accept."""
    return {
        "company": "Northwind Analytics",
        "title": "Staff Backend Engineer",
        "date": "2026-01-05",
    } | overrides


def step_data(**overrides: object) -> dict[str, object]:
    """The least a step form will accept."""
    return {
        "state": State.objects.get(slug="due").pk,
        "date": "2026-02-01",
        "title": "Second interview booked",
    } | overrides


# --- OpportunityForm -------------------------------------------------------


@pytest.mark.usefixtures("db")
def test_typing_a_new_company_creates_it() -> None:
    """No company screen: the name on the opportunity form is the company (§6.9)."""
    form = OpportunityForm(data=opportunity_data())

    assert form.is_valid(), form.errors
    opportunity = form.save()

    assert opportunity.company.name == "Northwind Analytics"


def test_typing_an_existing_company_reuses_it(company: Company) -> None:
    """Typing `Acme` again points at the same row rather than creating a second (§6.9)."""
    form = OpportunityForm(data=opportunity_data(company="acme"))
    assert form.is_valid(), form.errors

    opportunity = form.save()

    assert opportunity.company == company
    assert Company.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_a_company_created_mid_flow_needs_only_a_name() -> None:
    """Url, LinkedIn, head office and sector are all optional (§6, phase 4)."""
    form = OpportunityForm(data=opportunity_data())
    assert form.is_valid(), form.errors

    company = form.save().company

    assert (company.url, company.linkedin_url, company.head_office) == ("", "", "")
    assert company.sector is None


@pytest.mark.usefixtures("db")
def test_the_company_details_are_edited_from_the_opportunity_form() -> None:
    """The four optional company fields are filled in from here, not a second screen."""
    form = OpportunityForm(
        data=opportunity_data(
            company_url="https://northwind.example",
            company_linkedin_url="https://linkedin.example/northwind",
            company_head_office="Leeds",
            company_sector="Fintech",
        )
    )
    assert form.is_valid(), form.errors

    company = form.save().company

    assert company.url == "https://northwind.example"
    assert company.linkedin_url == "https://linkedin.example/northwind"
    assert company.head_office == "Leeds"
    assert company.sector is not None
    assert company.sector.name == "Fintech"


@pytest.mark.usefixtures("db")
def test_a_blank_company_detail_leaves_the_stored_one_alone() -> None:
    """A create must not wipe what another opportunity filled in (§6.9).

    The form was never opened on that company, so the box was blank because
    nobody filled it in rather than because someone emptied it. A form opened on
    the company does show what it holds, and there a blank does clear — see
    `test_row_edit.py`.
    """
    Company.objects.create(name="Northwind Analytics", head_office="Leeds")
    form = OpportunityForm(data=opportunity_data(company_head_office=""))
    assert form.is_valid(), form.errors

    assert form.save().company.head_office == "Leeds"


@pytest.mark.usefixtures("db")
def test_a_sector_is_resolved_case_insensitively() -> None:
    """`fintech` lands on the seeded `Fintech` rather than forking it (§6.9)."""
    form = OpportunityForm(data=opportunity_data(company_sector="fintech"))
    assert form.is_valid(), form.errors

    sector = form.save().company.sector

    assert sector is not None
    assert sector.name == "Fintech"
    assert Sector.objects.filter(name__iexact="fintech").count() == 1


@pytest.mark.usefixtures("db")
def test_the_source_is_free_text_too() -> None:
    """A source that does not exist yet is created by typing it (§6.10)."""
    form = OpportunityForm(data=opportunity_data(source="Jobs board"))
    assert form.is_valid(), form.errors

    opportunity = form.save()

    assert opportunity.source is not None
    assert opportunity.source.name == "Jobs board"
    assert Source.objects.filter(name="Jobs board").exists()


@pytest.mark.usefixtures("db")
def test_a_blank_source_leaves_the_opportunity_without_one() -> None:
    """Source is optional, and blank must not leave an empty `Source` row behind."""
    form = OpportunityForm(data=opportunity_data(source=""))
    assert form.is_valid(), form.errors

    assert form.save().source is None
    assert not Source.objects.filter(name="").exists()


@pytest.mark.usefixtures("db")
def test_the_contact_is_free_text_too() -> None:
    """Typing a person's name is how a contact is attached (§6.9)."""
    form = OpportunityForm(data=opportunity_data(contact="Ada Lovelace"))
    assert form.is_valid(), form.errors

    opportunity = form.save()

    assert opportunity.contact is not None
    assert opportunity.contact.name == "Ada Lovelace"


@pytest.mark.usefixtures("db")
def test_an_opportunity_without_a_company_is_invalid() -> None:
    """The one field a company needs is the one field the form insists on."""
    form = OpportunityForm(data=opportunity_data(company=""))

    assert not form.is_valid()
    assert "company" in form.errors


@pytest.mark.usefixtures("db")
def test_an_opportunity_without_a_title_is_invalid() -> None:
    """`position` is free text (§6.8), but it is not optional."""
    form = OpportunityForm(data=opportunity_data(title=""))

    assert not form.is_valid()
    assert "title" in form.errors


@pytest.mark.usefixtures("db")
def test_an_invalid_form_creates_no_company() -> None:
    """A form that will not save must not leave a picklist row behind (§6.9)."""
    OpportunityForm(data=opportunity_data(title="")).is_valid()

    assert not Company.objects.filter(name="Northwind Analytics").exists()


def test_editing_an_opportunity_offers_its_current_names(opportunity: Opportunity) -> None:
    """The text inputs open on what is stored, so an edit is not a retype."""
    form = OpportunityForm(instance=opportunity)

    assert form.initial["company"] == "Acme"


def test_editing_an_opportunity_updates_it(opportunity: Opportunity) -> None:
    """Editing the first opportunity updates rather than duplicates it (§4.6 regression).

    The GAS app tested `if (data.id)`, and index `0` is falsy, so editing the
    first row silently created a second. Real primary keys remove the class of
    bug; this is the test that says so.
    """
    form = OpportunityForm(
        data=opportunity_data(company="Acme", title="Principal Engineer"), instance=opportunity
    )
    assert form.is_valid(), form.errors

    saved = form.save()

    assert saved.pk == opportunity.pk
    assert Opportunity.objects.count() == 1
    assert saved.title == "Principal Engineer"


def test_the_job_description_is_on_the_opportunity_form() -> None:
    """A card in edit mode shows every field it has, the pasted ad included."""
    assert "job_description" in OpportunityForm().fields


# --- StepForm --------------------------------------------------------------


def test_a_step_is_saved_against_its_opportunity(opportunity: Opportunity) -> None:
    """A step has no meaning without the opportunity it belongs to."""
    form = StepForm(data=step_data(), opportunity=opportunity)
    assert form.is_valid(), form.errors

    step = form.save()

    assert step.opportunity == opportunity
    assert step.state.slug == "due"


def test_a_step_keeps_several_contacts(opportunity: Opportunity) -> None:
    """Contacts are a comma-separated list, each resolved the way a company is (§6.9)."""
    form = StepForm(data=step_data(contacts="Ada Lovelace, Grace Hopper"), opportunity=opportunity)
    assert form.is_valid(), form.errors

    step = form.save()

    assert {contact.name for contact in step.contacts.all()} == {"Ada Lovelace", "Grace Hopper"}


def test_a_step_reuses_a_contact_that_already_exists(
    opportunity: Opportunity, contact: Contact
) -> None:
    """Typing a known name attaches the stored person rather than a namesake (§6.9)."""
    form = StepForm(data=step_data(contacts="ada lovelace"), opportunity=opportunity)
    assert form.is_valid(), form.errors

    assert list(form.save().contacts.all()) == [contact]
    assert Contact.objects.count() == 1


def test_a_step_with_no_time_is_valid(opportunity: Opportunity) -> None:
    """The sheet stored ':' for an unset time, and the port keeps it optional (§4.5)."""
    form = StepForm(data=step_data(), opportunity=opportunity)
    assert form.is_valid(), form.errors

    assert form.save().time is None


def test_a_step_needs_a_state(opportunity: Opportunity) -> None:
    """A state is chosen, not typed: a new one needs a group and a rank (§6.10)."""
    form = StepForm(data=step_data(state=""), opportunity=opportunity)

    assert not form.is_valid()
    assert "state" in form.errors


def test_the_state_field_is_a_choice_not_free_text(opportunity: Opportunity) -> None:
    """Unlike every other picklist, a state cannot be invented by typing (§6.10).

    A new state needs a group and a `sort_order` — a decision in code — so the
    field offers the stored ones and nothing else.
    """
    from django.forms import ModelChoiceField

    assert isinstance(StepForm(opportunity=opportunity).fields["state"], ModelChoiceField)


def test_editing_a_step_offers_its_current_contacts(
    opportunity: Opportunity, contact: Contact
) -> None:
    """An edit opens on the names already attached, so it is not a retype."""
    step = Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )
    step.contacts.add(contact)

    form = StepForm(instance=step, opportunity=opportunity)

    assert form.initial["contacts"] == "Ada Lovelace"


def test_editing_a_step_updates_rather_than_duplicates(opportunity: Opportunity) -> None:
    """The §4.6 falsy-index bug hit a first step too; primary keys remove it."""
    step = Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )

    form = StepForm(data=step_data(title="Rescheduled"), instance=step, opportunity=opportunity)
    assert form.is_valid(), form.errors
    saved = form.save()

    assert saved.pk == step.pk
    assert opportunity.steps.count() == 1


# --- NoteForm and JobDescriptionForm ---------------------------------------


def test_a_note_is_saved_against_its_opportunity(opportunity: Opportunity) -> None:
    """A note is a row on an opportunity, written and read newest first."""
    form = NoteForm(data={"body": "Recruiter answered within a day"}, opportunity=opportunity)
    assert form.is_valid(), form.errors

    note = form.save()

    assert note.opportunity == opportunity
    assert note.body == "Recruiter answered within a day"


def test_an_empty_note_is_invalid(opportunity: Opportunity) -> None:
    """A note with no body is nothing; the form says so rather than storing it."""
    form = NoteForm(data={"body": "   "}, opportunity=opportunity)

    assert not form.is_valid()
    assert "body" in form.errors


def test_the_job_description_is_edited_on_its_own(opportunity: Opportunity) -> None:
    """The pasted ad gets a dialog of its own, the way comments did (§4.4)."""
    form = JobDescriptionForm(
        data={"job_description": "Python, Django, Postgres."}, instance=opportunity
    )
    assert form.is_valid(), form.errors

    assert form.save().job_description == "Python, Django, Postgres."


def test_the_job_description_may_be_emptied(opportunity: Opportunity) -> None:
    """Deleting the ad is clearing the field, not a separate action."""
    opportunity.job_description = "Something pasted in error"
    opportunity.save()

    form = JobDescriptionForm(data={"job_description": ""}, instance=opportunity)
    assert form.is_valid(), form.errors

    assert form.save().job_description == ""


@pytest.mark.parametrize(
    ("form_class", "field"),
    [(NoteForm, "body"), (JobDescriptionForm, "job_description")],
)
def test_the_small_forms_carry_one_field_each(
    opportunity: Opportunity, form_class: type, field: str
) -> None:
    """Each dialog edits one thing, so neither can quietly rewrite the other's."""
    kwargs = {"opportunity": opportunity} if form_class is NoteForm else {"instance": opportunity}

    assert list(form_class(**kwargs).fields) == [field]
