"""The board's ordering rules — plan 001 §4.5, and the notes order beside them.

The one piece of real domain logic in the port. It lives here, as pure
functions over steps, so it can be tested without a database and cannot drift
into a view or a template (§6.3). Nothing in this module imports the models at
runtime; the models import it.

Three orders are defined, and no two of them are the same order:

* steps inside an opportunity, `sort_steps`;
* opportunities inside the board, `sort_opportunities`, keyed on the step
  `sort_steps` leaves at the front;
* notes inside an opportunity, `sort_notes`, which is the simple one — the
  GAS app had no notes, so nothing about it is ported.
"""

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from jobs.models import Note, Opportunity, Step

# §4.5. A business rule, not data: adding a group means deciding where it
# ranks, which is a code change either way (§6.1).
GROUP_RANK: dict[str, int] = {"ATTENTION": 3, "DUE": 2, "COMPLETE": 1}

# §4.5: "anything else -1", so an unknown group sorts below every known one.
UNRANKED = -1

# The group whose date order is inverted. Nothing is pending in it, so the only
# useful order is most-recently-touched (§6.2).
INVERTED_GROUP = "COMPLETE"

_SECONDS_PER_DAY = 86_400
_MICROSECONDS_PER_SECOND = 1_000_000


def group_rank(group: str) -> int:
    """Rank a group, with anything unrecognised below all of them (§4.5)."""
    return GROUP_RANK.get(group, UNRANKED)


def _seconds_into_the_day(time: dt.time | None) -> float:
    """Read a missing time as midnight: the sheet stored ':' for empty (§4.5)."""
    if time is None:
        return 0.0
    return (
        time.hour * 3600
        + time.minute * 60
        + time.second
        + time.microsecond / _MICROSECONDS_PER_SECOND
    )


def _moment(step: "Step") -> float:
    """Where a step sits on the timeline, as one comparable number (§4.5)."""
    return step.date.toordinal() * _SECONDS_PER_DAY + _seconds_into_the_day(step.time)


def _timeline_key(step: "Step") -> float:
    """The date tie-break: ascending, except inside `INVERTED_GROUP` (§4.5)."""
    moment = _moment(step)
    return -moment if step.state.group == INVERTED_GROUP else moment


def step_sort_key(step: "Step") -> tuple[int, float]:
    """Sort key for a step within its opportunity (§4.5, `Opportunity.sortSteps`)."""
    return (-group_rank(step.state.group), _timeline_key(step))


def sort_steps(steps: "Iterable[Step]") -> "list[Step]":
    """Steps in §4.5 order. Stable, so equal timestamps keep the order they arrived in."""
    return sorted(steps, key=step_sort_key)


def top_step(steps: "Iterable[Step]") -> "Step | None":
    """The step an opportunity is judged by: the first one `sort_steps` leaves (§4.5)."""
    return next(iter(sort_steps(steps)), None)


def opportunity_sort_key(step: "Step | None") -> tuple[int, int, int, float]:
    """Sort key for an opportunity, keyed on its top step (§4.5, `Pool.sortOpportunities`).

    An opportunity with no steps sorts before every other one, so the leading
    element is 0 for it and 1 for everything else.
    """
    if step is None:
        return (0, 0, 0, 0.0)
    return (1, -group_rank(step.state.group), step.state.sort_order, _timeline_key(step))


def sort_opportunities(opportunities: "Iterable[Opportunity]") -> "list[Opportunity]":
    """Opportunities in board order (§4.5).

    Prefetch `steps__state` first, or this reaches back into the database once
    per row — `OpportunityQuerySet.in_board_order` does that.
    """
    return sorted(
        opportunities,
        key=lambda opportunity: opportunity_sort_key(top_step(opportunity.steps.all())),
    )


def note_sort_key(note: "Note") -> tuple[dt.datetime, int]:
    """Sort key for a note within its opportunity, read with `reverse=True`.

    The row's own id is the tie-break: a batch written in one go can share a
    timestamp to the microsecond, and an unsaved note has no id at all.
    """
    return (note.created_at, note.pk or 0)


def sort_notes(notes: "Iterable[Note]") -> "list[Note]":
    """Notes newest first — the last thing written about an opportunity is read first."""
    return sorted(notes, key=note_sort_key, reverse=True)
