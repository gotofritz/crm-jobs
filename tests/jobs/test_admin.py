"""The admin is the free CRUD backdoor while the real UI is built — plan 001 §6.9."""

import pytest
from django.contrib import admin
from django.db.models import Model
from django.test import Client

from jobs.models import (
    Company,
    Contact,
    Employment,
    Opportunity,
    Sector,
    Source,
    State,
    Step,
)


@pytest.mark.parametrize(
    "model",
    [Company, Contact, Employment, Opportunity, Sector, Source, State, Step],
)
def test_every_model_is_registered(model: type[Model]) -> None:
    """Every model is reachable, including the archive until search exists (§6.5)."""
    assert admin.site.is_registered(model)


def test_an_opportunity_and_its_first_step_are_created_together(
    admin_client: Client, company: Company, state: State
) -> None:
    """Creating an opportunity in the admin also creates its steps (§6.9)."""
    response = admin_client.post(
        "/admin/jobs/opportunity/add/",
        {
            "company": str(company.pk),
            "title": "Staff Software Engineer",
            "date": "2026-01-05",
            "comments": "",
            "steps-TOTAL_FORMS": "1",
            "steps-INITIAL_FORMS": "0",
            "steps-MIN_NUM_FORMS": "0",
            "steps-MAX_NUM_FORMS": "1000",
            "steps-0-state": str(state.pk),
            "steps-0-date": "2026-01-05",
            "steps-0-time": "",
            "steps-0-title": "Applied via site",
            "steps-0-comments": "",
        },
    )

    assert response.status_code == 302
    opportunity = Opportunity.objects.get(title="Staff Software Engineer")
    assert opportunity.steps.count() == 1
    assert opportunity.steps.get().state == state
