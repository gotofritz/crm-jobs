"""The visible archive — plan 006.

`/archive/` is the board again with archived rows, and both pages carry a bulk
bar: tick rows, pick an action, go. The bar is a plain form, so it works
without the script (§7).
"""

import datetime as dt

import pytest
from django.test import Client

from jobs.models import Company, Opportunity

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def archived(company: Company) -> Opportunity:
    """An opportunity that has been put away."""
    return Opportunity.objects.create(
        company=company,
        title="Put away",
        date=dt.date(2025, 11, 1),
        archived_at=dt.datetime(2025, 12, 1, tzinfo=dt.UTC),
    )


# --- The page --------------------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_the_archive_lists_archived_rows_only(client: Client, archived: Opportunity) -> None:
    """Live rows are the board's business."""
    body = client.get("/archive/").content.decode()

    assert f'id="opportunity-{archived.pk}"' in body
    assert "Staff Software Engineer" not in body


def test_the_archive_is_newest_archived_first(client: Client, company: Company) -> None:
    """`in_archive_order()` — most recently put away on top (§6.5)."""
    older = Opportunity.objects.create(
        company=company,
        title="Older",
        date=dt.date(2025, 1, 1),
        archived_at=dt.datetime(2025, 2, 1, tzinfo=dt.UTC),
    )
    newer = Opportunity.objects.create(
        company=company,
        title="Newer",
        date=dt.date(2025, 1, 1),
        archived_at=dt.datetime(2025, 3, 1, tzinfo=dt.UTC),
    )

    body = client.get("/archive/").content.decode()

    assert body.index(f"opportunity-{newer.pk}") < body.index(f"opportunity-{older.pk}")


@pytest.mark.usefixtures("opportunity", "archived")
def test_the_archive_heading_links_back_to_the_board(client: Client) -> None:
    """The heading reads Archive, Y archived, X live, with X live a link."""
    body = client.get("/archive/").content.decode()

    assert "Archive" in body
    assert '<a href="/">1 live</a>' in body
    assert "1 archived" in body


@pytest.mark.usefixtures("opportunity", "archived")
def test_the_board_counts_link_to_the_archive(client: Client) -> None:
    """The archived count is the way in."""
    body = client.get("/").content.decode()

    assert '<a href="/archive/">1 archived</a>' in body
    assert "1 live" in body


@pytest.mark.usefixtures("archived")
def test_the_archive_has_no_new_opportunity_button(client: Client) -> None:
    """Nothing is added to a pile that is put away."""
    assert "New opportunity" not in client.get("/archive/").content.decode()


@pytest.mark.usefixtures("opportunity")
def test_the_board_new_opportunity_button_is_primary(client: Client) -> None:
    """Solid fill, so it stands out; the rule itself is in the stylesheet."""
    body = client.get("/").content.decode()

    assert 'class="button button--primary"' in body


@pytest.mark.usefixtures("db")
def test_an_empty_archive_says_so(client: Client) -> None:
    """Not a blank page."""
    assert "Nothing archived." in client.get("/archive/").content.decode()


# --- The bulk bar ----------------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_the_board_offers_archive(client: Client) -> None:
    """One entry, and the old all-or-nothing button is gone."""
    body = client.get("/").content.decode()

    assert '<option value="archive">Archive</option>' in body
    assert "Archive all" not in body
    assert "archive-live" not in body
    assert "data-select-all" in body


@pytest.mark.usefixtures("archived")
def test_the_archive_offers_unarchive(client: Client) -> None:
    """The same bar, the other action."""
    body = client.get("/archive/").content.decode()

    assert '<option value="unarchive">Unarchive</option>' in body
    assert '<option value="archive"' not in body


def test_every_row_has_a_checkbox_before_its_title(
    client: Client, opportunity: Opportunity
) -> None:
    """Tied to the header form by `form=`, because forms do not nest."""
    body = client.get("/").content.decode()
    box = f'name="ids" value="{opportunity.pk}"'

    assert box in body
    assert 'form="bulk-form"' in body
    assert body.index(box) < body.index("card__title", body.index(f"opportunity-{opportunity.pk}"))


# --- POST ------------------------------------------------------------------


def test_bulk_archive_archives_the_ticked_rows_only(
    client: Client, opportunity: Opportunity, company: Company
) -> None:
    """Unticked rows stay live."""
    other = Opportunity.objects.create(company=company, title="Other", date=dt.date(2026, 1, 6))

    response = client.post(
        "/opportunities/bulk",
        {"action": "archive", "ids": [opportunity.pk], "view": "board"},
        headers=HTMX,
    )
    opportunity.refresh_from_db()
    other.refresh_from_db()

    assert response.status_code == 200
    assert opportunity.archived_at is not None
    assert other.archived_at is None
    assert f'id="opportunity-{other.pk}"' in response.content.decode()
    assert f'id="opportunity-{opportunity.pk}"' not in response.content.decode()


def test_bulk_unarchive_restores_the_ticked_rows(client: Client, archived: Opportunity) -> None:
    """The archive's own action."""
    client.post(
        "/opportunities/bulk",
        {"action": "unarchive", "ids": [archived.pk], "view": "archive"},
        headers=HTMX,
    )
    archived.refresh_from_db()

    assert archived.archived_at is None


@pytest.mark.usefixtures("opportunity")
def test_bulk_archive_leaves_archived_timestamps_alone(
    client: Client, archived: Opportunity
) -> None:
    """A stale page must not re-stamp an old burst (§6.5)."""
    client.post(
        "/opportunities/bulk",
        {"action": "archive", "ids": [archived.pk], "view": "board"},
        headers=HTMX,
    )
    archived.refresh_from_db()

    assert archived.archived_at == dt.datetime(2025, 12, 1, tzinfo=dt.UTC)


def test_bulk_unarchive_ignores_live_rows(client: Client, opportunity: Opportunity) -> None:
    """Unarchiving a live row is a no-op."""
    client.post(
        "/opportunities/bulk",
        {"action": "unarchive", "ids": [opportunity.pk], "view": "archive"},
        headers=HTMX,
    )
    opportunity.refresh_from_db()

    assert opportunity.archived_at is None


def test_bulk_rejects_an_unknown_action(client: Client, opportunity: Opportunity) -> None:
    """A whitelist, not a getattr."""
    response = client.post("/opportunities/bulk", {"action": "delete", "ids": [opportunity.pk]})

    assert response.status_code == 400
    assert Opportunity.objects.count() == 1


@pytest.mark.usefixtures("opportunity")
def test_bulk_with_nothing_ticked_changes_nothing(client: Client) -> None:
    """No ids, no change, and still a page back."""
    response = client.post("/opportunities/bulk", {"action": "archive", "view": "board"})

    assert response.status_code == 302
    assert Opportunity.objects.archived().count() == 0


def test_bulk_ignores_junk_ids(client: Client, opportunity: Opportunity) -> None:
    """Form input is not trusted."""
    response = client.post(
        "/opportunities/bulk", {"action": "archive", "ids": ["x", str(opportunity.pk)]}
    )

    assert response.status_code == 302
    opportunity.refresh_from_db()
    assert opportunity.archived_at is not None


def test_bulk_without_htmx_redirects_to_the_page_it_came_from(
    client: Client, archived: Opportunity
) -> None:
    """The script is an enhancement (§7)."""
    to_archive = client.post(
        "/opportunities/bulk", {"action": "unarchive", "ids": [archived.pk], "view": "archive"}
    )
    to_board = client.post("/opportunities/bulk", {"action": "archive", "view": "board"})

    assert to_archive["Location"] == "/archive/"
    assert to_board["Location"] == "/"


def test_bulk_is_post_only(client: Client) -> None:
    """Never a GET that changes things."""
    assert client.get("/opportunities/bulk").status_code == 405


def test_bulk_never_deletes(client: Client, opportunity: Opportunity) -> None:
    """Reversible, like the rest of the archive (§6.5)."""
    client.post("/opportunities/bulk", {"action": "archive", "ids": [opportunity.pk]})

    assert Opportunity.objects.count() == 1


# --- Stylesheet and script -------------------------------------------------


def test_the_primary_button_is_a_solid_fill_with_light_text(compiled_css: str) -> None:
    """New opportunity stands out; the compiled sheet is what is served."""
    assert ".button--primary" in compiled_css
    assert "--primary-bg" in compiled_css


def test_the_script_drives_the_bulk_bar(board_js: str) -> None:
    """Without it the bar still submits; with it the bar waits for a tick."""
    for hook in ("data-select-all", "data-select", "data-bulk-action", "data-bulk-go"):
        assert hook in board_js


@pytest.mark.usefixtures("opportunity")
def test_without_the_script_the_bar_is_usable(client: Client) -> None:
    """The toggle is hidden, the select and button are not disabled."""
    body = client.get("/").content.decode()

    assert "data-select-all hidden" in body
    assert "disabled" not in body.split('id="bulk-form"')[1].split("</form>")[0]
