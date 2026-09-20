"""The board's layout contract — plan 001 §7.

A row is a summary block and a steps block. Which element scrolls, and what the
phone does differently, are structural decisions rather than decorative ones —
get the first wrong and the scrollbar runs under the summary card too — so they
are asserted against the stylesheet rather than left to the eye.
"""

import re

_RULE = re.compile(r"(?<![\w-])(?P<selector>\.[a-z_-]+)\s*\{(?P<body>[^}]*)\}")
_TOKEN = re.compile(r"--(?P<name>[a-z-]+):\s*(?P<value>[^;]+);")
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

PHONE = "@media (max-width: 30rem)"

BOARD = ".board"
ROW = ".opportunity"
STEPS = ".opportunity__steps"
TRACK = ".opportunity__track"
SUMMARY = ".card--summary"
STEP = ".card--step"
ARROW = ".steps__arrow"
DESCRIPTION = ".opportunity__description"
DESCRIPTION_BODY = ".description__body"
CLOSED = ".has-js .opportunity__description:not([open])"
BAR = ".has-js .description__summary"
CARD_TOGGLE = ".card__toggle"


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


def declared(css: str, selector: str) -> str:
    """A rule's declarations with its comments removed, for tests that ban a value.

    `rule` keeps the comments, and a comment saying which value is wrong reads
    the same to a substring search as the wrong value itself.
    """
    return _COMMENT.sub("", rule(css, selector))


def rem(value: str) -> float:
    """A length in `rem`, as a number the test can compare."""
    return float(value.strip().removesuffix("rem"))


def token(css: str, name: str) -> str:
    """The value of a custom property, wherever it is declared."""
    for match in _TOKEN.finditer(css):
        if match["name"] == name:
            return match["value"]

    missing = f"--{name} is not in the stylesheet"
    raise AssertionError(missing)


def declarations(css: str, selector: str) -> str:
    """The declarations of the rule with this exact selector text, compound ones included.

    `rule` only knows single class selectors; these are scoped by `.has-js` or
    by state, which is the whole point of them.
    """
    assert selector in css, f"{selector} is not in the stylesheet"

    start = css.index(selector) + len(selector)

    return css[start : css.index("}", start)]


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


def test_the_job_description_takes_a_line_of_its_own(layout_css: str) -> None:
    """A third block on the row, wrapped underneath the other two rather than beside them.

    Making it a sibling that fills the line is what keeps the summary and the
    steps the width they were: a block between them would shrink both.
    """
    assert "flex-wrap: wrap" in rule(wide(layout_css), ROW)
    assert "flex: 0 0 100%" in rule(wide(layout_css), DESCRIPTION)


def test_the_job_description_is_laid_out_in_columns(layout_css: str) -> None:
    """1870 characters across a whole board is one unreadable measure (§4.8)."""
    assert "columns:" in rule(wide(layout_css), DESCRIPTION_BODY)


def test_the_phone_gives_the_job_description_one_column(layout_css: str) -> None:
    """Two columns at 30rem is two columns an inch wide; it is one cell under the steps."""
    assert "columns: 1" in rule(phone(layout_css), DESCRIPTION_BODY)


def test_the_notes_list_is_clamped_to_two_notes_and_four_lines(layout_css: str) -> None:
    """Whichever is shorter wins, so the stylesheet carries both limits (§7)."""
    assert "nth-child(n + 3)" in layout_css
    assert "--notes-lines: 4" in layout_css
    assert "max-height" in layout_css


def test_nothing_hides_a_note_unless_the_script_is_running(layout_css: str) -> None:
    """The toggle that puts the rest back is the script's, so without it every note shows."""
    before = layout_css.split("[data-notes-collapsed]")[:-1]

    assert before, "nothing in the stylesheet clamps the notes"
    for clamp in before:
        assert clamp.rstrip().endswith(".has-js")


def test_the_phone_does_not_wrap_the_row_into_columns(layout_css: str) -> None:
    """`flex: 0 0 100%` is a height once the row is a column, and wrapping goes sideways.

    The wrap is what puts the description on a line of its own on a laptop. On a
    phone the row already stacks, so the only thing left to wrap is the row into
    a second column, which is horizontal scrolling on the one screen that must
    not have any (§7).
    """
    assert "flex-wrap: nowrap" in rule(phone(layout_css), ROW)
    assert "flex: 0 0 auto" in rule(phone(layout_css), DESCRIPTION)


def test_the_laptop_hides_a_closed_description_block(layout_css: str) -> None:
    """The summary card carries the control there, so a closed block is a bar saying nothing."""
    assert "display: none" in declarations(wide(layout_css), CLOSED)
    assert "display: none" in declarations(wide(layout_css), BAR)


def test_the_phone_keeps_the_description_block_its_own_bar(layout_css: str) -> None:
    """The summary collapses to two lines there, so a control inside it is a tap out of reach."""
    assert "display: block" in declarations(phone(layout_css), CLOSED)
    assert "display: list-item" in declarations(phone(layout_css), BAR)
    assert "display: none" in declarations(phone(layout_css), CARD_TOGGLE)


def test_nothing_hides_the_description_unless_the_script_is_running(layout_css: str) -> None:
    """Without it the block's own bar is the only way in, so it has to stay where it is."""
    before = layout_css.split(".opportunity__description:not([open])")[:-1]

    assert before, "nothing in the stylesheet hides a closed description"
    for scope in before:
        assert scope.rstrip().endswith(".has-js")


def test_a_row_sits_on_a_tray_of_its_own(layout_css: str) -> None:
    """One background under both lines is what says the ad belongs to the row above it.

    Without it an opened description is a bar floating between two rows, and
    which of them it belongs to is a guess.
    """
    row = rule(wide(layout_css), ROW)

    assert "background: var(--row-bg)" in row
    assert "padding: var(--board-gap)" in row


def test_rows_sit_further_apart_than_the_blocks_inside_one(layout_css: str) -> None:
    """A tray groups nothing if what is outside it is no further away than what is inside."""
    assert "gap: var(--row-spacing)" in rule(wide(layout_css), BOARD)
    assert rem(token(layout_css, "row-spacing")) > rem(token(layout_css, "board-gap"))


def test_the_tray_is_not_the_colour_of_the_page(layout_css: str) -> None:
    """Two names for one colour would be a tray nobody can see."""
    assert token(layout_css, "row-bg") != token(layout_css, "page-bg")


def test_a_tray_is_outlined_as_well_as_filled(layout_css: str) -> None:
    """The fill is faint on purpose, so the edge is what has to carry the grouping.

    Solid, and its own colour: a 1px dotted line is not read as dots at all, only
    as a fainter version of the same line, which is the opposite of the job.
    """
    assert "border: 1px solid var(--tray-rule)" in rule(wide(layout_css), ROW)


def test_the_tray_edge_is_darker_than_a_cards(layout_css: str) -> None:
    """A card's edge separates two things on the tray; the tray's separates the rows."""
    assert token(layout_css, "tray-rule") != token(layout_css, "rule")


def test_the_tray_edge_does_not_borrow_ghosteds_dashes(layout_css: str, palette_css: str) -> None:
    """GHOSTED is dashed as its second channel (§6.4). Two dashed edges is one signal, twice."""
    assert "border-style: dashed" in palette_css
    assert "dashed" not in declared(wide(layout_css), ROW)
