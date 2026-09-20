"""Editing in place — the board's own answer to what the GAS sidebar did.

The panel is gone from everything but creating a row. A value on the board is a
link: following it swaps that value for an input, saving swaps the value back.
Three routes per model do it — open, save, cancel — and the field is named in
the URL and checked against the whitelist in `forms.EDITABLE`.

The old whole-object edit routes are gone with the panel, and a test here says
so, because leaving them reachable would leave two ways to write the same row.
"""

import datetime as dt
import re

import pytest
from django.test import Client

from jobs.models import Company, Note, Opportunity, Source, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A saved step to edit."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 2, 1),
        title="Second interview booked",
    )


@pytest.fixture
def note(opportunity: Opportunity) -> Note:
    """A saved note to edit."""
    return Note.objects.create(opportunity=opportunity, body="Recruiter answered within a day")


def field_url(opportunity: Opportunity, field: str) -> str:
    """Where a value on an opportunity is opened for editing."""
    return f"/opportunities/{opportunity.pk}/field/{field}"


# --- Opening a value -------------------------------------------------------


def test_following_a_value_opens_an_input(client: Client, opportunity: Opportunity) -> None:
    """`GET .../field/title` swaps the title for something to type in."""
    response = client.get(field_url(opportunity, "title"), headers=HTMX)

    assert response.status_code == 200
    body = response.content.decode()
    assert "<form" in body
    assert 'name="title"' in body


def test_the_input_opens_on_the_stored_value(client: Client, opportunity: Opportunity) -> None:
    """An edit is a correction, not a retype."""
    body = client.get(field_url(opportunity, "title"), headers=HTMX).content.decode()

    assert "Staff Software Engineer" in body


def test_only_that_field_is_offered(client: Client, opportunity: Opportunity) -> None:
    """Clicking the title opens the title, and nothing else on the row."""
    body = client.get(field_url(opportunity, "title"), headers=HTMX).content.decode()

    assert 'name="company"' not in body
    assert 'name="date"' not in body


def test_a_field_outside_the_whitelist_is_a_404(client: Client, opportunity: Opportunity) -> None:
    """Archiving is its own action, and naming it in a URL must not reach it (§6.5)."""
    assert client.get(field_url(opportunity, "archived_at"), headers=HTMX).status_code == 404
    assert client.post(field_url(opportunity, "archived_at"), {}, headers=HTMX).status_code == 404


# --- Saving ----------------------------------------------------------------


def test_saving_a_value_writes_it(client: Client, opportunity: Opportunity) -> None:
    """`POST .../field/title` saves that field."""
    response = client.post(
        field_url(opportunity, "title"), {"title": "Principal Engineer"}, headers=HTMX
    )
    opportunity.refresh_from_db()

    assert response.status_code == 200
    assert opportunity.title == "Principal Engineer"


def test_saving_a_value_swaps_the_value_back(client: Client, opportunity: Opportunity) -> None:
    """What comes back is the value again, ready to be clicked a second time."""
    body = client.post(
        field_url(opportunity, "title"), {"title": "Principal Engineer"}, headers=HTMX
    ).content.decode()

    assert "Principal Engineer" in body
    assert "<form" not in body


def test_saving_one_value_leaves_the_others_alone(client: Client, opportunity: Opportunity) -> None:
    """The browser sent one field; the row must keep the rest."""
    before = (opportunity.date, opportunity.company.pk)

    client.post(field_url(opportunity, "title"), {"title": "Principal"}, headers=HTMX)
    opportunity.refresh_from_db()

    assert (opportunity.date, opportunity.company.pk) == before


def test_a_typed_company_still_resolves(client: Client, opportunity: Opportunity) -> None:
    """The free-text picklists work the same in place as they did on the form (§6.9)."""
    client.post(field_url(opportunity, "company"), {"company": "Northwind Analytics"}, headers=HTMX)
    opportunity.refresh_from_db()

    assert opportunity.company.name == "Northwind Analytics"
    assert Company.objects.count() == 2


def test_a_typed_source_still_resolves(client: Client, opportunity: Opportunity) -> None:
    """Same for the source, created by typing it if it is new (§6.10)."""
    client.post(field_url(opportunity, "source"), {"source": "Jobs board"}, headers=HTMX)
    opportunity.refresh_from_db()

    assert opportunity.source == Source.objects.get(name="Jobs board")


def test_an_invalid_value_comes_back_as_the_input(client: Client, opportunity: Opportunity) -> None:
    """A required field left empty says so in place, and the row is not written."""
    response = client.post(field_url(opportunity, "title"), {"title": ""}, headers=HTMX)
    opportunity.refresh_from_db()

    body = response.content.decode()
    assert "<form" in body
    assert "This field is required." in body
    assert opportunity.title == "Staff Software Engineer"


def test_a_step_field_is_editable_in_place(client: Client, step: Step) -> None:
    """A step card's values are clicked the same way a summary card's are."""
    response = client.post(f"/steps/{step.pk}/field/title", {"title": "Rescheduled"}, headers=HTMX)
    step.refresh_from_db()

    assert response.status_code == 200
    assert step.title == "Rescheduled"


@pytest.mark.usefixtures("opportunity")
def test_changing_a_step_state_that_re_sorts_returns_the_board(
    client: Client, company: Company, step: Step
) -> None:
    """A state is what the sort keys on, so changing one can move the row (§4.5)."""
    other = Opportunity.objects.create(company=company, title="Other", date=dt.date(2026, 1, 6))
    Step.objects.create(
        opportunity=other, state=State.objects.get(slug="ghosted"), date=dt.date(2026, 1, 9)
    )

    response = client.post(
        f"/steps/{step.pk}/field/state",
        {"state": State.objects.get(slug="fail").pk},
        headers=HTMX,
    )

    assert response.headers.get("HX-Retarget") == "#board"


def test_a_note_body_is_editable_in_place(client: Client, note: Note) -> None:
    """A note is a row, and its body is a value on the card like any other."""
    response = client.post(
        f"/notes/{note.pk}/field/body", {"body": "Chased, no reply"}, headers=HTMX
    )
    note.refresh_from_db()

    assert response.status_code == 200
    assert note.body == "Chased, no reply"


def test_the_job_description_is_editable_in_place(client: Client, opportunity: Opportunity) -> None:
    """The ad had a dialog of its own; now it is edited where it is shown (§4.4)."""
    response = client.post(
        field_url(opportunity, "job_description"),
        {"job_description": "Python, Django, Postgres."},
        headers=HTMX,
    )
    opportunity.refresh_from_db()

    assert response.status_code == 200
    assert opportunity.job_description == "Python, Django, Postgres."


def test_a_company_detail_is_editable_in_place(client: Client, opportunity: Opportunity) -> None:
    """With no panel, the four optional company fields are edited on the card."""
    client.post(
        field_url(opportunity, "company_head_office"),
        {"company_head_office": "Leeds"},
        headers=HTMX,
    )
    opportunity.company.refresh_from_db()

    assert opportunity.company.head_office == "Leeds"


# --- Cancelling ------------------------------------------------------------


def test_cancelling_gives_the_value_back(client: Client, opportunity: Opportunity) -> None:
    """Escape asks for the value again; nothing is written."""
    response = client.get(f"{field_url(opportunity, 'title')}/cancel", headers=HTMX)

    body = response.content.decode()
    assert response.status_code == 200
    assert "Staff Software Engineer" in body
    assert "<form" not in body


def test_the_input_says_where_to_cancel_to(client: Client, opportunity: Opportunity) -> None:
    """The script reads it off the form rather than rebuilding the URL (§7)."""
    body = client.get(field_url(opportunity, "title"), headers=HTMX).content.decode()

    assert f"{field_url(opportunity, 'title')}/cancel" in body


# --- What the panel no longer does -----------------------------------------


def test_the_ad_has_no_dialog_of_its_own(client: Client, opportunity: Opportunity) -> None:
    """It is edited where it is shown, like every other value (§4.4)."""
    path = f"/opportunities/{opportunity.pk}/description/edit"

    assert client.get(path, headers=HTMX).status_code == 404


@pytest.mark.usefixtures("note", "step")
def test_a_value_needs_no_button_to_edit_it(client: Client) -> None:
    """Clicking the thing is the edit. Edit is for the fields that are not there.

    So there is one Edit per card, opening all of them, and no per-value button
    beside a value that is already its own control.
    """
    html = client.get("/").content.decode()

    assert "Edit description" not in html
    assert "Edit note" not in html
    # One for the summary card, one for the step card, and no more.
    assert html.count(">Edit</a>") == 2


# --- Without the script ----------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_a_value_is_a_link_without_the_script(client: Client) -> None:
    """No script, no swap — so following it has to go somewhere that works (§7)."""
    html = client.get("/").content.decode()
    value = re.search(r"<a[^>]*class=\"[^\"]*editable[^\"]*\"[^>]*>", html)

    assert value is not None
    assert "href=" in value[0]


def test_a_plain_get_of_a_field_returns_a_page(client: Client, opportunity: Opportunity) -> None:
    """Following that link without htmx gives a page with the one field on it."""
    response = client.get(field_url(opportunity, "title"))

    assert response.status_code == 200
    assert "<!doctype html>" in response.content.decode().lower()


def test_a_plain_post_of_a_field_redirects_to_the_board(
    client: Client, opportunity: Opportunity
) -> None:
    """And saving it lands back on the board, the way every other route does."""
    response = client.post(field_url(opportunity, "title"), {"title": "Principal"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_editing_the_first_opportunity_updates_rather_than_duplicates(
    client: Client, opportunity: Opportunity
) -> None:
    """The §4.6 falsy-index bug, as a regression test against the in-place edit.

    The GAS app tested `if (data.id)`, and index `0` is falsy, so editing the
    first row silently created a second. The primary key is in the URL now, so
    the class of bug has nowhere to live — this is the test that says so.
    """
    client.post(field_url(opportunity, "title"), {"title": "Principal Engineer"}, headers=HTMX)
    opportunity.refresh_from_db()

    assert Opportunity.objects.count() == 1
    assert opportunity.title == "Principal Engineer"


def test_editing_a_value_keeps_the_ones_beside_it(client: Client, opportunity: Opportunity) -> None:
    """Re-saving a title does not quietly drop the source the row already had."""
    opportunity.source = Source.objects.get(name="LinkedIn")
    opportunity.save()

    client.post(field_url(opportunity, "title"), {"title": "Principal"}, headers=HTMX)
    opportunity.refresh_from_db()

    assert opportunity.source is not None
    assert opportunity.source.name == "LinkedIn"


# --- What the script adds --------------------------------------------------


def test_the_input_commits_on_blur_and_on_enter(client: Client, opportunity: Opportunity) -> None:
    """No save button: typing and leaving is the whole interaction."""
    body = client.get(field_url(opportunity, "title"), headers=HTMX).content.decode()

    assert "hx-trigger=" in body
    # `focusout` rather than `blur`: it bubbles, so the form hears its own
    # control without a selector — and a selector is what split the trigger on
    # its own commas (see `test_blur_saves.py`).
    assert "focusout" in body
    # A single-input form submits on Enter by itself, so `submit` is the Enter path.
    assert "submit" in body


def test_escape_is_handled_by_the_one_script(board_js: str) -> None:
    """The cancel is behaviour, so it lives in board.js rather than in an attribute."""
    assert "Escape" in board_js
    # `dataset.cancel` is how a script reads the form's `data-cancel`.
    assert "dataset.cancel" in board_js


def test_escape_puts_the_typed_value_back_first(board_js: str) -> None:
    """Blur fires as the input goes away, and a cancelled edit must not save.

    Restoring `defaultValue` before the swap makes the race harmless: the worst
    a blur can then write is the value that was already there.
    """
    assert "defaultValue" in board_js


@pytest.mark.usefixtures("opportunity")
def test_a_value_carries_no_appearance(client: Client) -> None:
    """`editable` is identity; what it looks like is the stylesheet's (§6.3)."""
    html = client.get("/").content.decode()
    value = re.search(r"<a[^>]*class=\"[^\"]*editable[^\"]*\"[^>]*>", html)

    assert value is not None
    assert "style=" not in value[0]
