"""Writing a parsed sheet export into the database — plan 003 §5.

The half of the import that touches the ORM. `jobs.sheet` turns the exported
text into dataclasses and knows nothing about models; this turns those
dataclasses into rows and knows nothing about the file they came from. The
management command is the thin thing joining them.
"""

# The alias `manage.py import_sheet --demo` writes to, and the one it writes to
# otherwise. Both are configured in `config.settings` (plan 003 I4).
DEMO_DATABASE = "demo"
LIVE_DATABASE = "default"


def database_for(*, demo: bool) -> str:
    """Which database alias a run writes to.

    One line, and a function rather than an expression inside the command,
    because "did `--demo` keep this off the real database" is the question worth
    being able to ask in a test without opening a second database to ask it.
    """
    return DEMO_DATABASE if demo else LIVE_DATABASE
