from django.http import HttpResponse
from django.http.request import HttpRequest


def healthz(request: HttpRequest) -> HttpResponse:
    return HttpResponse(b"OK", status=200)
