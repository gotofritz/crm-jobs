"""The app's routes — plan 001 §7, as in-place editing rather than a panel.

§7 described a drawer because the GAS app had a sidebar, which was the only
thing a spreadsheet could offer. htmx can do better: a value on the board is a
link, following it swaps that value for an input, and saving swaps the value
back. So there is no edit route per object — there is one per *field*, and the
field is named in the URL and checked against the whitelist in `forms.EDITABLE`.

The drawer survives for creating only, because a row that does not exist yet
has nothing to click on.

`archive-live` is matched before the `<int:pk>` routes by virtue of not being an
integer, so the two cannot collide.
"""

from django.urls import path

from jobs import views

urlpatterns = [
    path("", views.board, name="board"),
    path("healthz", views.healthz, name="healthz"),
    # Creating — the three routes the drawer is still for
    path("new/cancel", views.new_cancel, name="new-cancel"),
    path("opportunities/new", views.opportunity_new, name="opportunity-new"),
    path("opportunities/", views.opportunity_create, name="opportunity-create"),
    path("opportunities/<int:pk>/notes/new", views.note_new, name="note-new"),
    path("opportunities/<int:pk>/notes/", views.note_create, name="note-create"),
    path("opportunities/<int:pk>/steps/new", views.step_new, name="step-new"),
    path("opportunities/<int:pk>/steps/", views.step_create, name="step-create"),
    # Editing one value in place: open it, save it, or put it back
    path("<str:kind>/<int:pk>/edit", views.card_edit, name="card-edit"),
    path("<str:kind>/<int:pk>/field/<str:field>", views.field, name="field"),
    path("<str:kind>/<int:pk>/field/<str:field>/cancel", views.field_cancel, name="field-cancel"),
    # Removing
    path("opportunities/<int:pk>/delete", views.opportunity_delete, name="opportunity-delete"),
    path("notes/<int:pk>/delete", views.note_delete, name="note-delete"),
    path("steps/<int:pk>/delete", views.step_delete, name="step-delete"),
    # The archive (§6.5)
    path("opportunities/archive-live", views.archive_live, name="archive-live"),
    path("opportunities/<int:pk>/archive", views.opportunity_archive, name="opportunity-archive"),
    path(
        "opportunities/<int:pk>/unarchive",
        views.opportunity_unarchive,
        name="opportunity-unarchive",
    ),
]
