"""`manage.py seed_demo` — fill the development board with something to look at."""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jobs.demo import seed_demo


class ProductionRefusedError(CommandError):
    """Refusal to write demo rows into a database that is not a development one."""

    def __init__(self) -> None:
        """Say why, since the command is about to stop over it."""
        super().__init__("seed_demo writes rows nobody asked for, so it needs DEBUG on")


class Command(BaseCommand):
    """Write the demo opportunities. `poe demo` rebuilds the database around this."""

    help = "Seed the development board with demo opportunities. Needs DEBUG on."

    def handle(self, *_args: Any, **_options: Any) -> None:
        """Refuse outside development, then seed."""
        if not settings.DEBUG:
            raise ProductionRefusedError

        self.stdout.write(f"Seeded {len(seed_demo())} demo opportunities.")
