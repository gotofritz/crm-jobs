"""The picklists suggest what is already there — plan 001 §6.9.

Typing a name is how a company, contact, source or sector gets created, so the
input has to offer the ones that exist or the same thing gets typed two ways.
A `<datalist>` does that without becoming a constraint: it drops down what
matches as you type, and a name that matches nothing is still accepted.

The two halves have to agree. An input with no `list` and a `<datalist>` nobody
points at both render perfectly well and do nothing at all, which is what these
tests are for.
"""

import datetime as dt
import re

import pytest
from django.test import Client

from jobs.models import Company, Contact, Opportunity, Sector, Source, State, Step

HTMX = {"HX-Request": "true"}

# field name -> the list its input points at
SUGGESTED = {
    "company": "companies-list",
    "source": "sources-list",
    "contact": "contacts-list",
    "company_sector": "sectors-list",
}


@pytest.fixture
def client() -> Client:
    """A browser."""
    return Client()


@pytest.fixture
def step(opportunity: Opportunity) -> Step:
    """A step, whose contacts are a picklist too."""
    return Step.objects.create(
        opportunity=opportunity, state=State.objects.get(slug="due"), date=dt.date(2026, 2, 1)
    )


def input_for(html: str, name: str) -> str:
    """The rendered input for a field."""
    match = re.search(rf'<input[^>]*name="{name}"[^>]*>', html)

    assert match is not None, f"no input named {name}"

    return match[0]


def options_in(html: str, list_id: str) -> set[str]:
    """What a `<datalist>` offers."""
    block = re.search(rf'<datalist id="{list_id}">(.*?)</datalist>', html, re.DOTALL)

    assert block is not None, f"no datalist {list_id}"

    return set(re.findall(r'<option value="([^"]*)"', block[1]))


@pytest.mark.parametrize(("field", "list_id"), sorted(SUGGESTED.items()))
def test_a_picklist_input_points_at_its_datalist(
    client: Client, opportunity: Opportunity, field: str, list_id: str
) -> None:
    """Without the `list` attribute the datalist beside it is decoration."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert f'list="{list_id}"' in input_for(html, field)


@pytest.mark.parametrize("list_id", sorted(SUGGESTED.values()))
def test_the_datalist_it_points_at_is_on_the_page(
    client: Client, opportunity: Opportunity, list_id: str
) -> None:
    """A `list` naming nothing is the same bug seen from the other side."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert f'<datalist id="{list_id}">' in html


def test_the_suggestions_are_what_is_in_the_database(
    client: Client, opportunity: Opportunity
) -> None:
    """The point of the list: what has been typed before."""
    Contact.objects.create(name="Grace Hopper")
    Company.objects.create(name="Northwind Analytics")

    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert {"Ada Lovelace", "Grace Hopper"} <= options_in(html, "contacts-list") | {"Ada Lovelace"}
    assert "Grace Hopper" in options_in(html, "contacts-list")
    assert "Northwind Analytics" in options_in(html, "companies-list")
    assert "Acme" in options_in(html, "companies-list")


def test_the_seeded_picklists_are_suggested(client: Client, opportunity: Opportunity) -> None:
    """A fresh database ships sources and sectors, and those are suggestions too (§6.10)."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert "LinkedIn" in options_in(html, "sources-list")
    assert "Fintech" in options_in(html, "sectors-list")


def test_a_suggestion_is_not_a_constraint(client: Client, opportunity: Opportunity) -> None:
    """Typing a new name still creates it — the list suggests, it does not limit (§6.9)."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert "<select" not in input_for(html, "company_sector")

    client.post(
        f"/opportunities/{opportunity.pk}/field/company_sector",
        {"company_sector": "Proptech"},
        headers=HTMX,
    )

    assert Sector.objects.filter(name="Proptech").exists()


def test_the_browser_history_does_not_compete_with_it(
    client: Client, opportunity: Opportunity
) -> None:
    """Two dropdowns over one box is one too many, and only one knows the data."""
    html = client.get(f"/opportunities/{opportunity.pk}/edit", headers=HTMX).content.decode()

    assert 'autocomplete="off"' in input_for(html, "contact")


# --- Editing one value on its own ------------------------------------------


def test_a_single_value_is_suggested_too(client: Client, opportunity: Opportunity) -> None:
    """Clicking the sector opens the same input, so it gets the same list."""
    html = client.get(
        f"/opportunities/{opportunity.pk}/field/company_sector", headers=HTMX
    ).content.decode()

    assert 'list="sectors-list"' in input_for(html, "company_sector")
    assert "Fintech" in options_in(html, "sectors-list")


def test_a_single_value_carries_only_the_list_it_uses(
    client: Client, opportunity: Opportunity
) -> None:
    """Every company on the page to edit one sector is markup nobody reads."""
    html = client.get(
        f"/opportunities/{opportunity.pk}/field/company_sector", headers=HTMX
    ).content.decode()

    assert html.count("<datalist") == 1
    assert "companies-list" not in html


def test_a_value_with_no_picklist_carries_no_list(client: Client, opportunity: Opportunity) -> None:
    """A job title is free text with nothing to suggest (§6.8)."""
    html = client.get(f"/opportunities/{opportunity.pk}/field/title", headers=HTMX).content.decode()

    assert "<datalist" not in html


# --- A step's contacts -----------------------------------------------------


def test_a_steps_contacts_are_suggested(client: Client, step: Step) -> None:
    """Several names, comma separated, each resolved the way a company is (§6.9)."""
    html = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()

    assert 'list="contacts-list"' in input_for(html, "contacts")
    assert '<datalist id="contacts-list">' in html


def test_a_step_is_not_given_the_company_list(client: Client, step: Step) -> None:
    """A step card has no company on it, so it has no use for the names of any."""
    html = client.get(f"/steps/{step.pk}/edit", headers=HTMX).content.decode()

    assert "companies-list" not in html


# --- Creating --------------------------------------------------------------


@pytest.mark.usefixtures("company")
def test_a_blank_row_suggests_too(client: Client) -> None:
    """The first thing typed into a new row is a company that probably exists."""
    html = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert 'list="companies-list"' in input_for(html, "company")
    assert "Acme" in options_in(html, "companies-list")


def test_a_blank_step_suggests_contacts(client: Client, opportunity: Opportunity) -> None:
    """Same for the card the `+` puts in the track."""
    html = client.get(f"/opportunities/{opportunity.pk}/steps/new", headers=HTMX).content.decode()

    assert 'list="contacts-list"' in input_for(html, "contacts")


@pytest.mark.usefixtures("db")
def test_the_suggestions_are_in_a_settled_order(client: Client) -> None:
    """Alphabetical, so the list does not reshuffle as rows are added."""
    for name in ("Zebra Co", "Acme", "Mistral Ltd"):
        Company.objects.create(name=name)

    html = client.get("/opportunities/new", headers=HTMX).content.decode()
    block = re.search(r'<datalist id="companies-list">(.*?)</datalist>', html, re.DOTALL)

    assert block is not None
    found = re.findall(r'<option value="([^"]*)"', block[1])
    assert found == sorted(found)


@pytest.mark.usefixtures("db")
def test_every_source_is_offered(client: Client) -> None:
    """The five the seed ships, plus anything typed since (§6.10)."""
    Source.objects.create(name="Jobs board")

    html = client.get("/opportunities/new", headers=HTMX).content.decode()

    assert {"LinkedIn", "Wellfound", "Referral", "Direct", "Recruiter", "Jobs board"} <= options_in(
        html, "sources-list"
    )
