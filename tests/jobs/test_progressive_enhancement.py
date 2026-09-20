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

from jobs.models import Opportunity, State, Step

# Every `[data-thing]` the script selects on.
_HOOKS = re.compile(r"\[data-(?P<hook>[a-z-]+)\]")


def render_board() -> str:
    """The board's HTML."""
    return Client().get("/").content.decode()


@pytest.fixture
def row(opportunity: Opportunity) -> Opportunity:
    """An opportunity with steps, so every partial is on the page."""
    for slug, day in (("unremarkable", "2026-01-08"), ("going-well", "2026-02-01")):
        Step.objects.create(
            opportunity=opportunity,
            state=State.objects.get(slug=slug),
            date=dt.date.fromisoformat(day),
        )
    return opportunity


@pytest.mark.usefixtures("row")
def test_the_board_loads_the_script() -> None:
    """One script, vendored and deferred — no CDN, no build step (§5)."""
    html = render_board()

    assert "js/board.js" in html
    assert "defer" in html


@pytest.mark.usefixtures("row")
def test_every_hook_the_script_reaches_for_is_in_the_markup(board_js: str) -> None:
    """Renaming one and not the other is silent, so it fails here instead."""
    html = render_board()
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
def test_the_summary_head_is_a_button_inside_the_heading() -> None:
    """The disclosure pattern: the heading names the row, the button toggles it."""
    html = render_board()

    assert re.search(r"<h2[^>]*>\s*<button[^>]*data-summary-toggle", html) is not None


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
