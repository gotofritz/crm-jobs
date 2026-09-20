"""Typing a name is how a picklist grows — plan 001 §6.9.

There are no management screens for companies, contacts, sources or sectors.
The form takes free text, `by_name` turns it into a row, and the first spelling
entered is the one later variants resolve to.
"""

import pytest

from jobs.forms import by_name
from jobs.models import Company, Contact, Sector, Source


@pytest.mark.usefixtures("db")
def test_an_unknown_name_is_created() -> None:
    """Typing a company that does not exist creates it (§6.9)."""
    company = by_name(Company, "Northwind Analytics")

    assert company is not None
    assert company.name == "Northwind Analytics"
    assert Company.objects.count() == 1


def test_a_known_name_is_reused(company: Company) -> None:
    """Typing a company that exists reuses it rather than creating a second one."""
    resolved = by_name(Company, "Acme")

    assert resolved == company
    assert Company.objects.count() == 1


@pytest.mark.usefixtures("db")
def test_a_differently_cased_name_is_the_same_row() -> None:
    """`FinTech` and `fintech` resolve to one `Sector` (§6.9).

    Both land on the `Fintech` the seed already shipped, which is the case worth
    covering: the picklist a fresh database starts with is what free text has to
    stop forking.
    """
    first = by_name(Sector, "FinTech")
    second = by_name(Sector, "fintech")

    assert first == second
    assert Sector.objects.filter(name__iexact="fintech").count() == 1


@pytest.mark.usefixtures("db")
def test_the_first_spelling_entered_wins() -> None:
    """A later variant matches the stored row; it does not rename it (§6.9)."""
    by_name(Sector, "PropTech")
    resolved = by_name(Sector, "PROPTECH")

    assert resolved is not None
    assert resolved.name == "PropTech"


@pytest.mark.usefixtures("db")
def test_stray_whitespace_is_collapsed() -> None:
    """`"  Acme   Corp "` is `"Acme Corp"`, so spacing cannot fork a picklist."""
    resolved = by_name(Company, "  Acme   Corp ")

    assert resolved is not None
    assert resolved.name == "Acme Corp"


@pytest.mark.usefixtures("db")
@pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
def test_a_blank_name_resolves_to_nothing(raw: str) -> None:
    """An optional field left empty creates no row — source and contact may be blank."""
    assert by_name(Source, raw) is None
    assert Source.objects.filter(name="").count() == 0


@pytest.mark.usefixtures("db")
def test_a_contact_with_a_repeated_name_is_reused() -> None:
    """Contact names are not unique in the model, but typing one still reuses it (§6.7)."""
    first = by_name(Contact, "Ada Lovelace")
    second = by_name(Contact, "ada lovelace")

    assert first == second
    assert Contact.objects.count() == 1
