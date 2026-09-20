"""How the notes read on a card — plan 001 §7.

A note is a row with its own delete, so the list is not prose and not a
bulleted aside. Each entry leads with the control that removes it, sitting
where a bullet would and aligned to the first line of the note; a dashed rule
separates one entry from the next.

The list also stays on the card while the card is being edited. It cannot be
*in* the edit form — a note's delete is a form of its own and forms do not
nest — so it sits beside it, inside the card.
"""

import re

import pytest
from django.test import Client

from jobs.models import Note, Opportunity

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def noted(opportunity: Opportunity) -> Opportunity:
    """An opportunity with two notes on it."""
    for body in ("Applied on a whim", "Recruiter answered within a day"):
        Note.objects.create(opportunity=opportunity, body=body)
    return opportunity


@pytest.fixture(scope="session")
def notes_css(project_root) -> str:
    """The stylesheets that between them decide what the list looks like."""
    return (project_root / "assets" / "board.css").read_text() + (
        project_root / "assets" / "forms.css"
    ).read_text()


def rule(css: str, selector: str) -> str:
    """The declarations of every rule with this exact selector, joined."""
    pattern = re.compile(r"(?<![\w-])" + re.escape(selector) + r"\s*\{([^}]*)\}")
    bodies = [match[1] for match in pattern.finditer(css)]

    assert bodies, f"{selector} is not in the stylesheet"

    return "\n".join(bodies)


def item(html: str) -> str:
    """The first note in the list."""
    match = re.search(r'<li class="notes__item".*?</li>', html, re.DOTALL)

    assert match is not None, "no note on the card"

    return match[0]


# --- The list stays while the card is edited --------------------------------


def test_the_notes_are_on_the_card_while_it_is_edited(client: Client, noted: Opportunity) -> None:
    """Editing the fields is no reason for what is written about the row to go."""
    body = client.get(f"/opportunities/{noted.pk}/edit", headers=HTMX).content.decode()

    assert "Applied on a whim" in body
    assert "notes__list" in body


def test_the_notes_are_not_inside_the_edit_form(client: Client, noted: Opportunity) -> None:
    """A note's delete is a form, and a form inside a form is not valid markup.

    The browser closes the outer one at the inner one's start tag, which throws
    the fields after it out of the form that was supposed to submit them.
    """
    body = client.get(f"/opportunities/{noted.pk}/edit", headers=HTMX).content.decode()
    edit_form = re.search(r'<form class="card__edit".*?</form>', body, re.DOTALL)

    assert edit_form is not None
    assert "<form" not in edit_form[0][len('<form class="card__edit"') :]
    assert "notes__item" not in edit_form[0]


def test_the_notes_are_still_inside_the_card(client: Client, noted: Opportunity) -> None:
    """Beside the form, not adrift of the card it belongs to."""
    body = client.get(f"/opportunities/{noted.pk}/edit", headers=HTMX).content.decode()
    card = re.search(r'<article class="card card--summary".*?</article>', body, re.DOTALL)

    assert card is not None
    assert "notes__item" in card[0]


# --- What an entry looks like ----------------------------------------------


@pytest.mark.usefixtures("noted")
def test_the_delete_control_comes_before_the_note(client: Client) -> None:
    """It stands where the bullet used to, so it reads as the list's marker."""
    entry = item(client.get("/").content.decode())

    assert entry.index("notes__delete") < entry.index("Recruiter answered")


def test_the_list_has_no_bullets(notes_css: str) -> None:
    """The delete control is the marker; a bullet beside it would be two."""
    declarations = rule(notes_css, ".notes__list")

    assert "list-style: none" in declarations
    assert "padding-left: 1.1rem" not in declarations


def test_an_entry_is_separated_by_a_dashed_rule(notes_css: str) -> None:
    """Between entries, not around them, so the first has no line above it."""
    declarations = rule(notes_css, ".notes__item + .notes__item")

    assert "dashed" in declarations
    assert "border-top" in declarations


def test_the_control_is_ranged_with_the_first_line(notes_css: str) -> None:
    """A two-line note keeps its control at the top rather than centred on it."""
    declarations = rule(notes_css, ".notes__item")

    assert "align-items: start" in declarations
    assert "grid" in declarations


def test_the_delete_control_reads_as_a_button(notes_css: str) -> None:
    """A border and a shadow, so it looks like the thing it is."""
    declarations = rule(notes_css, ".notes__delete")

    assert "border:" in declarations
    assert "box-shadow:" in declarations


# --- What has to keep working ----------------------------------------------


def test_the_clamp_still_counts_entries(notes_css: str) -> None:
    """Two notes or four lines, whichever bites first (§7) — restyling is not a rewrite."""
    assert ".notes__item:nth-child(n + 3)" in notes_css


def test_deleting_a_note_still_works(client: Client, noted: Opportunity) -> None:
    """The control changed shape, not job."""
    note = noted.notes.first()
    assert note is not None

    client.post(f"/notes/{note.pk}/delete", headers=HTMX)

    assert noted.notes.count() == 1


# --- A form in an entry is not the remove control ---------------------------


def test_only_the_remove_control_is_flattened(notes_css: str) -> None:
    """`display: contents` was for the form wrapping the remove button, and no other.

    Applied to every form in an entry it also flattens the one that writes a
    note, dropping its Save into the narrow marker column — nine pixels wide
    and seventy tall, a letter per line.
    """
    assert "display: contents" in rule(notes_css, ".notes__item .notes__remove")

    with pytest.raises(AssertionError):
        rule(notes_css, ".notes__item form")


def test_the_remove_control_says_which_form_it_is(project_root) -> None:
    """The class is what the rule above hangs on."""
    markup = (
        project_root / "src" / "jobs" / "templates" / "jobs" / "_note_controls.html"
    ).read_text()

    assert "notes__remove" in markup


def test_a_blank_note_has_no_marker_column(notes_css: str) -> None:
    """There is nothing to remove yet, so the entry is just the form."""
    assert "display: block" in rule(notes_css, ".notes__item--new")


def test_editing_a_note_keeps_the_form_in_one_piece(notes_css: str) -> None:
    """An input replacing a value sits in that value's cell, not spread across the grid."""
    assert "display: block" in rule(notes_css, ".notes__item .editable__form")
