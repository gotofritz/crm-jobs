"""The tab icon — vendored like everything else in `static/`.

A browser asks for `/favicon.ico` when a page names no icon, which is where the
404 in the log came from. Naming one stops the request and puts something in
the tab.

It is served from `static/` rather than inlined as a data URI: the project
already serves its own assets through WhiteNoise, and a URI with a glyph in it
is a percent-encoding trap for no gain.
"""

import pytest
from django.test import Client


def test_the_icon_is_vendored(project_root) -> None:
    """A file in the repository, not a fetch from anywhere else (AGENTS.md)."""
    assert (project_root / "static" / "icon.svg").exists()


@pytest.mark.usefixtures("db")
def test_the_board_names_an_icon() -> None:
    """Without this the browser guesses at `/favicon.ico` and gets a 404."""
    html = Client().get("/").content.decode()

    assert 'rel="icon"' in html
    assert "icon.svg" in html


@pytest.mark.usefixtures("db")
def test_the_icon_comes_from_static() -> None:
    """Same rule as the stylesheet and the scripts: nothing off-site (§5)."""
    html = Client().get("/").content.decode()

    assert "/static/icon.svg" in html


def test_the_icon_is_an_svg_of_one_glyph(project_root) -> None:
    """One character on a square canvas, which is all a 16px tab can show."""
    svg = (project_root / "static" / "icon.svg").read_text()

    assert svg.startswith("<svg")
    assert "viewBox" in svg
    assert "🎯" in svg


def test_the_icon_is_small_enough_to_be_free(project_root) -> None:
    """A tab icon is fetched on every cold load; a kilobyte is already generous."""
    assert (project_root / "static" / "icon.svg").stat().st_size < 1024
