"""Bullet lists in free text — the one piece of markdown the board reads.

Step comments and notes are often written as `- ` lists. This turns runs of
such lines into a `<ul>` and every other line break into a `<br>`, and nothing
else: it is not a markdown renderer, and does not want to become one.

Everything is escaped first and tags are only ever added around escaped text,
so nothing typed can become markup of its own. Pure, so it is tested without
a database or a template.
"""

import re

from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

# A marker, at least one space, then something to list. `*important*` has no
# space after its star and a lone `-` has nothing after it, so neither is one.
BULLET = re.compile(r"^\s*[-*•]\s+(?P<item>\S.*)$")


def bullets(text: str) -> SafeString:
    """Escape `text`, listing its bullet lines and breaking its other lines.

    No `<br>` is put beside a list: a block already starts on a line of its
    own, and a break there would read as a blank line.
    """
    parts: list[str] = []
    items: list[str] = []
    lines: list[str] = []

    def close_items() -> None:
        if items:
            parts.append(
                '<ul class="bullets">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
            )
            items.clear()

    def close_lines() -> None:
        if lines:
            parts.append("<br>".join(lines))
            lines.clear()

    for line in text.splitlines():
        found = BULLET.match(line)
        if found:
            close_lines()
            items.append(escape(found["item"].rstrip()))
        elif items and not line.strip():
            # A blank line straight after a list ends it and stands between
            # it and whatever follows.
            close_items()
            parts.append("<br>")
        else:
            close_items()
            lines.append(escape(line))
    close_items()
    close_lines()
    # Safe because every piece above was escaped before a tag went round it.
    return mark_safe("".join(parts))
