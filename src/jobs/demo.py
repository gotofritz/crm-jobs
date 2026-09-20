"""A board worth looking at, for development and for tests that want a full one.

Not a migration and not a fixture. Nothing here runs on `migrate`; the picklists
a fresh database does ship with are in `0002_seed_picklists`. These are
opportunities, which are the user's data, so they never go near the database you
work in: `poe demo` deletes `demo.sqlite3`, rebuilds it and serves that, while
`poe dev` keeps `db.sqlite3` to itself.
"""

import datetime as dt
from typing import NamedTuple

from jobs.models import Company, Contact, Opportunity, Source, State, Step


class DemoStep(NamedTuple):
    """One step to build, named by the seeded state it lands in (§6.1)."""

    state: str
    date: dt.date
    title: str


class DemoRow(NamedTuple):
    """One opportunity to build, with its steps."""

    company: str
    title: str
    source: str
    applied: dt.date
    steps: tuple[DemoStep, ...] = ()
    comments: str = ""
    archived: bool = False


DEMO_CONTACT = "Ada Lovelace"

# A pasted job ad, the thing the summary card has to survive (§4.8).
DEMO_AD = (
    "We are looking for an experienced engineer to join our platform team. "
    "You will own services end to end, from design through to production, and "
    "work closely with product. Stack: Python, Django, Postgres, a little Go. "
) * 8

# Chosen to exercise the board rather than to be realistic: every group is
# represented, one row has no steps at all, one is archived, and three carry a
# comment long enough to need collapsing.
DEMO_ROWS: tuple[DemoRow, ...] = (
    DemoRow(
        company="Northwind Analytics",
        title="Staff Backend Engineer",
        source="LinkedIn",
        applied=dt.date(2026, 1, 2),
        comments=DEMO_AD,
        steps=(
            DemoStep("unremarkable", dt.date(2026, 1, 20), "Applied via site"),
            DemoStep("due", dt.date(2026, 3, 2), "Second interview booked"),
            DemoStep("overdue", dt.date(2026, 2, 10), "Chased recruiter, no reply"),
        ),
    ),
    DemoRow(
        company="Belmont Robotics",
        title="Senior Platform Engineer",
        source="Referral",
        applied=dt.date(2026, 1, 11),
        comments=DEMO_AD,
        steps=(
            DemoStep("unremarkable", dt.date(2026, 2, 1), "Applied via site"),
            DemoStep("success", dt.date(2026, 2, 25), "Passed tech screen"),
            DemoStep("going-well", dt.date(2026, 3, 11), "Panel went well"),
        ),
    ),
    DemoRow(
        company="Kestrel Data",
        title="Principal Engineer",
        source="Wellfound",
        applied=dt.date(2026, 1, 20),
        comments=DEMO_AD,
        steps=(
            DemoStep("unremarkable", dt.date(2026, 1, 2), "Applied via site"),
            DemoStep("ghosted", dt.date(2026, 1, 30), "No reply in six weeks"),
        ),
    ),
    # Six steps, so the row has to scroll: the layout contract in §7 is only
    # visible on an opportunity that has run long enough to need it.
    DemoRow(
        company="Ardent Bioscience",
        title="Senior Backend Engineer",
        source="Wellfound",
        applied=dt.date(2026, 1, 8),
        steps=(
            DemoStep("unremarkable", dt.date(2026, 1, 8), "Applied via site"),
            DemoStep("going-well", dt.date(2026, 1, 19), "Recruiter call, sounded keen"),
            DemoStep("success", dt.date(2026, 2, 3), "Passed tech screen"),
            DemoStep("going-well", dt.date(2026, 2, 17), "System design went well"),
            DemoStep("tentative", dt.date(2026, 3, 9), "Final panel pencilled in"),
            DemoStep("due", dt.date(2026, 3, 16), "References requested"),
        ),
    ),
    DemoRow(
        company="Harbour Media",
        title="Engineering Lead",
        source="Recruiter",
        applied=dt.date(2026, 1, 29),
        steps=(
            DemoStep("unremarkable", dt.date(2026, 2, 18), "Applied via site"),
            DemoStep("bad-feeling", dt.date(2026, 3, 4), "Vague about the salary band"),
        ),
    ),
    DemoRow(
        company="Pelham Health",
        title="Backend Engineer",
        source="Direct",
        applied=dt.date(2026, 2, 7),
        steps=(DemoStep("blacklist", dt.date(2026, 2, 2), "Unpaid take-home, four days"),),
    ),
    DemoRow(
        company="Vale Logistics",
        title="Python Engineer",
        source="LinkedIn",
        applied=dt.date(2026, 2, 16),
    ),
    DemoRow(
        company="Old Job Co",
        title="Archived example",
        source="Direct",
        applied=dt.date(2025, 11, 1),
        archived=True,
    ),
)

DEMO_COMPANIES: tuple[str, ...] = tuple(row.company for row in DEMO_ROWS)

# Fixed rather than `now()`, so re-running the seed cannot move a row.
ARCHIVED_AT = dt.datetime(2025, 12, 1, tzinfo=dt.UTC)


def seed_demo() -> list[Opportunity]:
    """Build the demo board, or leave it as it is if it is already there.

    Every write is a `get_or_create` keyed on what identifies the row, so
    running this twice is the same as running it once.
    """
    contact = Contact.objects.get_or_create(name=DEMO_CONTACT)[0]
    built = []

    for index, row in enumerate(DEMO_ROWS):
        company = Company.objects.get_or_create(name=row.company)[0]
        opportunity = Opportunity.objects.get_or_create(
            company=company,
            title=row.title,
            defaults={
                "date": row.applied,
                "source": Source.objects.get(name=row.source),
                # Some rows have a contact and some do not; both render.
                "contact": contact if index % 2 == 0 else None,
                "comments": row.comments,
                "archived_at": ARCHIVED_AT if row.archived else None,
            },
        )[0]
        for step in row.steps:
            Step.objects.get_or_create(
                opportunity=opportunity,
                state=State.objects.get(slug=step.state),
                date=step.date,
                defaults={"title": step.title},
            )
        built.append(opportunity)

    return built
