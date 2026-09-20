"""The mutation routes — plan 001 §7, phase 4.

One test per route, and then the behaviours the phase names: the first step, the
§4.6 regression, the archive, and the picklists that must not fork.

Two rules run through all of it. A mutation answers with the row it changed,
unless the change moved rows about, in which case it answers with the board
(AGENTS.md, "Django"). And every route works without htmx: the same POST from a
plain form redirects to the board, because the script is an enhancement (§7).
"""

import datetime as dt

import pytest
from django.test import Client
from django.utils import timezone

from jobs.models import Company, Note, Opportunity, Sector, State, Step

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A saved step to edit and delete."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug="due"),
        date=dt.date(2026, 2, 1),
        title="Second interview booked",
    )


@pytest.fixture
def note(opportunity: Opportunity) -> Note:
    """A saved note to edit and delete."""
    return Note.objects.create(opportunity=opportunity, body="Recruiter answered within a day")


def new_opportunity_post(**overrides: str) -> dict[str, str]:
    """The body of a create-an-opportunity POST."""
    return {
        "company": "Northwind Analytics",
        "title": "Staff Backend Engineer",
        "date": "2026-01-05",
    } | overrides


def step_post(**overrides: object) -> dict[str, object]:
    """The body of a save-a-step POST."""
    return {
        "state": State.objects.get(slug="due").pk,
        "date": "2026-02-01",
        "title": "Second interview booked",
    } | overrides


# --- GET, the form partials ------------------------------------------------


@pytest.mark.usefixtures("db")
def test_the_new_opportunity_form_is_a_partial(client: Client) -> None:
    """`GET /opportunities/new` returns a form, not a page (§7)."""
    response = client.get("/opportunities/new", headers=HTMX)

    assert response.status_code == 200
    body = response.content.decode()
    assert "<form" in body
    assert "<!doctype html>" not in body.lower()


def test_the_new_step_form_is_a_partial(client: Client, opportunity: Opportunity) -> None:
    """`GET /opportunities/<id>/steps/new` returns a form (§7)."""
    response = client.get(f"/opportunities/{opportunity.pk}/steps/new", headers=HTMX)

    assert response.status_code == 200
    assert "<form" in response.content.decode()


def test_the_new_note_form_is_a_partial(client: Client, opportunity: Opportunity) -> None:
    """`GET /opportunities/<id>/notes/new` returns a form (§4.4, notes split)."""
    response = client.get(f"/opportunities/{opportunity.pk}/notes/new", headers=HTMX)

    assert response.status_code == 200
    assert "<form" in response.content.decode()


# --- POST, opportunities ---------------------------------------------------


@pytest.mark.usefixtures("db")
def test_creating_an_opportunity_saves_it(client: Client) -> None:
    """`POST /opportunities/` creates the row (§7)."""
    response = client.post("/opportunities/", new_opportunity_post(), headers=HTMX)

    assert response.status_code == 200
    assert Opportunity.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_creating_an_opportunity_also_creates_its_first_step(client: Client) -> None:
    """The GAS app's behaviour, kept (§4.4)."""
    client.post("/opportunities/", new_opportunity_post(), headers=HTMX)

    opportunity = Opportunity.objects.get()

    assert opportunity.steps.count() == 1
    assert opportunity.steps.get().state.slug == "unremarkable"


@pytest.mark.usefixtures("db")
def test_creating_an_opportunity_answers_with_the_whole_board(client: Client) -> None:
    """A new row lands in sorted order, not on top, so the board re-renders (§6.6)."""
    response = client.post("/opportunities/", new_opportunity_post(), headers=HTMX)

    assert response.headers.get("HX-Retarget") == "#board"
    assert 'id="board"' in response.content.decode()


@pytest.mark.usefixtures("db")
def test_the_new_row_is_marked_so_it_can_be_highlighted(client: Client) -> None:
    """The worry that a new row moved is answered in presentation (§6.6)."""
    response = client.post("/opportunities/", new_opportunity_post(), headers=HTMX)

    created = Opportunity.objects.get()

    assert f'id="opportunity-{created.pk}"' in response.content.decode()
    assert "data-new" in response.content.decode()


@pytest.mark.usefixtures("company")
def test_typing_an_existing_company_reuses_it(client: Client) -> None:
    """The route creates no second `Acme` (§6.9)."""
    client.post("/opportunities/", new_opportunity_post(company="ACME"), headers=HTMX)

    assert Company.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_a_sector_typed_twice_is_one_row(client: Client) -> None:
    """`FinTech` and `fintech` resolve to one `Sector` (§6.9)."""
    client.post("/opportunities/", new_opportunity_post(company_sector="FinTech"), headers=HTMX)
    client.post(
        "/opportunities/",
        new_opportunity_post(company="Belmont Robotics", company_sector="fintech"),
        headers=HTMX,
    )

    assert Sector.objects.filter(name__iexact="fintech").count() == 1


@pytest.mark.usefixtures("db")
def test_an_invalid_create_re_renders_the_form(client: Client) -> None:
    """Validation errors come back in the form partial, no page reload (§7)."""
    response = client.post("/opportunities/", new_opportunity_post(title=""), headers=HTMX)

    assert response.status_code == 200
    body = response.content.decode()
    assert "<form" in body
    assert "This field is required." in body
    assert Opportunity.objects.count() == 0


def test_deleting_an_opportunity_swaps_the_row_out(
    client: Client, opportunity: Opportunity
) -> None:
    """`POST /opportunities/<id>/delete` answers with nothing to put in its place (§7)."""
    response = client.post(f"/opportunities/{opportunity.pk}/delete", headers=HTMX)

    assert response.status_code == 200
    assert f'id="opportunity-{opportunity.pk}"' not in response.content.decode()
    assert not Opportunity.objects.filter(pk=opportunity.pk).exists()


# --- POST, steps -----------------------------------------------------------


def test_creating_a_step_saves_it_against_its_opportunity(
    client: Client, opportunity: Opportunity
) -> None:
    """`POST /opportunities/<id>/steps/` (§7)."""
    response = client.post(f"/opportunities/{opportunity.pk}/steps/", step_post(), headers=HTMX)

    assert response.status_code == 200
    assert opportunity.steps.count() == 1


def test_a_step_keeps_several_contacts(client: Client, opportunity: Opportunity) -> None:
    """Several names, comma separated, each resolved the way a company is (§6.9)."""
    client.post(
        f"/opportunities/{opportunity.pk}/steps/",
        step_post(contacts="Ada Lovelace, Grace Hopper"),
        headers=HTMX,
    )

    saved = opportunity.steps.get()

    assert {person.name for person in saved.contacts.all()} == {"Ada Lovelace", "Grace Hopper"}


def test_an_invalid_step_re_renders_the_form(client: Client, opportunity: Opportunity) -> None:
    """A step with no state comes back as a form with its error (§7)."""
    response = client.post(
        f"/opportunities/{opportunity.pk}/steps/", step_post(state=""), headers=HTMX
    )

    assert "<form" in response.content.decode()
    assert opportunity.steps.count() == 0


def test_deleting_a_step_answers_with_the_row(client: Client, step: Step) -> None:
    """`POST /steps/<id>/delete` leaves the opportunity, so the row comes back (§7)."""
    response = client.post(f"/steps/{step.pk}/delete", headers=HTMX)

    assert response.status_code == 200
    assert not Step.objects.filter(pk=step.pk).exists()


# --- POST, notes and the job description -----------------------------------


def test_creating_a_note_saves_it(client: Client, opportunity: Opportunity) -> None:
    """`POST /opportunities/<id>/notes/` (notes split, §4.4)."""
    response = client.post(
        f"/opportunities/{opportunity.pk}/notes/",
        {"body": "Applied on the off chance"},
        headers=HTMX,
    )

    assert response.status_code == 200
    assert opportunity.notes.count() == 1


def test_an_invalid_note_re_renders_the_form(client: Client, opportunity: Opportunity) -> None:
    """An empty note is nothing, and the form says so rather than storing it."""
    response = client.post(f"/opportunities/{opportunity.pk}/notes/", {"body": ""}, headers=HTMX)

    assert "<form" in response.content.decode()
    assert opportunity.notes.count() == 0


def test_deleting_a_note_answers_with_the_row(client: Client, note: Note) -> None:
    """`POST /notes/<id>/delete` — the summary card re-renders without it."""
    response = client.post(f"/notes/{note.pk}/delete", headers=HTMX)

    assert response.status_code == 200
    assert not Note.objects.filter(pk=note.pk).exists()
    assert f'id="opportunity-{note.opportunity.pk}"' in response.content.decode()


# --- POST, the archive -----------------------------------------------------


def test_archiving_an_opportunity_swaps_the_row_out(
    client: Client, opportunity: Opportunity
) -> None:
    """`POST /opportunities/<id>/archive` sets one timestamp — that is the mechanism (§6.5)."""
    response = client.post(f"/opportunities/{opportunity.pk}/archive", headers=HTMX)

    opportunity.refresh_from_db()

    assert response.status_code == 200
    assert opportunity.archived_at is not None
    assert f'id="opportunity-{opportunity.pk}"' not in response.content.decode()


def test_the_board_excludes_archived_opportunities(
    client: Client, opportunity: Opportunity
) -> None:
    """Not seeing them is the point of archiving (§6.5)."""
    client.post(f"/opportunities/{opportunity.pk}/archive", headers=HTMX)

    body = client.get("/").content.decode()

    assert f'id="opportunity-{opportunity.pk}"' not in body
    assert "1 archived" in body


def test_unarchiving_puts_one_back(client: Client, opportunity: Opportunity) -> None:
    """`POST /opportunities/<id>/unarchive` clears the timestamp (§6.5)."""
    opportunity.archived_at = timezone.now()
    opportunity.save()

    client.post(f"/opportunities/{opportunity.pk}/unarchive", headers=HTMX)
    opportunity.refresh_from_db()

    assert opportunity.archived_at is None
    assert f'id="opportunity-{opportunity.pk}"' in client.get("/").content.decode()


@pytest.mark.usefixtures("opportunity")
def test_archiving_everything_live_empties_the_board(client: Client, company: Company) -> None:
    """The "I got a job" action, at the end of a burst (§6.5)."""
    Opportunity.objects.create(company=company, title="Other", date=dt.date(2026, 1, 6))

    response = client.post("/opportunities/archive-live", headers=HTMX)

    assert response.status_code == 200
    assert Opportunity.objects.live().count() == 0
    assert Opportunity.objects.archived().count() == 2


@pytest.mark.usefixtures("opportunity")
def test_archiving_everything_live_leaves_the_archive_alone(
    client: Client, company: Company
) -> None:
    """An already-archived row keeps the timestamp that says which burst it was (§6.5)."""
    earlier = Opportunity.objects.create(
        company=company,
        title="Old",
        date=dt.date(2025, 11, 1),
        archived_at=dt.datetime(2025, 12, 1, tzinfo=dt.UTC),
    )

    client.post("/opportunities/archive-live", headers=HTMX)
    earlier.refresh_from_db()

    assert earlier.archived_at == dt.datetime(2025, 12, 1, tzinfo=dt.UTC)


@pytest.mark.usefixtures("opportunity")
def test_nothing_is_deleted_by_archiving(client: Client) -> None:
    """All three archive actions are reversible because nothing is removed (§6.5)."""
    client.post("/opportunities/archive-live", headers=HTMX)

    assert Opportunity.objects.count() == 1


# --- Without the script ----------------------------------------------------


@pytest.mark.usefixtures("db")
def test_a_plain_post_redirects_to_the_board(client: Client) -> None:
    """Without htmx the same route still works; it just answers with a page (§7)."""
    response = client.post("/opportunities/", new_opportunity_post())

    assert response.status_code == 302
    assert Opportunity.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_a_plain_post_points_at_the_new_row(client: Client) -> None:
    """The highlight survives a full page load, because the board reads it off the URL (§6.6)."""
    response = client.post("/opportunities/", new_opportunity_post())

    created = Opportunity.objects.get()

    assert response.headers["Location"] == f"/?new={created.pk}"


@pytest.mark.usefixtures("db")
def test_a_plain_get_of_a_form_returns_a_whole_page(client: Client) -> None:
    """A form opened without htmx is a page of its own, not a bare partial (§7)."""
    response = client.get("/opportunities/new")

    assert response.status_code == 200
    assert "<!doctype html>" in response.content.decode().lower()


def test_a_get_cannot_mutate(client: Client, opportunity: Opportunity) -> None:
    """The mutating routes refuse anything but POST."""
    assert client.get(f"/opportunities/{opportunity.pk}/delete").status_code == 405
    assert client.get(f"/opportunities/{opportunity.pk}/archive").status_code == 405
    assert client.get("/opportunities/archive-live").status_code == 405


@pytest.mark.usefixtures("db")
def test_a_missing_row_is_a_404(client: Client) -> None:
    """A stale row id is not found rather than a server error."""
    assert client.post("/opportunities/999/delete", headers=HTMX).status_code == 404
    assert client.get("/steps/999/edit", headers=HTMX).status_code == 404
    assert client.get("/notes/999/edit", headers=HTMX).status_code == 404


# --- The datalists ---------------------------------------------------------


@pytest.mark.usefixtures("company")
def test_the_form_offers_the_companies_already_known(client: Client) -> None:
    """A `<datalist>` is what replaces a company screen (§6.9)."""
    body = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert "<datalist" in body
    assert "Acme" in body


@pytest.mark.usefixtures("db")
def test_the_form_offers_the_sources_and_sectors_already_known(client: Client) -> None:
    """The seeded picklists show up as suggestions, not as a fixed vocabulary (§6.10)."""
    body = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert "LinkedIn" in body
    assert "Fintech" in body


@pytest.mark.usefixtures("contact")
def test_the_step_form_offers_the_contacts_already_known(
    client: Client, opportunity: Opportunity
) -> None:
    """Typing a contact is the only way to attach one, so the names are suggested (§6.9)."""
    body = client.get(f"/opportunities/{opportunity.pk}/steps/new", headers=HTMX).content.decode()

    assert "Ada Lovelace" in body


# --- Confirmations ---------------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_deleting_asks_first(client: Client) -> None:
    """A delete is the one thing here that is not reversible, so it confirms (§6.5)."""
    body = client.get("/").content.decode()

    assert "hx-confirm" in body


@pytest.mark.usefixtures("opportunity")
def test_bulk_archive_confirms_with_its_count(client: Client, company: Company) -> None:
    """Archiving everything live touches every row at once, so it says how many (§6.5)."""
    Opportunity.objects.create(company=company, title="Other", date=dt.date(2026, 1, 6))

    body = client.get("/").content.decode()

    assert "Archive all 2" in body
