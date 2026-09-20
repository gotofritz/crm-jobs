"""A board worth looking at, for development and for tests that want a full one.

Not a migration and not a fixture. Nothing here runs on `migrate`; the picklists
a fresh database does ship with are in `0002_seed_picklists`. These are
opportunities, which are the user's data, so they never go near the database you
work in: `poe demo` deletes `demo.sqlite3`, rebuilds it and serves that, while
`poe dev` keeps `db.sqlite3` to itself.
"""

import datetime as dt
from typing import NamedTuple

from jobs.models import Company, Contact, Note, Opportunity, Source, State, Step


class DemoStep(NamedTuple):
    """One step to build, named by the seeded state it lands in (§6.1)."""

    state: str
    date: dt.date
    title: str
    contacts: tuple[str, ...] = ()


class DemoNote(NamedTuple):
    """One note to build, dated by hand so the seed cannot reorder itself."""

    written: dt.datetime
    body: str


class DemoRow(NamedTuple):
    """One opportunity to build, with its steps and its notes."""

    company: str
    title: str
    source: str
    applied: dt.date
    steps: tuple[DemoStep, ...] = ()
    notes: tuple[DemoNote, ...] = ()
    job_description: str = ""
    archived: bool = False


DEMO_CONTACT = "Ada Lovelace"

# A step keeps several people, and the card prints them, so the demo board has
# to show one step with two and one with none.
DEMO_PANEL = ("Ada Lovelace", "Grace Hopper")

# A pasted job ad — 1870 characters in the sample export, which is what the
# description row has to lay out in columns without swallowing the page (§4.8).
DEMO_AD = (
    "We are looking for an experienced engineer to join our platform team. "
    "You will own services end to end, from design through to production, and "
    "work closely with product. Stack: Python, Django, Postgres, a little Go. "
) * 8

# The other shape an ad comes in: a few lines, not a wall. A row has to read
# right at both lengths.
DEMO_AD_SHORT = (
    "Backend engineer, mostly Python. Small team, four engineers, no on-call. "
    "Hybrid, two days a week in the office. Salary band published up front."
)

# One note long enough on its own to hit the four-line clamp before the
# two-note one (§7).
DEMO_LONG_NOTE = (
    "Spoke to someone who worked there until last spring. Two reorgs in "
    "eighteen months, the platform team was rebuilt around a new director, "
    "and the people who stayed did not sound happy about it. Worth asking "
    "who I would report to and how long they have been in the role."
)

# Chosen to exercise the board rather than to be realistic: every group is
# represented, two steps name the people who were there and the rest name none,
# one row has no steps at all, one is archived, five carry an ad
# long enough to need a description row, and the notes between them cover all
# four cases the summary card has to render — none, two, more than two, and one
# long enough to be clamped on its own.
DEMO_ROWS: tuple[DemoRow, ...] = (
    DemoRow(
        company="Northwind Analytics",
        title="Staff Backend Engineer",
        source="LinkedIn",
        applied=dt.date(2026, 1, 2),
        job_description=DEMO_AD,
        steps=(
            DemoStep("unremarkable", dt.date(2026, 1, 20), "Applied via site"),
            DemoStep("due", dt.date(2026, 3, 2), "Second interview booked", DEMO_PANEL),
            DemoStep("overdue", dt.date(2026, 2, 10), "Chased recruiter, no reply"),
        ),
        notes=(
            DemoNote(dt.datetime(2026, 1, 2, 9, 5, tzinfo=dt.UTC), "Found it on the LinkedIn feed"),
            DemoNote(
                dt.datetime(2026, 1, 21, 18, 40, tzinfo=dt.UTC),
                "Recruiter answered within a day, which is a good sign",
            ),
            DemoNote(
                dt.datetime(2026, 2, 11, 8, 15, tzinfo=dt.UTC),
                "Not sure about this one — the band they quoted is below the ad",
            ),
            DemoNote(
                dt.datetime(2026, 3, 3, 12, 0, tzinfo=dt.UTC),
                "Second interview is with the CTO, prepare the scaling story",
            ),
        ),
    ),
    DemoRow(
        company="Belmont Robotics",
        title="Senior Platform Engineer",
        source="Referral",
        applied=dt.date(2026, 1, 11),
        job_description=DEMO_AD,
        steps=(
            DemoStep("unremarkable", dt.date(2026, 2, 1), "Applied via site"),
            DemoStep("success", dt.date(2026, 2, 25), "Passed tech screen"),
            DemoStep("going-well", dt.date(2026, 3, 11), "Panel went well", DEMO_PANEL),
        ),
        notes=(
            DemoNote(dt.datetime(2026, 1, 12, 7, 45, tzinfo=dt.UTC), "Referral came from Ada"),
            DemoNote(
                dt.datetime(2026, 2, 26, 16, 20, tzinfo=dt.UTC),
                "Best conversation so far. Would take this one.",
            ),
        ),
    ),
    DemoRow(
        company="Kestrel Data",
        title="Principal Engineer",
        source="Wellfound",
        applied=dt.date(2026, 1, 20),
        job_description=DEMO_AD,
        steps=(
            DemoStep("unremarkable", dt.date(2026, 1, 2), "Applied via site"),
            DemoStep("ghosted", dt.date(2026, 1, 30), "No reply in six weeks"),
        ),
        notes=(DemoNote(dt.datetime(2026, 1, 25, 21, 30, tzinfo=dt.UTC), DEMO_LONG_NOTE),),
    ),
    # Six steps, so the row has to scroll: the layout contract in §7 is only
    # visible on an opportunity that has run long enough to need it.
    DemoRow(
        company="Ardent Bioscience",
        title="Senior Backend Engineer",
        source="Wellfound",
        applied=dt.date(2026, 1, 8),
        job_description=DEMO_AD_SHORT,
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
        notes=(
            DemoNote(dt.datetime(2026, 2, 19, 10, 0, tzinfo=dt.UTC), "Applied on the off chance"),
            DemoNote(
                dt.datetime(2026, 3, 5, 9, 30, tzinfo=dt.UTC),
                "Would not put a number on the band. Twice.",
            ),
            DemoNote(dt.datetime(2026, 3, 12, 19, 0, tzinfo=dt.UTC), "Leaving this one to go cold"),
        ),
    ),
    DemoRow(
        company="Pelham Health",
        title="Backend Engineer",
        source="Direct",
        applied=dt.date(2026, 2, 7),
        job_description=DEMO_AD,
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
                "job_description": row.job_description,
                "archived_at": ARCHIVED_AT if row.archived else None,
            },
        )[0]
        for step in row.steps:
            built_step = Step.objects.get_or_create(
                opportunity=opportunity,
                state=State.objects.get(slug=step.state),
                date=step.date,
                defaults={"title": step.title},
            )[0]
            if step.contacts:
                built_step.contacts.set(
                    Contact.objects.get_or_create(name=name)[0] for name in step.contacts
                )
        for note in row.notes:
            Note.objects.get_or_create(
                opportunity=opportunity,
                body=note.body,
                defaults={"created_at": note.written},
            )
        built.append(opportunity)

    return built
