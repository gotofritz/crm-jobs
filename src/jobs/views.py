"""The views — fetch and render, no business rules (plan 001 §6.3)."""

from django.http import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import render

from jobs.models import Opportunity


def healthz(_request: HttpRequest) -> HttpResponse:
    """Health check endpoint."""
    return HttpResponse(b"OK", status=200)


def board(request: HttpRequest) -> HttpResponse:
    """The whole app: one row per live opportunity, in §4.5 order (§7).

    Archived rows are not reachable from here beyond their count — not seeing
    them is the point of archiving (§6.5).
    """
    return render(
        request,
        "jobs/board.html",
        {
            "opportunities": Opportunity.objects.live().in_board_order(),
            "archived_count": Opportunity.objects.archived().count(),
        },
    )
