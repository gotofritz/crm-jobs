from django.http import HttpResponse
from django.test import Client


def test_healthz() -> None:
    client = Client()
    response: HttpResponse = client.get("/healthz")  # type: ignore[assignment]
    assert response.status_code == 200
    assert response.content == b"OK"
