from django.http import HttpResponse
from django.http.request import HttpRequest


def healthz(_request: HttpRequest) -> HttpResponse:
    """Health check endpoint."""
    return HttpResponse(b"OK", status=200)
