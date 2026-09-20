"""The read-only board — plan 001 §7, phase 3.

These tests go through the rendered page, because the board is markup plus one
stylesheet and the only way to check the boundary in §6.3 is to look at what
the template emits: identity as `data-state` and `data-group`, never an
appearance.
"""

import datetime as dt
import re

import pytest
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import DjangoAssertNumQueries

from jobs.models import Company, Group, Opportunity, State, Step

BOARD_URL = "/"

_DETAILS = re.compile(r"<details\b.*?</details>", re.DOTALL)
# The track holds `<article>` cards and no nested `<div>`, so this stops at its
# own closing tag.
_TRACK = re.compile(r"<div class=\"opportunity__track\"[^>]*>(.*?)</div>", re.DOTALL)


def render_board() -> str:
    """The board's HTML."""
    return Client().get(BOARD_URL).content.decode()


def add_opportunity(company: Company, *, title: str, **fields: object) -> Opportunity:
    """A live opportunity at `company`."""
    return Opportunity.objects.create(
        company=company, title=title, date=dt.date(2026, 1, 5), **fields
    )


def add_step(opportunity: Opportunity, *, slug: str, date: str, title: str = "") -> Step:
    """A saved step in one of the seeded states (§6.1)."""
    return Step.objects.create(
        opportunity=opportunity,
        state=State.objects.get(slug=slug),
        date=dt.date.fromisoformat(date),
        title=title or slug,
    )


@pytest.mark.usefixtures("db")
def test_the_board_answers_at_the_root() -> None:
    """`GET /` is the whole app (§7)."""
    response = Client().get(BOARD_URL)

    assert response.status_code == 200


def test_an_opportunity_with_no_steps_still_renders(opportunity: Opportunity) -> None:
    """A brand new row has a summary card and nothing to its right (§4.5, §7)."""
    html = render_board()

    assert f'id="opportunity-{opportunity.pk}"' in html
    assert opportunity.title in html
    assert "card--summary" in html
    assert "card--step" not in html


def test_steps_render_newest_first(opportunity: Opportunity) -> None:
    """Newest to the left of the steps, oldest to the right (§7, §4.5)."""
    add_step(opportunity, slug="going-well", date="2026-01-06", title="first call")
    add_step(opportunity, slug="going-well", date="2026-03-02", title="offer chat")
    add_step(opportunity, slug="going-well", date="2026-02-01", title="tech screen")

    html = render_board()

    assert [html.index(title) for title in ("offer chat", "tech screen", "first call")] == sorted(
        html.index(title) for title in ("offer chat", "tech screen", "first call")
    )


def test_the_board_orders_its_rows_by_the_rules(company: Company) -> None:
    """The board renders `in_board_order`; §4.5 decides it, not the template (§6.3)."""
    calm = add_opportunity(company, title="calm row")
    add_step(calm, slug="going-well", date="2026-06-01")
    alarmed = add_opportunity(company, title="alarmed row")
    add_step(alarmed, slug="error", date="2026-01-01")

    html = render_board()

    assert html.index("alarmed row") < html.index("calm row")


def test_step_cards_carry_their_state_and_group(opportunity: Opportunity) -> None:
    """The template emits identity; CSS turns it into colour (§6.3)."""
    add_step(opportunity, slug="bad-feeling", date="2026-02-01")

    html = render_board()

    assert 'data-state="bad-feeling"' in html
    assert 'data-group="complete"' in html


def test_a_state_with_no_rule_of_its_own_renders_in_its_groups_colours(
    opportunity: Opportunity, palette_css: str
) -> None:
    """Adding a state is a data change: no CSS written, no broken card (§6.3)."""
    on_hold = State.objects.create(slug="on-hold", name="ON_HOLD", group=Group.DUE, sort_order=13)
    Step.objects.create(opportunity=opportunity, state=on_hold, date=dt.date(2026, 2, 1))

    html = render_board()

    assert 'data-state="on-hold"' in html
    assert 'data-group="due"' in html
    assert '[data-state="on-hold"]' not in palette_css
    assert '[data-group="due"]' in palette_css


def test_the_state_name_is_printed_on_every_card(opportunity: Opportunity) -> None:
    """Colour is never the only channel — the name is on the card too (§6.4)."""
    add_step(opportunity, slug="ghosted", date="2026-02-01")

    assert "Ghosted" in render_board()


def test_no_template_comment_reaches_the_page(opportunity: Opportunity) -> None:
    """Django's `{# #}` is single-line only, so a wrapped one renders as body text.

    Every partial has to be on the page for this to mean anything, so the row
    needs a step and a comment as well as a summary card.
    """
    opportunity.comments = "a pasted job ad"
    opportunity.save()
    add_step(opportunity, slug="going-well", date="2026-02-01")

    html = render_board()

    assert "card--step" in html
    assert "{#" not in html
    assert "#}" not in html


def test_the_steps_sit_in_a_track_of_their_own(opportunity: Opportunity) -> None:
    """A row is two blocks, and the steps block holds a track and its arrows (§7)."""
    add_step(opportunity, slug="going-well", date="2026-02-01", title="panel")
    add_step(opportunity, slug="due", date="2026-03-01", title="references")

    html = render_board()
    track = _TRACK.search(html)

    assert track is not None
    assert track[1].count("card--step") == 2
    assert "card--summary" not in track[1]
    assert "steps__arrow" not in track[1]


@pytest.mark.usefixtures("opportunity")
def test_a_row_with_no_steps_still_has_a_track_to_put_them_in() -> None:
    """Phase 4 swaps steps into it, so it is there whether or not it holds any yet (§7)."""
    assert "opportunity__track" in render_board()


def test_a_step_in_the_default_state_prints_no_state_name(opportunity: Opportunity) -> None:
    """UNREMARKABLE has an empty name, so its card shows the step and no label (§6.6)."""
    add_step(opportunity, slug="unremarkable", date="2026-02-01", title="Applied via site")

    html = render_board()

    assert "Applied via site" in html
    assert 'data-state="unremarkable"' in html
    # One subtitle on the page: the summary card's company. The step card has none.
    assert html.count('class="card__subtitle"') == 1


def test_a_long_comment_is_collapsed_behind_a_details(opportunity: Opportunity) -> None:
    """The summary card holds the pasted job ad — 1870 characters in the sample (§4.8, §7)."""
    opportunity.comments = "lorem ipsum " * 167
    opportunity.save()

    html = render_board()

    collapsed = [block for block in _DETAILS.findall(html) if opportunity.comments in block]

    assert len(opportunity.comments) > 2000
    assert collapsed, "a 2000 character comment has to sit behind a <details>"


@pytest.mark.usefixtures("opportunity")
def test_a_row_with_no_comment_has_nothing_to_expand() -> None:
    """An empty `<details>` is a control that does nothing."""
    assert "<details" not in render_board()


def test_the_board_shows_live_rows_and_counts_the_archived(company: Company) -> None:
    """Not seeing archived rows is the point of archiving; the count is all that leaks (§6.5)."""
    add_opportunity(company, title="still going")
    add_opportunity(company, title="put away", archived_at=timezone.now())

    html = render_board()

    assert "still going" in html
    assert "put away" not in html
    assert "1 archived" in html


def test_the_board_costs_the_same_however_many_rows_it_has(
    company: Company, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """Rows, steps, states, and the archived count — four queries, not four per row (§4.5)."""
    for index in range(3):
        row = add_opportunity(company, title=f"row {index}")
        add_step(row, slug="due", date="2026-01-01")

    with django_assert_num_queries(4):
        render_board()
