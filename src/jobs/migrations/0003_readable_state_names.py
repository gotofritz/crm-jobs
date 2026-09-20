"""Make state names readable — plan 001 §6.1.

The SCREAMING_SNAKE names came straight from the sheet's header row, where they
were column labels rather than anything a person read. `slug` is what the code
looks up and what the stylesheet keys on, so `name` is free to be what its
comment always said it was: the thing printed on a card.

UNREMARKABLE loses its name entirely. It is the state a new opportunity lands in
(§6.6) and it means nothing notable happened, so there is nothing worth printing.
Empty in the data rather than hidden in the template: what a state is called is
the state's business.
"""

from django.db import migrations, models

# slug: (name before, name after)
NAMES = {
    "error": ("ERROR", "Error"),
    "overdue": ("OVERDUE", "Overdue"),
    "due": ("DUE", "Due"),
    "tentative": ("TENTATIVE", "Tentative"),
    "accepted": ("ACCEPTED", "Accepted"),
    "success": ("SUCCESS", "Success"),
    "bad-feeling": ("BAD_FEELING", "Bad Feeling"),
    "going-well": ("GOING_WELL", "Going Well"),
    "unremarkable": ("UNREMARKABLE", ""),
    "ghosted": ("GHOSTED", "Ghosted"),
    "fail": ("FAIL", "Fail"),
    "blacklist": ("BLACKLIST", "Blacklist"),
}


def rename(apps, schema_editor, index):
    """Rewrite the seeded names, leaving any state added since alone."""
    State = apps.get_model("jobs", "State")
    for slug, names in NAMES.items():
        State.objects.filter(slug=slug, name=names[1 - index]).update(name=names[index])


def to_readable(apps, schema_editor):
    """Sheet header to something a person reads."""
    rename(apps, schema_editor, 1)


def to_sheet_headers(apps, schema_editor):
    """Back to the sheet's header row."""
    rename(apps, schema_editor, 0)


class Migration(migrations.Migration):
    """Readable state names, and a name that is allowed to be empty."""

    dependencies = [("jobs", "0002_seed_picklists")]

    operations = [
        migrations.AlterField(
            model_name="state",
            name="name",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.RunPython(to_readable, to_sheet_headers),
    ]
