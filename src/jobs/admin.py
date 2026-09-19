"""Admin registrations — the CRUD backdoor while the real UI is built (plan 001 §6.9).

This is also where duplicate contacts and companies get merged, and, until
search exists, the only way to look at archived opportunities (§6.5).
"""

from django.contrib import admin

from jobs.models import Company, Contact, Employment, Opportunity, Sector, Source, State, Step


class StepInline(admin.TabularInline):
    """Steps are edited on their opportunity — they have no meaning without it."""

    model = Step
    extra = 1
    autocomplete_fields = ("state",)
    filter_horizontal = ("contacts",)


class EmploymentInline(admin.TabularInline):
    """Stints are edited from either end of the relationship (§6.7)."""

    model = Employment
    extra = 0
    autocomplete_fields = ("company", "contact")


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    """A picklist extended by typing (§6.10)."""

    search_fields = ("name",)


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    """A picklist extended by typing (§6.10)."""

    search_fields = ("name",)


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    """The state vocabulary. Its colours live in CSS, not here (§6.3)."""

    list_display = ("name", "slug", "group", "sort_order")
    list_filter = ("group",)
    ordering = ("sort_order",)
    search_fields = ("name", "slug")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Everything but the name is optional and often filled in later (§6)."""

    list_display = ("name", "sector", "head_office")
    list_filter = ("sector",)
    search_fields = ("name",)
    autocomplete_fields = ("sector",)
    inlines = (EmploymentInline,)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """Names are not unique, so the employments are what tell two people apart (§6.7)."""

    list_display = ("name",)
    search_fields = ("name",)
    inlines = (EmploymentInline,)


@admin.register(Employment)
class EmploymentAdmin(admin.ModelAdmin):
    """Who was where, when. NULL at either end means open (§6.7)."""

    list_display = ("contact", "company", "started_on", "ended_on")
    list_filter = ("company",)
    autocomplete_fields = ("company", "contact")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    """An opportunity and its steps are edited together."""

    list_display = ("title", "company", "date", "archived_at")
    list_filter = ("archived_at", "source")
    search_fields = ("title", "company__name")
    autocomplete_fields = ("company", "source", "contact")
    inlines = (StepInline,)


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    """Registered in its own right so a step can be found without its opportunity."""

    list_display = ("opportunity", "state", "date", "time", "title")
    list_filter = ("state",)
    autocomplete_fields = ("state",)
    filter_horizontal = ("contacts",)
