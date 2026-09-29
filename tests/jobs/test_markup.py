"""Bullet lists in step comments and notes.

Not markdown: one construct, a line starting `- `, `* ` or `•`, becomes a list
item. Everything is escaped before any tag is added, so what is typed can never
become markup of its own. The function is pure, so most of this needs no
database; the last tests render the board to show where it applies.
"""

import datetime as dt

import pytest
from django.test import Client

from jobs.markup import bullets
from jobs.models import Note, Opportunity, State, Step


def test_plain_text_is_escaped_and_otherwise_left_alone() -> None:
    """No list, no change beyond escaping."""
    assert bullets("Tom & Jerry <3") == "Tom &amp; Jerry &lt;3"


def test_line_breaks_between_plain_lines_survive() -> None:
    """The containers collapse whitespace, so a typed line break becomes a `<br>`."""
    assert bullets("first\nsecond") == "first<br>second"


def test_consecutive_dash_lines_become_one_list() -> None:
    """The case that matters: notes written as a bullet list."""
    assert bullets("- one\n- two") == '<ul class="bullets"><li>one</li><li>two</li></ul>'


@pytest.mark.parametrize("marker", ["-", "*", "•"])
def test_every_common_marker_is_a_bullet(marker: str) -> None:
    """Typed dashes, typed stars, and bullets pasted from somewhere else."""
    assert bullets(f"{marker} one") == '<ul class="bullets"><li>one</li></ul>'


def test_indented_bullets_are_still_bullets() -> None:
    """A pasted list often arrives indented. It stays one flat list."""
    assert bullets("  - one\n    - two") == '<ul class="bullets"><li>one</li><li>two</li></ul>'


def test_text_around_a_list_keeps_its_place() -> None:
    """No `<br>` beside the list: a block already starts on its own line."""
    assert bullets("Intro\n- one\n- two\nOutro") == (
        'Intro<ul class="bullets"><li>one</li><li>two</li></ul>Outro'
    )


def test_a_blank_line_ends_one_list_and_starts_another() -> None:
    """Two lists, as typed."""
    assert bullets("- one\n\n- two") == (
        '<ul class="bullets"><li>one</li></ul><br><ul class="bullets"><li>two</li></ul>'
    )


def test_markup_inside_a_bullet_is_escaped() -> None:
    """The list is the only markup that gets through."""
    assert bullets("- <script>x</script>") == (
        '<ul class="bullets"><li>&lt;script&gt;x&lt;/script&gt;</li></ul>'
    )


def test_a_star_that_starts_a_word_is_not_a_bullet() -> None:
    """`*important*` is emphasis in markdown, and no list item here."""
    assert bullets("*important*") == "*important*"


def test_a_dash_with_nothing_after_it_is_not_a_bullet() -> None:
    """An empty item would be a disc beside nothing."""
    assert bullets("-") == "-"


@pytest.fixture
def step(opportunity: Opportunity, state: State) -> Step:
    """A step whose comment is a bullet list."""
    return Step.objects.create(
        opportunity=opportunity,
        state=state,
        date=dt.date(2026, 9, 1),
        title="Call",
        comments="- salary ok\n- remote <3",
    )


@pytest.mark.usefixtures("step")
def test_a_step_comment_renders_as_a_list_on_the_board() -> None:
    """Where the list appears, escaped as ever."""
    html = Client().get("/").content.decode()

    assert '<ul class="bullets"><li>salary ok</li><li>remote &lt;3</li></ul>' in html


def test_a_note_renders_as_a_list_on_the_board(opportunity: Opportunity) -> None:
    """The summary card's notes take the same treatment."""
    Note.objects.create(opportunity=opportunity, body="- replied\n- follow up Friday")

    html = Client().get("/").content.decode()

    assert '<ul class="bullets"><li>replied</li><li>follow up Friday</li></ul>' in html


def test_a_step_title_is_not_turned_into_a_list(opportunity: Opportunity, state: State) -> None:
    """Only the free-text fields take bullets; a title starting `- ` stays as typed."""
    Step.objects.create(
        opportunity=opportunity, state=state, date=dt.date(2026, 9, 1), title="- odd title"
    )

    html = Client().get("/").content.decode()

    assert "- odd title" in html
