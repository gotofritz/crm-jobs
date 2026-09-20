"""The pasted ad lays out in columns — plan 001 §7.

The block is as wide as the board and one measure that wide is unreadable, so
`.description__body` is `columns: 22rem`. That only works on content the
browser can break: an `inline-block` is one unbreakable box, so making every
value editable turned the ad into a single monolith that lands in one column
and leaves the rest empty.

A block box fragments. `display: inline` also fragments, but an inline box sits
on the containing block's baseline, which drops a tall ad to the bottom of its
line — so it is `block`, not merely "not inline-block".
"""

import re

import pytest
from django.test import Client

from jobs.models import Opportunity


@pytest.fixture(scope="session")
def styles(project_root) -> str:
    """Both hand-written stylesheets, since the rule spans the two concerns."""
    return (project_root / "assets" / "board.css").read_text() + (
        project_root / "assets" / "forms.css"
    ).read_text()


def rule(css: str, selector: str) -> str:
    """The declarations of every rule with this exact selector, joined."""
    pattern = re.compile(r"(?<![\w-])" + re.escape(selector) + r"\s*\{([^}]*)\}")
    bodies = [match[1] for match in pattern.finditer(css)]

    assert bodies, f"{selector} is not in the stylesheet"

    return "\n".join(bodies)


def test_the_ad_is_laid_out_in_columns(styles: str) -> None:
    """One measure the width of the board is unreadable (§7)."""
    assert "columns: 22rem" in rule(styles, ".description__body")


def test_the_ad_is_a_block_so_the_columns_can_break_it(styles: str) -> None:
    """An inline-block is one box: the columns cannot split it, so they do not."""
    assert "display: block" in rule(styles, ".description__body .editable")


def test_the_ad_does_not_keep_the_empty_value_width(styles: str) -> None:
    """`min-width` gives a blank value something to click; an ad needs no help."""
    assert "min-width: 0" in rule(styles, ".description__body .editable")


def test_every_other_value_is_still_an_inline_block(styles: str) -> None:
    """A value on a line of facts sits in that line, and an empty one keeps a box."""
    declarations = rule(styles, ".editable")

    assert "display: inline-block" in declarations
    assert "min-width: 1.5rem" in declarations


def test_the_ad_is_still_editable(client_ad: Opportunity) -> None:
    """Fixing the layout must not cost the click that opens it."""
    html = Client().get("/").content.decode()
    body = re.search(r'<div class="description__body">(.*?)</div>', html, re.DOTALL)

    assert body is not None
    assert "editable" in body[1]
    assert f"/opportunities/{client_ad.pk}/field/job_description" in body[1]


@pytest.fixture
def client_ad(opportunity: Opportunity) -> Opportunity:
    """An opportunity carrying an ad long enough to need the columns."""
    opportunity.job_description = (
        "We are looking for an experienced engineer to join our platform team. "
    ) * 8
    opportunity.save()
    return opportunity


def test_the_container_does_not_preserve_template_whitespace(styles: str) -> None:
    """`pre-wrap` on the block turns the markup's own newlines into blank lines.

    The ad used to be the container's only text node, so there was no
    whitespace around it to preserve. It is wrapped in a link now, and the
    newlines the template puts either side of that link became leading blank
    lines that pushed the first column's text to the bottom.
    """
    assert "white-space: pre-wrap" not in rule(styles, ".description__body")


def test_the_ad_preserves_its_own_line_breaks(styles: str) -> None:
    """A pasted ad's paragraphs are newlines, and they still have to survive.

    On the element that holds the text rather than the one around it: inside
    the link there is no incidental whitespace to preserve.
    """
    assert "white-space: pre-wrap" in rule(styles, ".description__body .editable")


def test_the_link_holds_its_text_with_no_whitespace_around_it(project_root) -> None:
    """Which is what makes `pre-wrap` safe to put on it."""
    markup = (project_root / "src" / "jobs" / "templates" / "jobs" / "_editable.html").read_text()

    assert re.search(r">\{%\s*if iso", markup), "the link's content must start at its tag"
    assert re.search(r"endif %\}</a>", markup), "and end at it"
