"""Moving the board in and out as tables of text — plan 005 §6.

Knows models, forms, natural keys and the transaction. It does not know about
files or TSV: it hands out and takes in `{table: rows}`, each row a dict of
strings, and the command reads and writes them.

Rows point at each other by natural key, never by id: a step names its
opportunity by company, title and date. Import is create-only, so a stale file
cannot undo an edit made on the board since, and all-or-nothing, so one bad row
writes nothing.
"""

import datetime as dt
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import NamedTuple

from django.db import DEFAULT_DB_ALIAS, transaction
from django.forms import BaseForm

from jobs.forms import (
    CompanyForm,
    ContactRowForm,
    ImportNoteForm,
    ImportOpportunityForm,
    LeadForm,
    StepForm,
    by_name,
)
from jobs.models import Company, Contact, Employment, Lead, Opportunity, State

Cells = dict[str, str]
# A row as the reader hands it over: the line it started on, and its cells.
Line = tuple[int, Cells]


class Columns(NamedTuple):
    """What a table must carry, and what it may."""

    required: tuple[str, ...]
    optional: tuple[str, ...] = ()


OPPORTUNITY_KEY = ("opportunity_company", "opportunity_title", "opportunity_date")

# In the order an import needs them: a row can only point at one before it.
TABLES: dict[str, Columns] = {
    "companies": Columns(("name",), ("url", "linkedin_url", "head_office", "sector")),
    "contacts": Columns(("name",), ("company", "started_on", "ended_on", "notes")),
    "opportunities": Columns(
        ("company", "title", "date"), ("source", "contact", "job_description", "archived_at")
    ),
    "steps": Columns(
        (*OPPORTUNITY_KEY, "state", "date"), ("time", "title", "contacts", "comments")
    ),
    "notes": Columns((*OPPORTUNITY_KEY, "body"), ("created_at",)),
    "leads": Columns(("name", "url"), ("notes",)),
}


class Issue(NamedTuple):
    """One thing wrong with one row."""

    table: str
    line: int
    column: str
    message: str


@dataclass
class Report:
    """What an import did, or would have done."""

    created: Counter[str] = field(default_factory=Counter)
    skipped: Counter[str] = field(default_factory=Counter)
    issues: list[Issue] = field(default_factory=list)


def _stamp(value: dt.datetime | None) -> str:
    """A timestamp as ISO text, empty for none."""
    return value.isoformat() if value else ""


def _opportunity_key(opportunity: Opportunity) -> Cells:
    """The three cells that name an opportunity from another table."""
    return {
        "opportunity_company": opportunity.company.name,
        "opportunity_title": opportunity.title,
        "opportunity_date": opportunity.date.isoformat(),
    }


def _sorted_by_key(opportunities: Iterable[Opportunity]) -> list[Opportunity]:
    """Company, title, date, then id: stable, and the same on two databases."""
    return sorted(opportunities, key=lambda o: (o.company.name, o.title, o.date, o.pk))


# Free text is exported stripped, because the forms strip it on the way in: what
# is written is what an import would accept, so exporting twice agrees.
def export_tables(*, using: str = DEFAULT_DB_ALIAS) -> dict[str, list[Cells]]:
    """Every row of the board, as cells, in an order that depends only on the data."""
    companies = Company.objects.using(using).select_related("sector").order_by("name")
    contacts = Contact.objects.using(using).prefetch_related("employments__company")
    opportunities = _sorted_by_key(
        Opportunity.objects.using(using)
        .select_related("company", "source", "contact")
        .prefetch_related("steps__state", "steps__contacts", "notes")
    )

    contact_rows: list[Cells] = []
    for person in sorted(contacts, key=lambda c: (c.name, c.pk)):
        stints = sorted(
            person.employments.all(),
            key=lambda e: (e.company.name, e.started_on or dt.date.min, e.ended_on or dt.date.min),
        )
        if not stints:
            contact_rows.append(
                {
                    "name": person.name,
                    "company": "",
                    "started_on": "",
                    "ended_on": "",
                    "notes": person.notes,
                }
            )
        contact_rows.extend(
            {
                "name": person.name,
                "company": stint.company.name,
                "started_on": stint.started_on.isoformat() if stint.started_on else "",
                "ended_on": stint.ended_on.isoformat() if stint.ended_on else "",
                "notes": person.notes,
            }
            for stint in stints
        )

    step_rows: list[Cells] = []
    note_rows: list[Cells] = []
    for opportunity in opportunities:
        key = _opportunity_key(opportunity)
        steps = sorted(
            opportunity.steps.all(),
            key=lambda s: (s.date, s.time or dt.time.min, s.state.slug, s.title, s.pk),
        )
        step_rows.extend(
            {
                **key,
                "state": step.state.slug,
                "date": step.date.isoformat(),
                "time": step.time.strftime("%H:%M") if step.time else "",
                "title": step.title,
                "contacts": step.contact_names,
                "comments": step.comments.strip(),
            }
            for step in steps
        )
        note_rows.extend(
            {**key, "body": note.body.strip(), "created_at": _stamp(note.created_at)}
            for note in sorted(opportunity.notes.all(), key=lambda n: (n.created_at, n.pk))
        )

    return {
        "companies": [
            {
                "name": company.name,
                "url": company.url,
                "linkedin_url": company.linkedin_url,
                "head_office": company.head_office,
                "sector": company.sector.name if company.sector else "",
            }
            for company in companies
        ],
        "contacts": contact_rows,
        "opportunities": [
            {
                "company": opportunity.company.name,
                "title": opportunity.title,
                "date": opportunity.date.isoformat(),
                "source": opportunity.source.name if opportunity.source else "",
                "contact": opportunity.contact.name if opportunity.contact else "",
                "job_description": opportunity.job_description.strip(),
                "archived_at": _stamp(opportunity.archived_at),
            }
            for opportunity in opportunities
        ],
        "steps": step_rows,
        "notes": note_rows,
        # Oldest first: the sources page lists by descending id, so importing in
        # this order brings the list back the way it was.
        "leads": [
            {"name": lead.name, "url": lead.url, "notes": lead.notes.strip()}
            for lead in Lead.objects.using(using).order_by("pk")
        ],
    }


class _Importer:
    """One import run: the database it writes to, and what it has found so far."""

    def __init__(self, *, using: str) -> None:
        self.using = using
        self.report = Report()
        # Opportunities whose own row was rejected, so their steps and notes are
        # not reported a second time as pointing at nothing.
        self._rejected: set[tuple[str, str, str]] = set()

    def run(self, table: str, rows: Sequence[Line]) -> None:
        """Import every row of one table."""
        handler: Callable[[int, Cells], None] = getattr(self, f"_{table}")
        for line, cells in rows:
            self._current = (table, line)
            handler(line, cells)

    # -- bookkeeping ---------------------------------------------------------

    def _created(self, table: str) -> None:
        self.report.created[table] += 1

    def _skipped(self, table: str) -> None:
        self.report.skipped[table] += 1

    def _issue(self, column: str, message: str) -> None:
        table, line = self._current
        self.report.issues.append(Issue(table, line, column, message))

    def _form_issues(self, form: BaseForm) -> None:
        for column, messages in form.errors.items():
            for message in messages:
                self._issue(column if column != "__all__" else "", str(message))

    # -- tables --------------------------------------------------------------

    def _companies(self, _line: int, cells: Cells) -> None:
        form = CompanyForm(data=cells, using=self.using)
        if not form.is_valid():
            return self._form_issues(form)
        name = form.cleaned_data["name"]
        if Company.objects.using(self.using).filter(name__iexact=name).exists():
            return self._skipped("companies")
        form.save()
        self._created("companies")

    def _contacts(self, _line: int, cells: Cells) -> None:
        form = ContactRowForm(data=cells)
        if not form.is_valid():
            return self._form_issues(form)
        data = form.cleaned_data
        person = Contact.objects.using(self.using).filter(name=data["name"]).first()
        made = person is None
        if person is None:
            person = Contact.objects.using(self.using).create(
                name=data["name"], notes=data["notes"]
            )
        if data["company"]:
            company = by_name(Company, data["company"], using=self.using)
            _, stint_made = Employment.objects.using(self.using).get_or_create(
                contact=person,
                company=company,
                started_on=data["started_on"],
                defaults={"ended_on": data["ended_on"]},
            )
            made = made or stint_made
        if made:
            self._created("contacts")
        else:
            self._skipped("contacts")

    def _opportunities(self, _line: int, cells: Cells) -> None:
        form = ImportOpportunityForm(data=cells, using=self.using)
        if not form.is_valid():
            self._rejected.add((cells["company"], cells["title"], cells["date"]))
            return self._form_issues(form)
        existing = self._find(
            form.cleaned_data["company"], form.cleaned_data["title"], form.cleaned_data["date"]
        )
        if existing is not None:
            return self._skipped("opportunities")
        form.save()
        self._created("opportunities")

    def _steps(self, _line: int, cells: Cells) -> None:
        opportunity = self._parent(cells)
        if opportunity is None:
            return
        state = State.objects.using(self.using).filter(slug=cells["state"]).first()
        if state is None:
            return self._issue("state", f"unknown state {cells['state']!r}")
        form = StepForm(
            data={**cells, "state": state.pk}, opportunity=opportunity, using=self.using
        )
        if not form.is_valid():
            return self._form_issues(form)
        data = form.cleaned_data
        exists = opportunity.steps.filter(
            state=state, date=data["date"], time=data["time"], title=data["title"]
        ).exists()
        if exists:
            return self._skipped("steps")
        form.save()
        self._created("steps")

    def _notes(self, _line: int, cells: Cells) -> None:
        opportunity = self._parent(cells)
        if opportunity is None:
            return
        form = ImportNoteForm(data=cells, opportunity=opportunity, using=self.using)
        if not form.is_valid():
            return self._form_issues(form)
        stamp = form.cleaned_data["created_at"]
        # A note with no date is new by definition: it has no key to match on.
        if (
            stamp is not None
            and opportunity.notes.filter(created_at=stamp, body=form.cleaned_data["body"]).exists()
        ):
            return self._skipped("notes")
        form.save()
        self._created("notes")

    def _leads(self, _line: int, cells: Cells) -> None:
        form = LeadForm(data=cells)
        if not form.is_valid():
            return self._form_issues(form)
        data = form.cleaned_data
        if Lead.objects.using(self.using).filter(name=data["name"], url=data["url"]).exists():
            return self._skipped("leads")
        form.save(commit=False).save(using=self.using)
        self._created("leads")

    # -- looking rows up -----------------------------------------------------

    def _find(self, company: str, title: str, date: dt.date | str) -> Opportunity | None:
        """The opportunity with this natural key, if it is already in the database."""
        return (
            Opportunity.objects.using(self.using)
            .filter(company__name__iexact=company, title=title, date=date)
            .first()
        )

    def _parent(self, cells: Cells) -> Opportunity | None:
        """The opportunity a step or note names, or a problem saying there is none."""
        company, title, date = (cells[column] for column in OPPORTUNITY_KEY)
        try:
            found = self._find(company, title, dt.date.fromisoformat(date))
        except ValueError:
            self._issue("opportunity_date", f"{date!r} is not a YYYY-MM-DD date")
            return None
        if found is None and (company, title, date) not in self._rejected:
            self._issue("opportunity_title", f"no opportunity {title!r} at {company!r} on {date}")
        return found


def import_tables(
    tables: Mapping[str, Sequence[Line]],
    *,
    using: str = DEFAULT_DB_ALIAS,
    dry_run: bool = False,
) -> Report:
    """Create what `tables` hold that the database lacks, or report why it cannot.

    The real import runs inside a transaction, and is rolled back when anything
    was wrong or `dry_run` asked for a preview, so the preview cannot differ from
    the run. Rows already there are skipped, never updated.
    """
    importer = _Importer(using=using)
    with transaction.atomic(using=using):
        for table in TABLES:
            importer.run(table, tables.get(table, ()))
        if dry_run or importer.report.issues:
            transaction.set_rollback(True, using=using)
    return importer.report
