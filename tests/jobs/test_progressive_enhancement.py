"""What the board does with the script, and without it — plan 001 §7.

There is no JavaScript test runner here and no npm to add one, so what is
checked is the contract between the template and the script: that every hook
the script reaches for is in the markup, and that a browser which never runs it
is left with a board that works.
"""

import datetime as dt
import re

import pytest
from django.test import Client

from jobs.models import Note, Opportunity, State, Step

# Every `[data-thing]` the script selects on.
_HOOKS = re.compile(r"\[data-(?P<hook>[a-z-]+)\]")


def render_board() -> str:
    """The board's HTML."""
    return Client().get("/").content.decode()


@pytest.fixture
def row(opportunity: Opportunity) -> Opportunity:
    """An opportunity with steps, notes and an ad, so every partial is on the page."""
    for slug, day in (("unremarkable", "2026-01-08"), ("going-well", "2026-02-01")):
        Step.objects.create(
            opportunity=opportunity,
            state=State.objects.get(slug=slug),
            date=dt.date.fromisoformat(day),
        )
    for day, body in ((3, "applied on a whim"), (20, "not sure about this")):
        Note.objects.create(
            opportunity=opportunity,
            body=body,
            created_at=dt.datetime(2026, 2, day, 9, 0, tzinfo=dt.UTC),
        )
    opportunity.job_description = "We are looking for an experienced engineer."
    opportunity.save()
    return opportunity


@pytest.mark.usefixtures("row")
def test_the_board_loads_the_script() -> None:
    """One script, vendored and deferred — no CDN, no build step (§5)."""
    html = render_board()

    assert "js/board.js" in html
    assert "defer" in html


def test_every_hook_the_script_reaches_for_is_in_the_markup(
    row: Opportunity, board_js: str
) -> None:
    """Renaming one and not the other is silent, so it fails here instead.

    Every markup the app renders is read, not only the resting board: `data-new`
    is on the one a create leaves behind (§6.6), and `data-editing` on the input
    a value swaps itself for. A hook that only appears mid-interaction is still
    a hook the script reaches for.
    """
    client = Client()
    html = (
        render_board()
        + client.get(f"/?new={row.pk}").content.decode()
        + client.get(f"/opportunities/{row.pk}/field/title").content.decode()
    )
    hooks = {match["hook"] for match in _HOOKS.finditer(board_js)}

    assert hooks, "the script selects on no data attributes at all"
    assert [hook for hook in sorted(hooks) if f"data-{hook}" not in html] == []


@pytest.mark.usefixtures("row")
def test_without_the_script_every_summary_is_already_open() -> None:
    """Collapsing is the enhancement. A browser that never ran it shows everything."""
    html = render_board()

    assert 'aria-expanded="true"' in html
    assert "data-collapsed" not in html
    assert "Applied" in html


@pytest.mark.usefixtures("row")
def test_the_summary_head_is_a_button_beside_the_heading() -> None:
    """The disclosure pattern: the heading names the row, the button toggles it.

    The button used to wrap the heading's two lines. It cannot any more: both of
    them are links now, and a button may not contain one. So it sits beside the
    heading as a chevron of its own, and CSS puts it in the corner.
    """
    html = render_board()
    heading = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.DOTALL)

    assert heading is not None
    assert "data-summary-toggle" not in heading[1]
    assert re.search(r"<button[^>]*data-summary-toggle[^>]*>", html) is not None
    assert re.search(r'aria-controls="summary-\d+"', html) is not None


@pytest.mark.usefixtures("row")
def test_the_arrows_start_hidden() -> None:
    """Visible only when they can move something, which only the script knows (§7)."""
    html = render_board()

    for hook in ("data-steps-prev", "data-steps-next"):
        assert re.search(rf"<button[^>]*{hook}[^>]*hidden", html) is not None


@pytest.mark.usefixtures("row")
def test_the_arrows_are_buttons_and_not_links() -> None:
    """They move a track in place; nothing navigates, so nothing belongs in the URL."""
    html = render_board()

    assert re.search(r"<button[^>]*data-steps-prev", html) is not None
    assert re.search(r"<button[^>]*data-steps-next", html) is not None
    assert 'href="#' not in html


@pytest.mark.usefixtures("row")
def test_without_the_script_every_note_is_shown() -> None:
    """Clamping the list is the enhancement, and the toggle that undoes it waits for it."""
    html = render_board()

    assert "data-notes-collapsed" not in html
    assert re.search(r"<button[^>]*data-notes-toggle[^>]*hidden", html) is not None
    assert "not sure about this" in html


@pytest.mark.usefixtures("row")
def test_the_notes_toggle_names_the_list_it_clamps() -> None:
    """A disclosure has to say what it opens, or nothing following it by ear can tell."""
    html = render_board()

    assert re.search(r'<ul[^>]*id="notes-\d+"', html) is not None
    assert re.search(r'aria-controls="notes-\d+"', html) is not None


@pytest.mark.usefixtures("row")
def test_the_job_description_opens_without_the_script() -> None:
    """A native `<details>`, so the one block that is closed by default still opens (§7)."""
    html = render_board()

    assert re.search(r"<details[^>]*opportunity__description", html) is not None


def test_the_script_is_what_clamps_the_notes(board_js: str) -> None:
    """The button ships `hidden` and the clamp is `.has-js` — both are the script's to set."""
    assert "data-notes-toggle" in board_js
    assert "data-notes-collapsed" in board_js


@pytest.mark.usefixtures("row")
def test_the_summary_card_carries_a_control_for_the_description() -> None:
    """On a laptop the block is out of sight until this opens it, so the card offers it (§7)."""
    html = render_board()

    assert re.search(r"<button[^>]*data-description-toggle[^>]*hidden", html) is not None
    assert re.search(r'aria-controls="description-\d+"', html) is not None
    assert re.search(r'<details[^>]*id="description-\d+"', html) is not None


@pytest.mark.usefixtures("row")
def test_the_description_control_starts_closed() -> None:
    """It ships `hidden` beside a block that is closed, and the script swaps both round."""
    html = render_board()

    assert re.search(r'<button[^>]*data-description-toggle[^>]*aria-expanded="false"', html)
    assert re.search(r"<details[^>]*opportunity__description[^>]*\sopen", html) is None


def test_the_script_opens_the_description_from_the_summary(board_js: str) -> None:
    """The card's control and the block's own bar drive the same element (§7)."""
    assert "data-description-toggle" in board_js
    assert "data-description]" in board_js


@pytest.mark.usefixtures("opportunity")
def test_a_row_with_no_ad_offers_no_description_control() -> None:
    """A control that opens nothing is worse than no control."""
    assert "data-description-toggle" not in render_board()
