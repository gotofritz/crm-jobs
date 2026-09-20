"""Shared fixtures for the jobs tests."""

import datetime as dt
from pathlib import Path

import pytest

from jobs.demo import seed_demo
from jobs.models import Company, Contact, Opportunity, State

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The one exported opportunity the sheet's packing rules were validated against
# (plan 003 §4.1), and the one bad cell it still contains (§4.2) with the fix the
# cleanup checklist asks for.
SAMPLE_EXPORT = PROJECT_ROOT / "clasp" / "Crm-clasp-2 - Sheet2.csv"
STRAY_BLANK = "Scheduling interview\n\nMaya Richardson"
CLEANED = "Scheduling interview\nMaya Richardson"


@pytest.fixture(scope="session")
def project_root() -> Path:
    """The repository root, for the tests that read source files rather than objects."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def palette_css() -> str:
    """The one stylesheet that knows what a state looks like (§6.3)."""
    return (PROJECT_ROOT / "assets" / "states.css").read_text()


@pytest.fixture(scope="session")
def layout_css() -> str:
    """The stylesheet that owns the board's layout contract (§7)."""
    return (PROJECT_ROOT / "assets" / "board.css").read_text()


@pytest.fixture(scope="session")
def tailwind_input() -> str:
    """What `poe css` compiles, and the paths it resolves them from."""
    return (PROJECT_ROOT / "assets" / "app.css").read_text()


@pytest.fixture(scope="session")
def board_js() -> str:
    """The one script the board loads (§7)."""
    return (PROJECT_ROOT / "static" / "js" / "board.js").read_text()


@pytest.fixture(scope="session")
def compiled_css() -> str:
    """What Tailwind built from `assets/`, committed and actually served."""
    return (PROJECT_ROOT / "static" / "css" / "app.css").read_text()


@pytest.fixture
def company(db: None) -> Company:
    """A company with nothing filled in but its name."""
    return Company.objects.create(name="Acme")


@pytest.fixture
def contact(db: None) -> Contact:
    """A person to hang employments and steps off."""
    return Contact.objects.create(name="Ada Lovelace")


@pytest.fixture
def state(db: None) -> State:
    """The seeded state a new opportunity's first step lands in (§6.6)."""
    return State.objects.get(slug="unremarkable")


@pytest.fixture
def demo_board(db: None) -> list[Opportunity]:
    """The live rows `seed_demo` writes, in board order (`jobs/demo.py`).

    For the tests that want a full board rather than the two rows they built
    themselves. It lives in the test database, so it goes away with it.
    """
    seed_demo()
    return Opportunity.objects.live().in_board_order()


@pytest.fixture
def opportunity(company: Company) -> Opportunity:
    """A live opportunity at the fixture company."""
    return Opportunity.objects.create(
        company=company,
        title="Staff Software Engineer",
        date=dt.date(2026, 1, 5),
    )


@pytest.fixture(scope="session")
def sample_csv() -> str:
    """The committed sample export, stray blank line and all."""
    return SAMPLE_EXPORT.read_text()


@pytest.fixture(scope="session")
def cleaned_csv(sample_csv: str) -> str:
    """The same export with §4.2's one bad cell fixed, as the checklist says to."""
    return sample_csv.replace(STRAY_BLANK, CLEANED)
