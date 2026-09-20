"""HTMX is vendored and switched on — plan 001 §5, §7.

The board already ships one hand-written script; htmx is the second, and the
rule is the same for both: it comes out of `static/`, never a CDN (AGENTS.md,
"Frontend"). `django-htmx` is what gives a view `request.htmx`, which is how a
mutation decides between a partial and a whole page.
"""

from typing import cast

import pytest
from django.conf import settings
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django_htmx.middleware import HtmxMiddleware

from jobs.views import HtmxHttpRequest


def test_htmx_is_vendored(project_root) -> None:
    """The library is a file in the repository, not a fetch at page load."""
    assert (project_root / "static" / "js" / "htmx.min.js").exists()


@pytest.mark.usefixtures("db")
def test_the_board_loads_htmx_from_static() -> None:
    """The page asks for the vendored copy."""
    body = Client().get("/").content.decode()

    assert "js/htmx.min.js" in body


@pytest.mark.usefixtures("db")
def test_the_board_loads_no_script_from_a_cdn() -> None:
    """No `src` on the page points off-site (AGENTS.md, "Frontend")."""
    body = Client().get("/").content.decode()

    assert "//unpkg.com" not in body
    assert "//cdn." not in body
    assert "//cdnjs." not in body


def test_django_htmx_is_installed() -> None:
    """The app supplies the template tag that keeps the debug headers honest."""
    assert "django_htmx" in settings.INSTALLED_APPS


def test_requests_carry_an_htmx_flag() -> None:
    """`request.htmx` is what a view reads to choose partial over full (§7)."""
    request = cast("HtmxHttpRequest", RequestFactory().get("/", headers={"hx-request": "true"}))
    HtmxMiddleware(lambda _request: HttpResponse())(request)

    assert request.htmx
