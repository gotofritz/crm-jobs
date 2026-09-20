"""Root URL configuration.

The app owns its own routes (`jobs/urls.py`); this file mounts them at the root
and puts the admin behind `/admin/`, which is the CRUD backdoor and, until
search exists, the only way to look at an archived opportunity (plan 001 §6.5).

Reference: https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("jobs.urls")),
]
