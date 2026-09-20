"""Creating is a blank card in edit mode — plan 001 §7, and no drawer left.

A new opportunity is a blank row at the top of the board with every field
showing; a new step is a blank card at the near end of the track; a new note is
a blank item in the list. Each is the same markup an edit produces, which is the
point: there is one way a card looks when it is being filled in.

They save with one submit rather than on blur, because there is no row yet to
save a field into. Cancel and Escape take the blank away.
"""

import pytest
from django.test import Client

from jobs.models import Opportunity

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


# --- The drawer is gone ----------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_the_board_has_no_drawer(client: Client) -> None:
    """Everything it held now happens on the card it belongs to."""
    html = client.get("/").content.decode()

    assert 'id="drawer"' not in html
    assert 'hx-target="#drawer"' not in html


def test_no_stylesheet_rule_is_left_for_it(project_root) -> None:
    """A rule for an element that no longer exists is dead weight."""
    css = (project_root / "assets" / "forms.css").read_text()

    assert ".drawer" not in css


def test_the_drawer_partials_are_gone(project_root) -> None:
    """Two ways to render a form is one too many."""
    templates = project_root / "src" / "jobs" / "templates" / "jobs"

    assert not (templates / "_form.html").exists()
    assert not (templates / "form_page.html").exists()


# --- A new opportunity -----------------------------------------------------


@pytest.mark.usefixtures("db")
def test_a_new_opportunity_is_a_blank_row(client: Client) -> None:
    """`GET /opportunities/new` gives a row, not a panel."""
    body = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert "<section" in body
    assert "opportunity--new" in body
    assert "<form" in body


@pytest.mark.usefixtures("db")
def test_the_blank_row_shows_every_field(client: Client) -> None:
    """It is a card in edit mode, so it looks like one."""
    body = client.get("/opportunities/new", headers=HTMX).content.decode()

    for name in ("title", "company", "date", "source", "contact", "company_sector"):
        assert f'name="{name}"' in body, name


@pytest.mark.usefixtures("db")
def test_the_blank_row_saves_with_one_submit(client: Client) -> None:
    """There is no row yet, so there is nothing to save a single field into."""
    response = client.post(
        "/opportunities/",
        {"company": "Northwind Analytics", "title": "Staff Engineer", "date": "2026-01-05"},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert Opportunity.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_the_blank_row_goes_at_the_top(client: Client) -> None:
    """Nothing sorts it — it has no steps yet — so it is put where it is seen."""
    body = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert "hx-swap-oob" not in body


@pytest.mark.usefixtures("db")
def test_cancelling_a_blank_row_takes_it_away(client: Client) -> None:
    """Nothing was created, so there is nothing to put back."""
    response = client.get("/new/cancel", headers=HTMX)

    assert response.status_code == 200
    assert response.content.decode().strip() == ""
    assert Opportunity.objects.count() == 0


@pytest.mark.usefixtures("db")
def test_the_blank_row_says_where_to_cancel_to(client: Client) -> None:
    """Escape reads it off the form, the same way an edited value does (§7)."""
    body = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert 'data-cancel="/new/cancel"' in body


# --- A new step ------------------------------------------------------------


def test_a_new_step_is_a_blank_card(client: Client, opportunity: Opportunity) -> None:
    """`+` puts a card in the track rather than opening a panel."""
    body = client.get(f"/opportunities/{opportunity.pk}/steps/new", headers=HTMX).content.decode()

    assert "card--step" in body
    assert "<form" in body
    assert 'name="state"' in body


def test_the_blank_step_saves_with_one_submit(client: Client, opportunity: Opportunity) -> None:
    """Same reason: the step does not exist until it is submitted."""
    from jobs.models import State

    response = client.post(
        f"/opportunities/{opportunity.pk}/steps/",
        {"state": State.objects.get(slug="due").pk, "date": "2026-02-01", "title": "Screen"},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert opportunity.steps.count() == 1


# --- A new note ------------------------------------------------------------


def test_a_new_note_is_a_blank_item(client: Client, opportunity: Opportunity) -> None:
    """A note is one field, so its blank is one input in the list."""
    body = client.get(f"/opportunities/{opportunity.pk}/notes/new", headers=HTMX).content.decode()

    assert "<form" in body
    assert 'name="body"' in body


def test_the_blank_note_saves(client: Client, opportunity: Opportunity) -> None:
    """And comes back as the row it was written on."""
    response = client.post(
        f"/opportunities/{opportunity.pk}/notes/", {"body": "Applied on a whim"}, headers=HTMX
    )

    assert response.status_code == 200
    assert opportunity.notes.count() == 1


# --- Without the script ----------------------------------------------------


@pytest.mark.usefixtures("db")
def test_a_blank_row_asked_for_without_htmx_is_a_page(client: Client) -> None:
    """The board is still usable with nothing running (§7)."""
    response = client.get("/opportunities/new")

    assert response.status_code == 200
    assert "<!doctype html>" in response.content.decode().lower()


@pytest.mark.usefixtures("opportunity")
def test_every_control_is_still_a_link_or_a_form(client: Client) -> None:
    """Every `hx-get` on an anchor with an `href`, every `hx-post` on a form."""
    import re

    html = client.get("/").content.decode()

    for tag in re.findall(r"<(?:a|form|button)\b[^>]*>", html):
        if "hx-get=" in tag:
            assert "href=" in tag, tag
        if "hx-post=" in tag:
            assert "action=" in tag, tag
