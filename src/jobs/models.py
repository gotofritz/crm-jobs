"""Domain model for the jobs CRM — see docs/plans/001-port-gas-to-django.md §6.

The model layer knows that a step has a state and that a state belongs to a
group. It never knows what any of that looks like: colour lives in CSS (§6.3).
"""

import datetime as dt
from typing import TYPE_CHECKING, ClassVar

from django.db import models
from django.db.models import Q

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class Group(models.TextChoices):
    """The three buckets a state can sit in (§6.2)."""

    ATTENTION = "ATTENTION"
    DUE = "DUE"
    COMPLETE = "COMPLETE"


# A business rule, not data: adding a group means deciding where it ranks (§6.10).
GROUP_RANK = {Group.ATTENTION: 3, Group.DUE: 2, Group.COMPLETE: 1}


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

    slug = models.SlugField(unique=True)  # "bad-feeling" — the CSS hook
    name = models.CharField(max_length=50)  # "BAD_FEELING" — what is displayed
    group = models.CharField(max_length=20, choices=Group.choices)
    sort_order = models.PositiveIntegerField()  # the third tie-break in §4.5

    def __str__(self) -> str:
        """Name the state."""
        return self.name


class OpportunityQuerySet(models.QuerySet["Opportunity"]):
    """Live and archived are asked for explicitly — no manager filters silently (§6.5)."""

    def live(self) -> "OpportunityQuerySet":
        """Opportunities that have not been archived."""
        return self.filter(archived_at__isnull=True)

    def archived(self) -> "OpportunityQuerySet":
        """Opportunities that have been archived."""
        return self.exclude(archived_at__isnull=True)


class Opportunity(models.Model):
    """One application at one company, carrying the steps taken on it."""

    if TYPE_CHECKING:
        steps: "RelatedManager[Step]"

    company = models.ForeignKey(Company, related_name="opportunities", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)  # free text, see §6.8
    date = models.DateField()
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.SET_NULL)
    contact = models.ForeignKey(
        Contact, null=True, blank=True, related_name="opportunities", on_delete=models.SET_NULL
    )
    comments = models.TextField(blank=True, default="")
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
        return f"{self.state.name} on {self.date.isoformat()}"
