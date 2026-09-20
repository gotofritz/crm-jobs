"""Forms — validation and coercion, and nothing else (AGENTS.md, "Boundaries").

Every picklist here is a text input backed by a `<datalist>`, resolved on save.
That is what lets the model be normalised without dragging in a management
screen per table (§6.9): typing a new company creates it, typing an existing
one reuses it.

`State` is the one exception, and the reason is in §6.10: a new state needs a
group and a `sort_order`, which is a decision in code. A new sector is not. So
sectors are typed and states are chosen.

Resolution happens in `save`, never in `clean`: a form that fails validation
must not leave a half-created company behind.
"""

from typing import Any, ClassVar, TypeVar

from django import forms
from django.db import DEFAULT_DB_ALIAS, models

from jobs.models import Company, Contact, Note, Opportunity, Sector, Source, Step

M = TypeVar("M", bound=models.Model)


# `LANGUAGE_CODE` is `en-gb`, so Django localises a date on the way out as
# `05/01/2026`. A native date input only understands `YYYY-MM-DD` and shows an
# empty box for anything else — and the field is required, so that turns into a
# card that cannot be saved. The format is therefore stated rather than left to
# the locale. Reading a date back is unaffected: `DATE_INPUT_FORMATS` for en-gb
# accepts both spellings, so a form still takes what a person types.
def named(hint: str, label: str) -> dict[str, str]:
    """What every box on a card carries, whatever kind of box it is.

    A placeholder, because the card's heading is a title and a company with no
    label between them: two empty boxes there are indistinguishable, which is
    how a company ends up typed into a job title.

    An `aria-label`, because a placeholder stops helping the moment the box has
    something in it, and because nothing here renders a `<label for=…>` — the
    `<dt>` beside a field is a description term, not a label.
    """
    return {"placeholder": hint, "aria-label": label}


def suggesting(list_id: str, hint: str, label: str) -> forms.TextInput:
    """A text input that drops down what is already stored, and still takes a new name.

    The `list` is half of it; the other half is the `<datalist>` the view puts on
    the page, which `_datalists` works out from these attributes so the two
    cannot disagree. `autocomplete="off"` keeps the browser's own history from
    opening a second dropdown over the first — only one of them knows the data.
    """
    return forms.TextInput(attrs={"list": list_id, "autocomplete": "off"} | named(hint, label))


def box(rows: int, hint: str, label: str) -> forms.Textarea:
    """A textarea sized to the card it sits on.

    Django's default is ten rows, which on an 18rem summary card runs past the
    bottom edge — the box has no visible end and the card cannot contain it.
    """
    return forms.Textarea(attrs={"rows": str(rows)} | named(hint, label))


ISO_DATE = "%Y-%m-%d"
# Seconds are noise on a card, and the sheet stored ":" for an unset time (§4.5).
ISO_TIME = "%H:%M"

# Form field -> the `Company` field it writes. All four are optional and are
# filled in from the opportunity form rather than a screen of their own.
COMPANY_DETAILS = {
    "company_url": "url",
    "company_linkedin_url": "linkedin_url",
    "company_head_office": "head_office",
}


# What an in-place edit may name in a URL. Everything the board shows, and
# nothing else: `archived_at` is the archive's own action (§6.5), and the
# timestamps belong to the model.
EDITABLE: dict[type[models.Model], set[str]] = {
    Opportunity: {
        "title",
        "company",
        "date",
        "source",
        "contact",
        "job_description",
        "company_url",
        "company_linkedin_url",
        "company_head_office",
        "company_sector",
    },
    Step: {"state", "date", "time", "title", "comments", "contacts"},
    Note: {"body"},
}


def by_name(model: type[M], raw: str, *, using: str = DEFAULT_DB_ALIAS) -> M | None:
    """Resolve free text to a picklist row, creating it when it is new (§6.9).

    The first spelling entered wins: a later `FINTECH` matches the stored
    `Fintech` rather than renaming it or forking a second row. Blank resolves to
    nothing, because source and contact are optional and an empty input must not
    leave an empty row behind.

    On SQLite `iexact` is ASCII-only, which is fine for these names and worth
    knowing before anyone relies on it for accented ones (§6.9).

    `using` is here for the sheet importer, which resolves the same names against
    whichever database `--demo` picked (plan 003 §5). A form always means the one
    the request is being served from.
    """
    name = " ".join(raw.split())
    if not name:
        return None
    objects = model._default_manager.db_manager(using)
    return objects.filter(name__iexact=name).first() or objects.create(name=name)


def names_of(raw: str) -> list[str]:
    """Split a comma-separated list of names, dropping the empties."""
    return [name for name in (part.strip() for part in raw.split(",")) if name]


class FieldScoped(forms.ModelForm):
    """A `ModelForm` that can be narrowed to the one field an edit is about.

    The board edits in place: clicking a job title edits the job title, and the
    browser sends that field and nothing else. A whole-object form fed one field
    would reject the row for the others it never received, so the form is cut
    down to match the request instead.

    Narrowing is also what keeps an edit honest. `only` is checked against
    `EDITABLE`, so `archived_at` — which is how the archive works (§6.5) — and
    the model's own timestamps cannot be reached by naming one in a URL.
    """

    def __init__(self, *args: Any, only: str | None = None, **kwargs: Any) -> None:
        """Build the whole form, then keep one field if `only` names one."""
        super().__init__(*args, **kwargs)
        self.only = only
        # Overwritten by `OpportunityForm` when it was opened on a saved row.
        self._opened_on: int | None = None
        if only is None:
            return
        # The instance's own class rather than `Meta.model`: it is the same
        # class, and it is the one a type checker can see is not `None`.
        model = type(self.instance)
        if only not in EDITABLE[model]:
            message = f"{only} is not editable in place on {model.__name__}"
            raise KeyError(message)
        self.fields = {only: self.fields[only]}

    def edits(self, field: str) -> bool:
        """Whether this form is responsible for `field`.

        A narrowed form writes only what it was opened on; a whole one writes
        everything. `save` asks this before any of the resolution that turns free
        text into rows, because an edit that never sent a company must not create
        one, and one that never sent the contacts must not empty them.
        """
        return field in self.fields


class OpportunityForm(FieldScoped):
    """An opportunity and, in passing, the company it is at (§6.9).

    The pasted ad is deliberately absent: it has a dialog of its own, the way
    the GAS app's comments did (§4.4), and an 1870-character textarea does not
    belong in the form used to add a row in a hurry.
    """

    company = forms.CharField(
        max_length=200,
        label="Company",
        widget=suggesting("companies-list", "Company, e.g. Northwind Analytics", "Company"),
    )
    source = forms.CharField(
        max_length=100,
        required=False,
        label="Source",
        widget=suggesting("sources-list", "Where you saw it", "Source"),
    )
    contact = forms.CharField(
        max_length=200,
        required=False,
        label="Contact",
        widget=suggesting("contacts-list", "Who you dealt with", "Contact"),
    )

    # The four optional company fields, edited from here because a company
    # created mid-flow needs only a name and the rest arrives later.
    company_url = forms.URLField(
        required=False,
        label="Site",
        widget=forms.URLInput(attrs=named("https://northwind.example", "Company site")),
    )
    company_linkedin_url = forms.URLField(
        required=False,
        label="LinkedIn",
        widget=forms.URLInput(
            attrs=named("https://linkedin.com/company/…", "Company LinkedIn page")
        ),
    )
    company_head_office = forms.CharField(
        max_length=200,
        required=False,
        label="Office",
        widget=forms.TextInput(attrs=named("Where they are based", "Head office")),
    )
    company_sector = forms.CharField(
        max_length=100,
        required=False,
        label="Sector",
        widget=suggesting("sectors-list", "Fintech, SaaS, healthtech…", "Sector"),
    )

    class Meta:
        """Only the fields the model can take verbatim; the rest are resolved in `save`."""

        model = Opportunity
        fields = ("title", "date", "job_description")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            # The heading pair. These two sit one above the other with no label
            # between them, so their hints are the only thing telling them apart.
            "title": forms.TextInput(attrs=named("Job title, e.g. Staff Engineer", "Job title")),
            "date": forms.DateInput(attrs={"type": "date"}, format=ISO_DATE),
            # The pasted ad is the long one — 1870 characters in the sample
            # export (§4.8) — so it gets more room than a note does.
            "job_description": box(6, "Paste the ad here", "Job description"),
        }
        # A card in edit mode is the same card, so it prints the same labels.
        labels: ClassVar[dict[str, str]] = {"date": "Applied"}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Open the text inputs on what is stored, so an edit is not a retype."""
        super().__init__(*args, **kwargs)
        opportunity = self.instance
        if opportunity.pk is None:
            return
        # Which company the boxes below were filled from, so `_resolve_company`
        # can tell an emptied field from one that was never filled in.
        self._opened_on = opportunity.company.pk
        company = opportunity.company
        self.initial.setdefault("company", company.name)
        self.initial.setdefault("source", opportunity.source.name if opportunity.source else "")
        self.initial.setdefault("contact", opportunity.contact.name if opportunity.contact else "")
        self.initial.setdefault("company_url", company.url)
        self.initial.setdefault("company_linkedin_url", company.linkedin_url)
        self.initial.setdefault("company_head_office", company.head_office)
        self.initial.setdefault("company_sector", company.sector.name if company.sector else "")

    def _resolve_company(self) -> Company:
        """The company this opportunity is at, created by typing it if it is new (§6.9).

        Whether a blank detail clears the stored one depends on whether the form
        was opened on that company. If it was, the box was shown holding the
        value, so emptying it is an instruction. If it was not — a create, or a
        company just typed in — the box was blank because nobody filled it in,
        and writing that over what the company already has would be a side
        effect of the row rather than a decision about the company.
        """
        # On a create the form is whole, so the typed name is always there. On a
        # narrowed edit of some other field it is not, and the row keeps the
        # company it already had.
        typed = by_name(Company, self.cleaned_data["company"]) if self.edits("company") else None
        company = typed if typed is not None else self.instance.company

        opened_on_it = company.pk is not None and company.pk == self._opened_on

        changed = []
        for form_field, company_field in COMPANY_DETAILS.items():
            value = self.cleaned_data.get(form_field, "")
            if self.edits(form_field) and (value or opened_on_it):
                setattr(company, company_field, value)
                changed.append(company_field)

        if self.edits("company_sector"):
            sector = by_name(Sector, self.cleaned_data["company_sector"])
            if sector is not None or opened_on_it:
                company.sector = sector
                changed.append("sector")

        if changed:
            company.save(update_fields=changed)
        return company

    def save(self, commit: bool = True) -> Opportunity:
        """Resolve the typed names, then save. Nothing is created until the form is valid.

        `commit` stays positional-or-keyword because `ModelForm.save` declares it
        that way, and a stricter override is not a drop-in replacement.
        """
        opportunity = super().save(commit=False)
        opportunity.company = self._resolve_company()
        if self.edits("source"):
            opportunity.source = by_name(Source, self.cleaned_data["source"])
        if self.edits("contact"):
            opportunity.contact = by_name(Contact, self.cleaned_data["contact"])
        if commit:
            opportunity.save()
        return opportunity


class StepForm(FieldScoped):
    """Something that happened on an opportunity, in one state.

    `state` is a choice rather than free text: unlike a sector, a new state
    needs a group and a rank, which is a decision in code (§6.10).
    """

    contacts = forms.CharField(
        max_length=500,
        required=False,
        label="Contacts",
        help_text="Separate several with commas.",
        widget=suggesting("contacts-list", "Ada Lovelace, Grace Hopper", "Who this step was with"),
    )

    class Meta:
        """The step's own fields; `contacts` is resolved from free text in `save`."""

        model = Step
        fields = ("state", "date", "time", "title", "comments")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "title": forms.TextInput(attrs=named("What happened", "Step")),
            "date": forms.DateInput(attrs={"type": "date"}, format=ISO_DATE),
            "time": forms.TimeInput(attrs={"type": "time"}, format=ISO_TIME),
            "comments": box(3, "Anything worth remembering", "Notes on this step"),
        }

    def __init__(self, *args: Any, opportunity: Opportunity, **kwargs: Any) -> None:
        """A step has no meaning without its opportunity, so it is not optional here."""
        super().__init__(*args, **kwargs)
        self.opportunity = opportunity
        if self.instance.pk is not None:
            self.initial.setdefault("contacts", self.instance.contact_names)

    def save(self, commit: bool = True) -> Step:
        """Save against the opportunity, resolving each typed contact name (§6.9)."""
        step = super().save(commit=False)
        step.opportunity = self.opportunity
        if not commit:
            return step
        step.save()
        # An edit that never sent the contacts must not empty them.
        if self.edits("contacts"):
            people = [by_name(Contact, name) for name in names_of(self.cleaned_data["contacts"])]
            step.contacts.set([person for person in people if person is not None])
        return step


class NoteForm(FieldScoped):
    """One remark on an opportunity. A row, so it can be dated and removed on its own."""

    class Meta:
        """The body is the note; its date is the model's business."""

        model = Note
        fields = ("body",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "body": box(3, "What is worth remembering", "Note")
        }

    def __init__(self, *args: Any, opportunity: Opportunity, **kwargs: Any) -> None:
        """A note belongs to an opportunity, and is never written without one."""
        super().__init__(*args, **kwargs)
        self.opportunity = opportunity

    def save(self, commit: bool = True) -> Note:
        """Save against the opportunity the form was opened on."""
        note = super().save(commit=False)
        note.opportunity = self.opportunity
        if commit:
            note.save()
        return note


class JobDescriptionForm(forms.ModelForm):
    """The pasted ad, edited on its own — the dialog the GAS app gave comments (§4.4)."""

    class Meta:
        """One field, so this dialog cannot quietly rewrite anything else."""

        model = Opportunity
        fields = ("job_description",)
