"""Seed the picklists a fresh database needs — plan 001 §6.1 and §6.10.

States come from the live sheet's header row, in column order. Sources and
sectors are starter sets: new values are created by typing them (§6.9), so
this is a head start, not a fixed vocabulary.
"""

from django.db import migrations

STATES = [
    (1, "ATTENTION", "ERROR", "error"),
    (2, "ATTENTION", "OVERDUE", "overdue"),
    (3, "DUE", "DUE", "due"),
    (4, "DUE", "TENTATIVE", "tentative"),
    (5, "COMPLETE", "ACCEPTED", "accepted"),
    (6, "COMPLETE", "SUCCESS", "success"),
    (7, "COMPLETE", "BAD_FEELING", "bad-feeling"),
    (8, "COMPLETE", "GOING_WELL", "going-well"),
    (9, "COMPLETE", "UNREMARKABLE", "unremarkable"),
    (10, "COMPLETE", "GHOSTED", "ghosted"),
    (11, "COMPLETE", "FAIL", "fail"),
    (12, "COMPLETE", "BLACKLIST", "blacklist"),
]

SOURCES = ["LinkedIn", "Wellfound", "Referral", "Direct", "Recruiter"]

SECTORS = [
    "AI / ML",
    "Consultancy / agency",
    "Developer tools",
    "E-commerce",
    "Education",
    "Energy",
    "Fintech",
    "Gaming",
    "Government / public sector",
    "Healthtech",
    "Logistics",
    "Media / publishing",
    "Non-profit",
    "Retail",
    "SaaS",
    "Telecoms",
    "Travel",
    "Other",
]


def seed_picklists(apps, _schema_editor) -> None:
    """Create the starter states, sources and sectors, leaving existing rows alone."""
    state_model = apps.get_model("jobs", "State")
    source_model = apps.get_model("jobs", "Source")
    sector_model = apps.get_model("jobs", "Sector")

    for sort_order, group, name, slug in STATES:
        state_model.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "group": group, "sort_order": sort_order},
        )
    for name in SOURCES:
        source_model.objects.get_or_create(name=name)
    for name in SECTORS:
        sector_model.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    """Seed data only — nothing is removed on reverse, because steps point at states."""

    dependencies = [("jobs", "0001_initial")]

    operations = [migrations.RunPython(seed_picklists, migrations.RunPython.noop)]
