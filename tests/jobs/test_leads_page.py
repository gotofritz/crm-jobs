"""The sources page — plan 010.

A page of places to look for future opportunities: a link and some notes each,
with create, update and delete. Plain forms, so it works without the script.
"""

import pytest
from django.test import Client
from django.urls import reverse

from jobs.models import Lead


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def lead(db: None) -> Lead:  # noqa: ARG001
    """A source already on the page."""
    return Lead.objects.create(url="https://example.com/jobs", notes="Check Mondays")


def test_str_is_the_link(lead: Lead) -> None:
    """The admin and the shell name a lead by where it points."""
    assert str(lead) == "https://example.com/jobs"


def test_the_page_lists_sources_and_offers_a_blank_form(client: Client, lead: Lead) -> None:
    """Existing sources come back as editable fields, with a form to add one."""
    response = client.get(reverse("leads"))

    assert response.status_code == 200
    body = response.content.decode()
    assert "https://example.com/jobs" in body
    assert "Check Mondays" in body
    assert reverse("lead-create") in body
    assert reverse("lead-update", args=[lead.pk]) in body
    assert reverse("lead-delete", args=[lead.pk]) in body


@pytest.mark.usefixtures("db")
def test_the_empty_page_still_renders(client: Client) -> None:
    """No sources yet is not an error."""
    assert client.get(reverse("leads")).status_code == 200


@pytest.mark.usefixtures("db")
def test_newest_source_first(client: Client) -> None:
    """The latest addition is the one at the top."""
    Lead.objects.create(url="https://old.example.com")
    Lead.objects.create(url="https://new.example.com")

    body = client.get(reverse("leads")).content.decode()

    assert body.index("new.example.com") < body.index("old.example.com")


@pytest.mark.usefixtures("db")
def test_create_saves_and_redirects_back(client: Client) -> None:
    """A valid post adds a row and returns to the page."""
    response = client.post(
        reverse("lead-create"), {"url": "https://wellfound.com/jobs", "notes": "Remote only"}
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("leads")
    lead = Lead.objects.get()
    assert (lead.url, lead.notes) == ("https://wellfound.com/jobs", "Remote only")


@pytest.mark.usefixtures("db")
def test_create_with_notes_left_blank(client: Client) -> None:
    """Notes are optional."""
    client.post(reverse("lead-create"), {"url": "https://wellfound.com/jobs"})

    assert Lead.objects.get().notes == ""


@pytest.mark.parametrize("url", ["", "not a link"])
@pytest.mark.usefixtures("db")
def test_create_rejects_a_bad_link(client: Client, url: str) -> None:
    """The page comes back with the error; nothing is saved."""
    response = client.post(reverse("lead-create"), {"url": url, "notes": "kept"})

    assert response.status_code == 200
    assert not Lead.objects.exists()
    body = response.content.decode()
    assert "errorlist" in body
    assert "kept" in body


def test_update_changes_the_row(client: Client, lead: Lead) -> None:
    """Saving a row writes both fields."""
    response = client.post(
        reverse("lead-update", args=[lead.pk]),
        {"url": "https://example.com/careers", "notes": "Moved"},
    )

    assert response.status_code == 302
    lead.refresh_from_db()
    assert (lead.url, lead.notes) == ("https://example.com/careers", "Moved")


def test_update_rejects_a_bad_link(client: Client, lead: Lead) -> None:
    """A bad edit leaves the stored row alone and shows the error."""
    response = client.post(reverse("lead-update", args=[lead.pk]), {"url": "nope", "notes": "x"})

    assert response.status_code == 200
    assert "errorlist" in response.content.decode()
    lead.refresh_from_db()
    assert lead.url == "https://example.com/jobs"


@pytest.mark.usefixtures("db")
def test_update_unknown_is_404(client: Client) -> None:
    """No such row."""
    response = client.post(reverse("lead-update", args=[999]), {"url": "https://a.com"})

    assert response.status_code == 404


def test_delete_removes_the_row(client: Client, lead: Lead) -> None:
    """Delete is a POST and goes back to the page."""
    response = client.post(reverse("lead-delete", args=[lead.pk]))

    assert response.status_code == 302
    assert not Lead.objects.exists()


def test_delete_needs_post(client: Client, lead: Lead) -> None:
    """A GET must never delete."""
    response = client.get(reverse("lead-delete", args=[lead.pk]))

    assert response.status_code == 405
    assert Lead.objects.exists()


@pytest.mark.usefixtures("db")
def test_the_board_links_to_the_page(client: Client) -> None:
    """The way in is from the board's header, and the way back is on the page."""
    assert reverse("leads") in client.get(reverse("board")).content.decode()
    assert reverse("board") in client.get(reverse("leads")).content.decode()
