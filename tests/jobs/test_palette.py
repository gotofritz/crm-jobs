"""The state palette — plan 001 §6.3 and §6.4.

The ratios printed in §6.4 are a claim about a file. These tests read the
file and check the claim, so a later tweak that breaks legibility fails here
rather than in somebody's eyes. Nothing here touches the database: the palette
is CSS, and the model is not allowed to know it exists.
"""

import re
from pathlib import Path

import pytest

from jobs.models import Group

# §6.4, verbatim: slug, background, foreground, and the ratio the plan claims.
PALETTE = [
    ("error", "#b3261e", "#ffffff", 6.54),
    ("overdue", "#e8710a", "#1a1a1a", 5.63),
    ("due", "#ffd54f", "#1a1a1a", 12.33),
    ("tentative", "#fff3cd", "#1a1a1a", 15.71),
    ("accepted", "#1b5e20", "#ffffff", 7.87),
    ("success", "#a5d6a7", "#1a1a1a", 10.59),
    ("going-well", "#c8e6c9", "#1a1a1a", 12.94),
    ("unremarkable", "#f5f5f5", "#1a1a1a", 15.96),
    ("bad-feeling", "#e28fae", "#1a1a1a", 7.27),
    ("ghosted", "#e0e0e0", "#424242", 7.61),
    ("fail", "#d7ccc8", "#4e342e", 7.20),
    ("blacklist", "#37474f", "#ffffff", 9.65),
]

# WCAG 2.1 AA for body text. §6.4's worst pair is 5.63.
WCAG_AA_BODY_TEXT = 4.5

# Quotes are optional so that the same parser reads the source stylesheet and
# the minified build, which drops them.
_RULE = re.compile(r"\[data-(?P<kind>state|group)=\"?(?P<key>[a-z-]+)\"?\][^{]*\{(?P<body>[^}]*)\}")
_DECLARATION = re.compile(r"--state-(?P<side>bg|fg):\s*(?P<value>#[0-9a-f]{3,6})")
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")


def rules(css: str) -> dict[tuple[str, str], str]:
    """Every `[data-state]` and `[data-group]` rule in the stylesheet, by selector."""
    return {(match["kind"], match["key"]): match["body"] for match in _RULE.finditer(css)}


def _expand(colour: str) -> str:
    """`#fff` and `#ffffff` are the same colour; minifying writes the short one."""
    if len(colour) == 4:
        return "#" + "".join(channel * 2 for channel in colour[1:])
    return colour


def declared_pair(css: str, *, kind: str, key: str) -> tuple[str, str]:
    """The background and foreground one selector sets."""
    sides = {
        match["side"]: _expand(match["value"])
        for match in _DECLARATION.finditer(rules(css)[kind, key])
    }
    return sides["bg"], sides["fg"]


def _linear(channel: int) -> float:
    """One sRGB channel, gamma-expanded (WCAG 2.1, relative luminance)."""
    proportion = channel / 255
    if proportion <= 0.03928:
        return proportion / 12.92
    return ((proportion + 0.055) / 1.055) ** 2.4


def relative_luminance(colour: str) -> float:
    """The luminance of a `#rrggbb` colour."""
    red, green, blue = (_linear(int(colour[start : start + 2], 16)) for start in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """The WCAG contrast ratio between two `#rrggbb` colours, 1 to 21."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_the_contrast_helper_matches_the_known_extremes() -> None:
    """Black on white is 21:1 and anything on itself is 1:1 — the helper's calibration."""
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)
    assert contrast_ratio("#b3261e", "#b3261e") == pytest.approx(1.0)


@pytest.mark.parametrize(("slug", "background", "foreground", "ratio"), PALETTE)
def test_every_state_is_painted_as_the_plan_says_and_stays_legible(
    palette_css: str, slug: str, background: str, foreground: str, ratio: float
) -> None:
    """The stylesheet is the palette; §6.4 only documents it, down to the ratio.

    Checking the pair and its contrast together is what stops a later tweak
    passing: changing a hex value here fails unless the new pair still clears
    4.5:1 and §6.4 is updated to match.
    """
    assert declared_pair(palette_css, kind="state", key=slug) == (background, foreground)

    measured = contrast_ratio(background, foreground)

    assert measured >= WCAG_AA_BODY_TEXT
    assert measured == pytest.approx(ratio, abs=0.01)


@pytest.mark.parametrize("group", [group.lower() for group in Group.values])
def test_every_group_has_a_legible_fallback(palette_css: str, group: str) -> None:
    """A state with no rule of its own still renders, in its group's colours (§6.3)."""
    background, foreground = declared_pair(palette_css, kind="group", key=group)

    assert contrast_ratio(background, foreground) >= WCAG_AA_BODY_TEXT


def test_the_group_fallbacks_cover_every_group_the_model_knows(palette_css: str) -> None:
    """Adding a `Group` without deciding what it looks like fails here (§6.3)."""
    declared = {key for kind, key in rules(palette_css) if kind == "group"}

    assert {group.lower() for group in Group.values} <= declared


def test_ghosted_carries_a_second_visual_channel(palette_css: str) -> None:
    """The pale end of COMPLETE is close in lightness, and GHOSTED is what you scan for (§6.4)."""
    assert "dashed" in rules(palette_css)["state", "ghosted"]


def test_the_group_fallbacks_come_before_the_per_state_rules(palette_css: str) -> None:
    """Same specificity, so the cascade decides: per-state has to be later to win (§6.3)."""
    last_group = max(
        palette_css.index(f'[data-group="{key}"]')
        for kind, key in rules(palette_css)
        if kind == "group"
    )
    first_state = min(
        palette_css.index(f'[data-state="{key}"]')
        for kind, key in rules(palette_css)
        if kind == "state"
    )

    assert last_group < first_state


def test_no_colour_reaches_python_or_the_templates(project_root: Path) -> None:
    """If a hex value reaches a model, a view or a template, the design is wrong (§6.3)."""
    sources = [
        path
        for path in (project_root / "src").rglob("*")
        if path.suffix in {".py", ".html"} and "migrations" not in path.parts
    ]

    offenders = sorted(
        str(path.relative_to(project_root)) for path in sources if _HEX.search(path.read_text())
    )

    assert offenders == []


def test_the_compiled_stylesheet_carries_the_palette(palette_css: str, compiled_css: str) -> None:
    """`static/css/app.css` is committed, so it can go stale — and nothing else would notice.

    The tests above read `assets/`, which is the source. This one reads what is
    actually served, so editing a colour without running `uv run poe css` fails
    here rather than on the board.
    """
    source = {
        selector: declared_pair(palette_css, kind=selector[0], key=selector[1])
        for selector in rules(palette_css)
    }
    built = {
        selector: declared_pair(compiled_css, kind=selector[0], key=selector[1])
        for selector in rules(compiled_css)
    }

    assert built == source
