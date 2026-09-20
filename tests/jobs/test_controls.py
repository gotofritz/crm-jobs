"""The row controls and the new-row highlight — plan 001 §7, §6.6.

Appearance is asserted against the stylesheet for the same reason the layout
contract is (see `test_layout.py`): whether a new row can be found once the
board has re-sorted around it is a decision that would be expensive to get
wrong and invisible to a unit test.

Nothing here reaches into Python for a colour or a size. If one turns up in a
template or a view, the board in §6.3 has been crossed and the test says so.
"""

import re

import pytest
from django.test import Client

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
PHONE = "@media (max-width: 30rem)"


@pytest.fixture(scope="session")
def forms_css(project_root) -> str:
    """The stylesheet that owns the controls, the editing affordances and the highlight."""
    return (project_root / "assets" / "forms.css").read_text()


def rule(css: str, selector: str) -> str:
    """The declarations of every rule with this exact selector, joined."""
    pattern = re.compile(r"(?<![\w-])" + re.escape(selector) + r"\s*\{([^}]*)\}")
    bodies = [match[1] for match in pattern.finditer(css)]

    assert bodies, f"{selector} is not in the stylesheet"

    return "\n".join(bodies)


# --- The stylesheet is wired in ---------------------------------------------


def test_the_controls_stylesheet_is_compiled(tailwind_input: str) -> None:
    """`app.css` imports it, relative to itself — a root-relative one fails the build."""
    assert '@import "./forms.css"' in tailwind_input


def test_the_compiled_stylesheet_carries_the_editing_rules(compiled_css: str) -> None:
    """`static/css/app.css` is committed, so it has to be rebuilt with the rest."""
    assert ".editable" in compiled_css


# --- The new row -----------------------------------------------------------


def test_the_new_row_is_highlighted_in_css(forms_css: str) -> None:
    """`data-new` is identity; what it looks like is the stylesheet's business (§6.3)."""
    assert "[data-new]" in forms_css


def test_the_highlight_respects_reduced_motion(forms_css: str) -> None:
    """A highlight that animates is an animation, and some people have asked for none."""
    assert "prefers-reduced-motion: reduce" in forms_css


# --- The boundary ----------------------------------------------------------


def test_no_colour_reaches_a_template(project_root) -> None:
    """If a hex value reaches a template the design is wrong (§6.3)."""
    for template in sorted((project_root / "src" / "jobs" / "templates").rglob("*.html")):
        assert not _HEX.search(template.read_text()), template.name


def test_no_colour_reaches_the_python(project_root) -> None:
    """The model layer knows nothing about how anything looks, and nor do the views (§6.3)."""
    for module in ("views.py", "forms.py", "models.py", "urls.py"):
        source = (project_root / "src" / "jobs" / module).read_text()
        assert not _HEX.search(source), module


# --- The controls ----------------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_every_control_is_a_link_or_a_form() -> None:
    """Without the script the board still mutates: htmx attributes are the second channel.

    Every `hx-get` sits on an anchor with an `href`, and every `hx-post` on a
    form with an `action`, so the same control works either way (§7).
    """
    html = Client().get("/").content.decode()

    for tag in re.findall(r"<(?:a|form|button)\b[^>]*>", html):
        if "hx-get=" in tag:
            assert "href=" in tag, tag
        if "hx-post=" in tag:
            assert "action=" in tag, tag


@pytest.mark.usefixtures("opportunity")
def test_every_mutating_form_carries_a_csrf_token() -> None:
    """A POST without one is rejected, script or no script."""
    html = Client().get("/").content.decode()

    assert html.count("csrfmiddlewaretoken") == html.count("<form")


# --- The script's part of it -----------------------------------------------


def test_the_script_re_enhances_a_swapped_row(board_js: str) -> None:
    """A row htmx swapped in has never been through `apply`, so it is re-run (§7).

    Without this the arrows, the notes clamp and the description toggle all stop
    working on the one row that just changed, which is the row being looked at.
    """
    assert "htmx:afterSwap" in board_js


def test_the_script_scrolls_a_new_row_into_view(board_js: str) -> None:
    """The worry that a new row moved is answered in presentation (§6.6)."""
    assert "data-new" in board_js
    assert "scrollIntoView" in board_js


def test_the_new_row_marker_is_cleared_after_it_is_seen(board_js: str) -> None:
    """The highlight is a moment, not a state: the next swap must not re-announce it."""
    assert "removeAttribute" in board_js


def test_the_scroll_respects_reduced_motion(board_js: str) -> None:
    """The script already reads the query for the step arrows; the same answer applies.

    The behaviour is an argument to the call, so it is the call itself that is
    read rather than the lines around it.
    """
    call = board_js[board_js.index("scrollIntoView") :].split(");", 1)[0]

    assert "STILL" in call


# --- Adding a step ---------------------------------------------------------


@pytest.mark.usefixtures("opportunity")
def test_adding_a_step_is_a_control_on_the_steps_block() -> None:
    """A step is added where the steps are, not from a link in the summary card."""
    html = Client().get("/").content.decode()

    assert "steps__add" in html
    assert "Add step" not in html[: html.index("opportunity__steps")]


@pytest.mark.usefixtures("opportunity")
def test_the_add_step_control_sits_against_the_summary() -> None:
    """First in the steps block, so it never scrolls away from the row it adds to.

    A new step is the newest, and the track runs newest-first from this end, so
    the control is also at the end the new card arrives at.
    """
    html = Client().get("/").content.decode()

    assert html.index("steps__add") < html.index("data-steps-prev")


@pytest.mark.usefixtures("opportunity")
def test_the_add_step_control_is_outside_the_track() -> None:
    """Inside it, the control would scroll away with the steps (§7)."""
    html = Client().get("/").content.decode()
    track = re.search(r'<div class="opportunity__track"[^>]*>(.*?)</div>', html, re.DOTALL)

    assert track is not None
    assert "steps__add" not in track[1]


@pytest.mark.usefixtures("opportunity")
def test_the_add_step_control_wears_the_arrow_box() -> None:
    """It is the navigation arrow's twin: same box, a `+` where the chevron is."""
    html = Client().get("/").content.decode()
    control = re.search(r"<a[^>]*steps__add[^>]*>.*?</a>", html, re.DOTALL)

    assert control is not None
    assert "steps__button" in control[0]
    assert "+" in control[0]
    assert "&rsaquo;" not in control[0]


@pytest.mark.usefixtures("opportunity")
def test_the_add_step_control_is_a_link_not_a_button() -> None:
    """Unlike the arrows it goes somewhere, so it stays a link and works unscripted."""
    html = Client().get("/").content.decode()
    control = re.search(r"<a[^>]*steps__add[^>]*>", html)

    assert control is not None
    assert "/steps/new" in control[0]
    assert "hidden" not in control[0]


def test_the_arrows_and_the_add_control_share_one_box(layout_css: str) -> None:
    """Looking exactly like the arrow is one rule both wear, not a second copy."""
    box = rule(layout_css, ".steps__button")

    assert "align-self: stretch" in box
    assert "width: 2.25rem" in box


def test_the_add_control_shows_without_the_script(layout_css: str) -> None:
    """The arrows wait for the script because only it knows if they can move (§7).

    This one always can, so it is not gated on `.has-js` the way they are.
    """
    assert "display: flex" in rule(layout_css, ".steps__add")
    assert ".has-js .steps__add" not in layout_css
