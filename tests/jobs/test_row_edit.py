"""Edit mode, and the empty fields it is the only way to reach — plan 001 §7.

A card shows what it has. A field with nothing in it is a label and a dash
taking up an 18rem column, so it is not shown at all — which leaves no way to
fill one in, and that is what Edit is for. Edit opens the whole card as one
form with every field on it, empty ones included; Done saves and the empty ones
go back to being hidden.

Clicking a single value still edits that value on its own. The two do not
overlap: one is for changing something that is there, the other for filling in
something that is not.
"""

import datetime as dt

import pytest
from django.test import Client

from jobs.models import Company, Opportunity, Source, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A saved step, with nothing optional filled in."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 2, 1),
        title="Second interview booked",
    )


@pytest.fixture
def furnished(opportunity: Opportunity) -> Opportunity:
    """An opportunity with its optional fields filled in."""
    opportunity.source = Source.objects.get(name="LinkedIn")
    opportunity.save()
    opportunity.company.head_office = "Leeds"
    opportunity.company.save()
    return opportunity


# --- An empty field is not on the card -------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_an_empty_optional_field_is_not_shown(client: Client) -> None:
    """A label and a dash is an 18rem column spent on nothing."""
    html = client.get("/").content.decode()

    for label in ("Source", "Contact", "Sector", "LinkedIn", "Office"):
        assert f"<dt>{label}</dt>" not in html, label


@pytest.mark.usefixtures("furnished")
def test_a_filled_optional_field_is_shown(client: Client) -> None:
    """What the row has, the row prints."""
    html = client.get("/").content.decode()

    assert "<dt>Source</dt>" in html
    assert "LinkedIn" in html
    assert "Leeds" in html


@pytest.mark.usefixtures("opportunity")
def test_the_required_fields_are_always_shown(client: Client) -> None:
    """Title, company and date cannot be empty, so they are never hidden."""
    html = client.get("/").content.decode()

    assert "Staff Software Engineer" in html
    assert "Acme" in html
    assert "<dt>Applied</dt>" in html


@pytest.mark.usefixtures("step")
def test_an_empty_step_field_is_not_shown(client: Client) -> None:
    """A step's time and comments are optional and go the same way."""
    html = client.get("/").content.decode()

    assert "<dt>Notes</dt>" not in html


# --- Edit opens everything -------------------------------------------------


def test_edit_opens_the_card_as_one_form(client: Client, opportunity: Opportunity) -> None:
    """`GET /opportunities/<id>/edit` — the whole card, not one field."""
    response = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX)

    assert response.status_code == 200
    assert "<form" in response.content.decode()


def test_edit_shows_the_empty_fields_too(client: Client, opportunity: Opportunity) -> None:
    """Filling one in is the whole reason the button exists."""
    body = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    for name in ("source", "contact", "company_sector", "company_linkedin_url"):
        assert f'name="{name}"' in body, name


def test_edit_shows_the_filled_fields_on_their_values(
    client: Client, furnished: Opportunity
) -> None:
    """An edit is a correction, not a retype."""
    body = client.get(f"/opportunities/{furnished.pk}/edit", headers=HTMX).content.decode()

    assert "LinkedIn" in body
    assert "Leeds" in body


def test_edit_becomes_done(client: Client, opportunity: Opportunity) -> None:
    """The button that opened it is the button that closes it."""
    normal = client.get("/").content.decode()
    editing = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert ">Edit</a>" in normal or ">Edit<" in normal
    assert ">Done<" in editing
    assert ">Edit<" not in editing


def test_done_saves_every_field_at_once(client: Client, opportunity: Opportunity) -> None:
    """One form, one submit — unlike a single value, which commits on blur."""
    response = client.post(
        f"/opportunities/{opportunity.pk}/edit",
        {
            "title": "Principal Engineer",
            "company": "Acme",
            "date": "2026-01-05",
            "source": "Wellfound",
            "contact": "Ada Lovelace",
            "company_head_office": "Leeds",
            "company_sector": "Fintech",
            "company_url": "",
            "company_linkedin_url": "",
            "job_description": "",
        },
        headers=HTMX,
    )
    opportunity.refresh_from_db()
    opportunity.company.refresh_from_db()

    assert response.status_code == 200
    assert opportunity.title == "Principal Engineer"
    assert opportunity.source is not None
    assert opportunity.source.name == "Wellfound"
    assert opportunity.company.head_office == "Leeds"


def test_done_hides_the_ones_left_empty(client: Client, opportunity: Opportunity) -> None:
    """What comes back is the card again, and an empty field is not on it."""
    body = client.post(
        f"/opportunities/{opportunity.pk}/edit",
        {"title": "Principal", "company": "Acme", "date": "2026-01-05"},
        headers=HTMX,
    ).content.decode()

    assert "<dt>Source</dt>" not in body
    assert "<dt>Applied</dt>" in body
    # The archive and delete controls are forms too, so it is the edit form that
    # has to be gone, not every form on the card.
    assert "card__edit" not in body
    assert ">Done<" not in body


def test_an_invalid_edit_comes_back_as_the_form(client: Client, opportunity: Opportunity) -> None:
    """A required field left empty says so, and the row is not written."""
    response = client.post(
        f"/opportunities/{opportunity.pk}/edit",
        {"title": "", "company": "Acme", "date": "2026-01-05"},
        headers=HTMX,
    )
    opportunity.refresh_from_db()

    body = response.content.decode()
    assert "<form" in body
    assert "This field is required." in body
    assert opportunity.title == "Staff Software Engineer"


def test_a_step_has_an_edit_mode_of_its_own(client: Client, step: Step) -> None:
    """A step card is a card, and its optional fields hide the same way."""
    body = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()

    assert 'name="time"' in body
    assert 'name="comments"' in body


def test_done_on_a_step_saves_it(client: Client, step: Step) -> None:
    """One submit for the whole card."""
    response = client.post(
        f"/steps/{step.pk}/edit",
        {
            "state": State.objects.get(slug="success").pk,
            "date": "2026-02-02",
            "title": "Passed the panel",
            "time": "",
            "comments": "Went well",
            "contacts": "",
        },
        headers=HTMX,
    )
    step.refresh_from_db()

    assert response.status_code == 200
    assert step.title == "Passed the panel"
    assert step.comments == "Went well"


# --- Clicking one value still works ----------------------------------------


def test_a_single_value_is_still_click_to_edit(client: Client, opportunity: Opportunity) -> None:
    """The quick path survives the arrival of the slow one."""
    html = client.get("/").content.decode()

    assert 'class="editable"' in html
    assert f"/opportunities/{opportunity.pk}/field/title" in html


def test_a_single_value_still_commits_on_blur(client: Client, opportunity: Opportunity) -> None:
    """Edit mode has a Done; one value does not, and never did."""
    body = client.get(f"/opportunities/{opportunity.pk}/field/title", headers=HTMX).content.decode()

    assert "focusout" in body
    assert ">Done<" not in body


# --- Clearing a company detail ---------------------------------------------


def test_done_clears_a_company_detail_that_was_emptied(
    client: Client, furnished: Opportunity
) -> None:
    """Edit mode shows the field on its value, so submitting it blank is deliberate.

    The rule that a blank leaves the stored value alone was written when these
    fields were a side effect of the opportunity form and nobody could see them.
    Edit mode puts them on the card, which makes emptying one an instruction.
    """
    client.post(
        f"/opportunities/{furnished.pk}/edit",
        {
            "title": furnished.title,
            "company": "Acme",
            "date": "2026-01-05",
            "company_head_office": "",
        },
        headers=HTMX,
    )
    furnished.company.refresh_from_db()

    assert furnished.company.head_office == ""


def test_clicking_one_detail_and_emptying_it_clears_it(
    client: Client, furnished: Opportunity
) -> None:
    """Same reasoning for the single-value path: the box was shown holding Leeds."""
    client.post(
        f"/opportunities/{furnished.pk}/field/company_head_office",
        {"company_head_office": ""},
        headers=HTMX,
    )
    furnished.company.refresh_from_db()

    assert furnished.company.head_office == ""


@pytest.mark.usefixtures("db")
def test_creating_at_a_known_company_does_not_clear_its_details(client: Client) -> None:
    """A blank box on a create is a box nobody filled in, not a box someone emptied.

    The form was never opened on that company, so it never showed what it holds,
    so submitting blank cannot mean "remove it".
    """
    Company.objects.create(name="Northwind Analytics", head_office="Leeds")

    client.post(
        "/opportunities/",
        {
            "company": "Northwind Analytics",
            "title": "Staff Engineer",
            "date": "2026-01-05",
            "company_head_office": "",
        },
        headers=HTMX,
    )

    assert Company.objects.get(name="Northwind Analytics").head_office == "Leeds"
