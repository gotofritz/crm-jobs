"""Domain model for the jobs CRM — see the archived plan 001 §6.

The model layer knows that a step has a state and that a state belongs to a
group. It never knows what any of that looks like: colour lives in CSS (§6.3).
"""

import datetime as dt
from typing import TYPE_CHECKING, ClassVar

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import Truncator

from jobs.ordering import sort_notes, sort_opportunities, sort_steps

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


# The state a new opportunity's first step lands in (§6.6). A slug rather than a
# row, because `State` is data and this module must not query at import time.
DEFAULT_STEP_STATE = "unremarkable"


class Group(models.TextChoices):
    """The three buckets a state can sit in (§6.2)."""

    ATTENTION = "ATTENTION"
    DUE = "DUE"
    COMPLETE = "COMPLETE"


class Sector(models.Model):
    """A coarse industry label, extended by typing rather than by deploy (§6.10)."""

    if TYPE_CHECKING:
        companies: "RelatedManager[Company]"

    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        """Name the sector."""
        return self.name


class Company(models.Model):
    """An employer.

    Every field but the name is optional: a company is usually created mid-flow,
    when all that is known is its name (§6).
    """

    if TYPE_CHECKING:
        opportunities: "RelatedManager[Opportunity]"
        employments: "RelatedManager[Employment]"

    name = models.CharField(max_length=200, unique=True)
    url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    head_office = models.CharField(max_length=200, blank=True, default="")
    sector = models.ForeignKey(
        Sector, null=True, blank=True, related_name="companies", on_delete=models.SET_NULL
    )

    def __str__(self) -> str:
        """Name the company."""
        return self.name


class Contact(models.Model):
    """A person. The name is deliberately not unique — two people share one (§6.7)."""

    if TYPE_CHECKING:
        opportunities: "RelatedManager[Opportunity]"
        employments: "RelatedManager[Employment]"
        steps: "RelatedManager[Step]"

    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        """Name the contact."""
        return self.name


class EmploymentQuerySet(models.QuerySet["Employment"]):
    """Stints, asked about by the day they were true."""

    def on(self, day: dt.date) -> "EmploymentQuerySet":
        """Stints in force on ``day``, counting a NULL bound as open rather than absent."""
        return self.filter(
            Q(started_on__isnull=True) | Q(started_on__lte=day),
            Q(ended_on__isnull=True) | Q(ended_on__gte=day),
        )


class Employment(models.Model):
    """Who was where, when. One row per stint, because a contact moves (§6.7)."""

    contact = models.ForeignKey(Contact, related_name="employments", on_delete=models.CASCADE)
    company = models.ForeignKey(Company, related_name="employments", on_delete=models.CASCADE)
    started_on = models.DateField(null=True, blank=True)  # NULL = unknown
    ended_on = models.DateField(null=True, blank=True)  # NULL = still there

    objects = EmploymentQuerySet.as_manager()

    class Meta:
        """Overlapping stints are allowed; the same stint recorded twice is not."""

        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["contact", "company", "started_on"], name="unique_stint"
            )
        ]

    def __str__(self) -> str:
        """Name the stint by its person and company."""
        return f"{self.contact.name} at {self.company.name}"


class Source(models.Model):
    """Where an opportunity came from: LinkedIn, Wellfound, a referral (§6.10)."""

    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        """Name the source."""
        return self.name


class State(models.Model):
    """What a step means. The vocabulary is data; its colours are not (§6.10)."""

    slug = models.SlugField(unique=True)  # "bad-feeling" — the key, and the CSS hook
    # "Bad Feeling" — what a card prints. Empty means there is nothing worth
    # printing, which is how UNREMARKABLE renders as a bare card (§6.6).
    name = models.CharField(max_length=50, blank=True, default="")
    group = models.CharField(max_length=20, choices=Group.choices)
    sort_order = models.PositiveIntegerField()  # the third tie-break in §4.5

    def __str__(self) -> str:
        """Name the state, falling back to the slug for the ones with no name."""
        return self.name or self.slug


class OpportunityQuerySet(models.QuerySet["Opportunity"]):
    """Live and archived are asked for explicitly — no manager filters silently (§6.5)."""

    def live(self) -> "OpportunityQuerySet":
        """Opportunities that have not been archived."""
        return self.filter(archived_at__isnull=True)

    def archived(self) -> "OpportunityQuerySet":
        """Opportunities that have been archived."""
        return self.exclude(archived_at__isnull=True)

    def in_board_order(self) -> "list[Opportunity]":
        """Board order (§4.5).

        A list, not a queryset: the date tie-break inverts on the state's group,
        which SQL cannot express in one ORDER BY. The joins and the prefetch are
        what keep the sort, and the summary card that follows it, from costing a
        query per row.
        """
        rows = self.select_related("company", "source", "contact").prefetch_related(
            "steps__state", "steps__contacts", "notes"
        )
        return sort_opportunities(rows)

    def in_archive_order(self) -> "OpportunityQuerySet":
        """Archived opportunities, most recently put away first (§6.5).

        Urgency ranking is meaningless once nothing is pending; "which burst was
        this" is the only question left.
        """
        return self.order_by("-archived_at")


class Opportunity(models.Model):
    """One application at one company, carrying the steps taken on it."""

    if TYPE_CHECKING:
        steps: "RelatedManager[Step]"
        notes: "RelatedManager[Note]"

    company = models.ForeignKey(Company, related_name="opportunities", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)  # free text, see §6.8
    date = models.DateField()
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.SET_NULL)
    contact = models.ForeignKey(
        Contact, null=True, blank=True, related_name="opportunities", on_delete=models.SET_NULL
    )
    # The pasted job ad — 1870 characters in the sample export (§4.8). Notes about
    # the application are `Note` rows, not prose in here.
    job_description = models.TextField(blank=True, default="")
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OpportunityQuerySet.as_manager()

    class Meta:
        """Django model options."""

        verbose_name_plural = "opportunities"

    def __str__(self) -> str:
        """Name the opportunity by its title and company."""
        return f"{self.title} at {self.company.name}"

    def add_first_step(self) -> "Step":
        """Open this opportunity with a step, the way the GAS app did (§4.4).

        The step is dated when the application went out and carries the
        opportunity's contact, so the row has something in its track from the
        moment it exists. A domain rule, so it lives here: a second way of
        creating an opportunity must not be able to skip it.
        """
        step = Step.objects.create(
            opportunity=self,
            state=State.objects.get(slug=DEFAULT_STEP_STATE),
            date=self.date,
        )
        if self.contact is not None:
            step.contacts.add(self.contact)
        return step

    @property
    def ordered_steps(self) -> "list[Step]":
        """This opportunity's steps in §4.5 order, so the board template need not sort.

        Reads the prefetched rows `in_board_order` loaded, so the board costs no
        query per row. Ordering is a rule, and rules do not belong in a template
        (§6.3).
        """
        return sort_steps(self.steps.all())

    @property
    def ordered_notes(self) -> "list[Note]":
        """This opportunity's notes newest first, so the board template need not sort.

        Reads the rows `in_board_order` prefetched, for the same reason
        `ordered_steps` does. Ordering is a rule, and rules do not belong in a
        template (§6.3).
        """
        return sort_notes(self.notes.all())


class Step(models.Model):
    """Something that happened on an opportunity, in one state."""

    opportunity = models.ForeignKey(Opportunity, related_name="steps", on_delete=models.CASCADE)
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)  # the GAS app treats ":" as empty
    title = models.CharField(max_length=200, default="Applied via site")
    contacts = models.ManyToManyField(Contact, blank=True, related_name="steps")
    comments = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        """Name the step by its state and date."""
        return f"{self.state} on {self.date.isoformat()}"

    @property
    def contact_names(self) -> str:
        """Who this step was with, as the card prints it and the form takes it back.

        Sorted in Python rather than with `order_by`, which would issue a query
        of its own and undo the prefetch `in_board_order` set up — the same
        reason `ordered_steps` sorts the way it does.
        """
        return ", ".join(sorted(person.name for person in self.contacts.all()))


class Note(models.Model):
    """A remark written on an opportunity — "not sure about this", and why.

    A row rather than a line of prose, so each one can be dated, read newest
    first, and removed on its own. The job ad it sits beside is
    `Opportunity.job_description`; the two are different kinds of text and no
    longer share a field.
    """

    opportunity = models.ForeignKey(Opportunity, related_name="notes", on_delete=models.CASCADE)
    body = models.TextField()
    # `default` rather than `auto_now_add`: the latter makes the field unwritable,
    # and the demo seed dates its notes by hand so a re-run cannot reorder them.
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        """Name the note by its opening words — a label, not the whole note."""
        return Truncator(self.body).chars(60)
