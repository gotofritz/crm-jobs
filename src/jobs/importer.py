"""Writing parsed imports into the database — plan 003 §5 and plan 004 §6.

The half of each import that touches the ORM. `jobs.sheet` and
`jobs.opportunity_csv` turn a file's text into dataclasses and know nothing
about models; this turns those dataclasses into rows and knows nothing about
the file they came from. The management commands are the thin things joining
them.

Everything here is keyed on what identifies a row. A second run of the old
sheet updates rather than duplicates (plan 003 I6); a second run of a CSV of
opportunities skips what is already there (plan 004 I5).
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from django.db import transaction

from jobs.forms import OpportunityForm, by_name
from jobs.models import Company, Contact, Employment, Opportunity, Source, State, Step
from jobs.opportunity_csv import Problem, Row
from jobs.sheet import DEFAULT_STATE, ParsedRow, ParsedStep, split_names, state_for

# The alias `manage.py import_sheet --demo` writes to, and the one it writes to
# otherwise. Both are configured in `config.settings` (plan 003 I4).
DEMO_DATABASE = "demo"
LIVE_DATABASE = "default"


class BlankCompanyError(ValueError):
    """A row that reached the writer without a company.

    The parser refuses one (§4.2), so this is a bug rather than bad data, and it
    stops the transaction instead of writing an opportunity nobody can find.
    """

    def __init__(self) -> None:
        """Say what happened, since the import is about to stop over it."""
        super().__init__("a parsed row had no company, which the parser should have refused")


def database_for(*, demo: bool) -> str:
    """Which database alias a run writes to.

    One line, and a function rather than an expression inside the command,
    because "did `--demo` keep this off the real database" is the question worth
    being able to ask in a test without opening a second database to ask it.
    """
    return DEMO_DATABASE if demo else LIVE_DATABASE


@dataclass(frozen=True)
class Inference:
    """One step's title, and the state it was guessed into (§6).

    Reported for every step, not only the ones that matched something: a step
    that fell through to `unremarkable` is as much a decision as one that did
    not, and the reader is checking both.
    """

    company: str
    title: str
    state: str

    def __str__(self) -> str:
        """Company, title and state, which is what a reader checks."""
        return f"{self.company}: {self.title!r} -> {self.state}"


@dataclass(frozen=True)
class Collision:
    """A contact name at more than one company, for a human to look at (§5.1)."""

    name: str
    companies: tuple[str, ...]

    def __str__(self) -> str:
        """Name the person and everywhere that name turns up."""
        return f"{self.name}, at {', '.join(self.companies)}"


@dataclass(frozen=True)
class Written:
    """What a run came to, and what it wants a human to check afterwards."""

    opportunities: int
    steps: int
    inferences: tuple[Inference, ...]
    collisions: tuple[Collision, ...]


def named_states(*, using: str) -> dict[str, str]:
    """Each seeded state's printed name, lowercased, against its slug.

    What `state_for` matches a title against. Built here rather than there, so
    the inference itself stays pure and needs no database to test (§6).
    """
    return {
        state.name.lower(): state.slug for state in State.objects.using(using).all() if state.name
    }


def company_named(raw: str, *, using: str) -> Company:
    """Resolve a company by name, creating it when the sheet brought a new one."""
    company = by_name(Company, raw, using=using)
    if company is None:
        raise BlankCompanyError
    return company


def contact_at(company: Company, name: str, *, using: str) -> Contact:
    """The person of that name at that company, created with a stint if new (§5.1).

    Identity is per company, not global: `Contact.name` is deliberately not
    unique, and the sheet cannot say whether one name under two companies is one
    person who moved or two strangers. `Employment` is where the per-company
    answer lives, which is why one is opened here with both bounds unknown.
    """
    existing = (
        Contact.objects.using(using).filter(employments__company=company, name__iexact=name).first()
    )
    if existing is not None:
        return existing

    person = Contact.objects.using(using).create(name=name)
    Employment.objects.using(using).create(contact=person, company=company)
    return person


def collisions_among(names: set[str], *, using: str) -> tuple[Collision, ...]:
    """Names that turn up at more than one company, for review rather than merging.

    Asked of the database rather than of this run alone, so a name colliding with
    somebody already in the tables is reported too.
    """
    found = []
    for name in sorted(names):
        companies = sorted(
            Company.objects.using(using)
            .filter(employments__contact__name__iexact=name)
            .values_list("name", flat=True)
            .distinct()
        )
        if len(companies) > 1:
            found.append(Collision(name=name, companies=tuple(companies)))
    return tuple(found)


def write_step(parsed: ParsedStep, *, opportunity: Opportunity, state: State, using: str) -> None:
    """Write one step, keyed on what makes it that step rather than another."""
    step, _ = Step.objects.using(using).update_or_create(
        opportunity=opportunity,
        date=parsed.date,
        time=parsed.time,
        title=parsed.title,
        defaults={"state": state, "comments": parsed.comments},
    )
    step.contacts.set(
        contact_at(opportunity.company, name, using=using) for name in parsed.contacts
    )


def write_row(row: ParsedRow, *, using: str) -> tuple[Opportunity, set[str]]:
    """Write one opportunity and its steps, and say which names it mentioned.

    Column 2 can name more than one person (§4.1) while `Opportunity.contact` is
    a single foreign key. The first name takes the key and the rest still become
    people at the company, so nothing is dropped — they are reachable from the
    steps, from the collision report and from the contact autosuggest (#10).
    """
    company = company_named(row.company, using=using)
    names = set(split_names(row.contact))
    people = [contact_at(company, name, using=using) for name in sorted(names)]

    opportunity, _ = Opportunity.objects.using(using).update_or_create(
        company=company,
        title=row.title,
        date=row.date,
        defaults={
            "source": by_name(Source, row.source, using=using),
            "contact": people[0] if people else None,
            "job_description": row.job_description,
        },
    )
    return opportunity, names


def write(rows: Sequence[ParsedRow], *, using: str) -> Written:
    """Write a whole parsed export, in one transaction (§7).

    One transaction because a half-written import is the hardest thing to undo:
    the rows that landed look like real ones, and only a diff against the sheet
    says otherwise.
    """
    named = named_states(using=using)
    states = {state.slug: state for state in State.objects.using(using).all()}
    inferences: list[Inference] = []
    names: set[str] = set()
    steps = 0

    with transaction.atomic(using=using):
        for row in rows:
            opportunity, mentioned = write_row(row, using=using)
            names |= mentioned

            for parsed in row.steps:
                slug = state_for(parsed.title, named=named)
                inferences.append(
                    Inference(company=opportunity.company.name, title=parsed.title, state=slug)
                )
                names.update(parsed.contacts)
                write_step(
                    parsed,
                    opportunity=opportunity,
                    state=states.get(slug, states[DEFAULT_STATE]),
                    using=using,
                )
                steps += 1

        found = collisions_among(names, using=using)

    return Written(
        opportunities=len(rows), steps=steps, inferences=tuple(inferences), collisions=found
    )


def preview(rows: Sequence[ParsedRow], *, using: str) -> Written:
    """What a run would do, worked out by doing it and rolling it back (§7).

    A dry run that took a second code path would be a dry run that could differ
    from the real one, which is the one thing it must not do. The rollback is a
    savepoint, so nothing reaches the database and the report is exact.
    """
    with transaction.atomic(using=using):
        written = write(rows, using=using)
        transaction.set_rollback(True, using=using)
    return written


@dataclass(frozen=True)
class Entry:
    """One CSV row that was, or would be, created or skipped (plan 004 §7)."""

    line: int
    company: str
    title: str
    date: dt.date

    def __str__(self) -> str:
        """Where it is in the file, and what it is on the board."""
        return f"line {self.line}: {self.title} at {self.company}, {self.date.isoformat()}"


@dataclass(frozen=True)
class Imported:
    """What a CSV run came to. With any problem, nothing was written (plan 004 I4)."""

    created: tuple[Entry, ...]
    skipped: tuple[Entry, ...]
    problems: tuple[Problem, ...]


def form_problems(form: OpportunityForm, *, line: int) -> list[Problem]:
    """The form's own messages, one per field, placed on the row's line."""
    return [
        Problem(
            line=line,
            column="" if field == "__all__" else field,
            reason=" ".join(str(error) for error in errors),
        )
        for field, errors in form.errors.items()
    ]


def entry_for(form: OpportunityForm, *, line: int) -> Entry:
    """A validated row, named by what identifies it (plan 004 I5)."""
    data = form.cleaned_data
    return Entry(
        line=line, company=" ".join(data["company"].split()), title=data["title"], date=data["date"]
    )


def already_there(entry: Entry, *, using: str) -> bool:
    """Whether the board has this row, whatever case its company was typed in."""
    return (
        Opportunity.objects.using(using)
        .filter(company__name__iexact=entry.company, title=entry.title, date=entry.date)
        .exists()
    )


def import_opportunities(rows: Sequence[Row], *, using: str, dry_run: bool = False) -> Imported:
    """Validate every row through the board's form, then write them all or none.

    Nothing is written until every row has validated and no two rows in the file
    say the same thing, so a file that fails on its fortieth row has not already
    created thirty-nine companies. A row the board already has is skipped, never
    updated: it has been edited there since, and a stale file must not undo that.

    A dry run does the real thing and rolls it back, as plan 003's `preview`
    does, so it cannot take a path the real run would not.
    """
    problems: list[Problem] = []
    first_seen: dict[tuple[str, str, dt.date], int] = {}
    to_create: list[tuple[Entry, OpportunityForm]] = []
    skipped: list[Entry] = []

    for row in rows:
        form = OpportunityForm(data=row.values, using=using)
        if not form.is_valid():
            problems.extend(form_problems(form, line=row.line))
            continue

        entry = entry_for(form, line=row.line)
        key = (entry.company.lower(), entry.title, entry.date)
        if key in first_seen:
            reason = f"same company, title and date as line {first_seen[key]}"
            problems.append(Problem(line=row.line, column="", reason=reason))
            continue
        first_seen[key] = row.line

        if already_there(entry, using=using):
            skipped.append(entry)
        else:
            to_create.append((entry, form))

    if problems:
        return Imported(created=(), skipped=tuple(skipped), problems=tuple(problems))

    with transaction.atomic(using=using):
        for _, form in to_create:
            form.save().add_first_step()
        transaction.set_rollback(dry_run, using=using)

    created = tuple(entry for entry, _ in to_create)
    return Imported(created=created, skipped=tuple(skipped), problems=())
