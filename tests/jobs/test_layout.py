"""The board's layout contract — plan 001 §7.

A row is a summary block and a steps block. Which element scrolls, and what the
phone does differently, are structural decisions rather than decorative ones —
get the first wrong and the scrollbar runs under the summary card too — so they
are asserted against the stylesheet rather than left to the eye.
"""

import re

_RULE = re.compile(r"(?<![\w-])(?P<selector>\.[a-z_-]+)\s*\{(?P<body>[^}]*)\}")

PHONE = "@media (max-width: 30rem)"

ROW = ".opportunity"
STEPS = ".opportunity__steps"
TRACK = ".opportunity__track"
SUMMARY = ".card--summary"
STEP = ".card--step"
ARROW = ".steps__arrow"


def block(css: str, header: str) -> str:
    """The body of an at-rule, found by matching its braces rather than by regex."""
    start = css.index(header) + len(header)
    depth = 0
    for offset, character in enumerate(css[start:], start=start):
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return css[start : offset + 1]

    unclosed = f"{header} is never closed"
    raise AssertionError(unclosed)


def rule(css: str, selector: str) -> str:
    """The declarations of every rule with this exact selector, joined."""
    bodies = [match["body"] for match in _RULE.finditer(css) if match["selector"] == selector]

    assert bodies, f"{selector} is not in the stylesheet"

    return "\n".join(bodies)


def wide(css: str) -> str:
    """The stylesheet with the phone's overrides removed: what a laptop sees."""
    return css.replace(block(css, PHONE), "")


def phone(css: str) -> str:
    """Only the phone's overrides."""
    return block(css, PHONE)


def test_the_track_is_what_scrolls(layout_css: str) -> None:
    """The scroller is the track holding the cards, so a scrollbar spans only them (§7)."""
    assert "overflow-x: auto" in rule(wide(layout_css), TRACK)
    assert "overflow-x" not in rule(wide(layout_css), STEPS)
    assert "overflow-x" not in rule(wide(layout_css), ROW)


def test_the_track_is_allowed_to_be_narrower_than_its_steps(layout_css: str) -> None:
    """A flex item defaults to `min-width: auto`, which would push the row wide instead."""
    assert "min-width: 0" in rule(wide(layout_css), TRACK)


def test_the_summary_card_holds_its_place_by_layout_not_by_sticky(layout_css: str) -> None:
    """The scroller is the summary's sibling now, so nothing moves under it to pin against."""
    assert "position: sticky" not in rule(wide(layout_css), SUMMARY)


def test_the_phone_stacks_the_row(layout_css: str) -> None:
    """Summary across the viewport, steps in a row underneath it."""
    assert "flex-direction: column" in rule(phone(layout_css), ROW)
    assert "width: 100%" in rule(phone(layout_css), SUMMARY)


def test_the_phone_shows_one_step_at_a_time(layout_css: str) -> None:
    """A step card fills the track, so the next one is a tap away rather than a peek."""
    assert "flex: 0 0 100%" in rule(phone(layout_css), STEP)


def test_the_phone_does_not_scroll_the_steps_sideways(layout_css: str) -> None:
    """The arrows move the track; nothing swipes or scrolls it (§7).

    Scoped to `.has-js`, so a browser that never ran the script keeps the
    scrolling it would otherwise have no way to replace.
    """
    assert f".has-js {TRACK}" in phone(layout_css)
    assert "overflow-x: hidden" in rule(phone(layout_css), TRACK)


def test_a_row_is_one_height_all_the_way_across(layout_css: str) -> None:
    """Summary and steps end level, however much taller one of them would be alone.

    The row stretches its two blocks, the steps block stretches the track, and
    the track stretches the cards. Centring anywhere in that chain leaves the
    steps shrinkwrapped to their own content and short of the summary.
    """
    assert "align-items: stretch" in rule(wide(layout_css), ROW)
    assert "align-items: stretch" in rule(wide(layout_css), STEPS)
    assert "align-items: center" not in rule(wide(layout_css), STEPS)


def test_the_laptop_scrolls_the_track_without_a_scrollbar(layout_css: str) -> None:
    """The arrows replace the scrollbar, but not the wheel or the trackpad (§7)."""
    track = rule(wide(layout_css), TRACK)

    assert "overflow-x: auto" in track
    assert "scrollbar-width: none" in track


def test_the_arrows_are_useless_without_the_script(layout_css: str) -> None:
    """They move a track the script moves, so nothing shows them until it has run."""
    assert "display: none" in rule(wide(layout_css), ARROW)
    assert f".has-js {ARROW}" in layout_css
    assert "display: flex" in rule(wide(layout_css), ARROW)


def test_the_compiled_stylesheet_is_minified(compiled_css: str) -> None:
    """`poe css` and the watch in `poe serve` have to agree, or every dev run rewrites it.

    The file is committed. A watch built without `--minify` produces the same
    CSS spread over four hundred lines, so the artifact flips back and forth
    depending on which task ran last and every diff carries it.
    """
    assert compiled_css.count("\n") <= 1


def test_the_tailwind_input_finds_the_templates_from_its_own_directory(
    tailwind_input: str,
) -> None:
    """`@source` resolves against the stylesheet, and gets it wrong in silence.

    `@source "src/jobs/templates"` and `@source "/src/jobs/templates"` both
    build without complaint and scan nothing, so a utility used in a template
    would quietly never reach the stylesheet. Only the file-relative form works.
    `@import` is stricter — a root-relative path fails the build outright.
    """
    assert '@source "../src/jobs/templates"' in tailwind_input
    assert '@import "./board.css"' in tailwind_input
    assert '@import "./states.css"' in tailwind_input


def test_the_compiled_stylesheet_carries_the_layout(layout_css: str, compiled_css: str) -> None:
    """`static/css/app.css` is committed, so it can go stale — and nothing else would notice."""
    selectors = {match["selector"] for match in _RULE.finditer(layout_css)}
    built = {match["selector"] for match in _RULE.finditer(compiled_css)}

    assert selectors <= built
