"""A blank note must never be clipped by the notes clamp — issue #26.

The clamp keeps a card to two notes or four lines. On an opportunity with no
notes the blank note's textarea alone fills that, so the Save and Cancel under
it were cut off and the note could not be saved.
"""

import pytest
from django.test import Client

from jobs.models import Opportunity

HTMX = {"HX-Request": "true"}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


def test_a_blank_note_carries_save_and_cancel(client: Client, opportunity: Opportunity) -> None:
    """The controls the clamp must not hide."""
    html = client.get(f"/opportunities/{opportunity.pk}/notes/new", headers=HTMX).content.decode()

    assert 'type="submit">Save</button>' in html
    assert ">Cancel</a>" in html
    assert "notes__item--new" in html


def test_the_script_leaves_a_blank_note_unclamped(board_js: str) -> None:
    """`syncNotes` has to know about the blank note, or the clamp swallows its buttons."""
    assert ".notes__item--new" in board_js
