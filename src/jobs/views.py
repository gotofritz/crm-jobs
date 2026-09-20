"""The views — fetch and render, no business rules (plan 001 §6.3).

Two rules shape every mutation here.

A mutation answers with the row it changed, because that is the cheapest
correct swap; it answers with the whole board only when the change moved rows
about, which the sort in §4.5 can do from a single step (AGENTS.md, "Django").
`_order_of_the_board` is how that is decided — the order is read before and
after, and the two are compared.

And every route works without the script. htmx is an enhancement, exactly as
`board.js` is (§7): the same POST from a plain form redirects to the board, and
the same GET without htmx returns a whole page rather than a bare partial.
"""

from typing import Any

from django.db import models
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_htmx.middleware import HtmxDetails

from jobs.forms import NoteForm, OpportunityForm, StepForm
from jobs.models import Company, Contact, Note, Opportunity, Sector, Source, Step

# Every mutation response carries these two out of band: the header counts,
# which an archive changes, and an empty drawer, which closes the form.
EXTRAS = "jobs/_swap_extras.html"


class HtmxHttpRequest(HttpRequest):
    """`HttpRequest` plus what `HtmxMiddleware` puts on it at runtime.

    `request.htmx` is set by the middleware rather than declared on the class,
    so a type checker cannot see it. This is the annotation django-htmx
    documents for saying so, and it is the request type every view here takes.
    """

    htmx: HtmxDetails


def healthz(_request: HtmxHttpRequest) -> HttpResponse:
    """Health check endpoint."""
    return HttpResponse(b"OK", status=200)


# --- Shared plumbing -------------------------------------------------------


def _names(model: type[models.Model], /) -> list[str]:
    """The names a `<datalist>` suggests — what replaces a management screen (§6.9)."""
    return list(model._default_manager.order_by("name").values_list("name", flat=True))


# Which table stands behind each suggestion list. The ids are the ones
# `forms.suggesting` writes into the inputs.
SUGGESTIONS: dict[str, type[models.Model]] = {
    "companies-list": Company,
    "sources-list": Source,
    "sectors-list": Sector,
    "contacts-list": Contact,
}


def _datalists(form: Any) -> dict[str, list[str]]:
    """The suggestion lists this form's inputs actually point at.

    Read off the widgets rather than listed by hand, so an input can never name
    a `<datalist>` the page does not carry, and the page never carries one
    nothing points at. It also keeps a one-field edit from shipping every
    company on record to fill in a sector.
    """
    wanted = {
        widget.attrs["list"]
        for widget in (field.widget for field in form.fields.values())
        if "list" in widget.attrs
    }
    return {name: _names(SUGGESTIONS[name]) for name in sorted(wanted)}


def _counts() -> dict[str, int]:
    """What the header prints: how much is live, and how much is put away (§6.5)."""
    return {
        "live_count": Opportunity.objects.live().count(),
        "archived_count": Opportunity.objects.archived().count(),
    }


def _order_of_the_board() -> list[int]:
    """The live rows, in board order (§4.5), as the ids alone.

    Read before and after a mutation: if the two differ the board has to
    re-render, and if they match the changed row is swap enough.
    """
    return [row.pk for row in Opportunity.objects.live().in_board_order()]


def _board_context(*, new_pk: int | None = None) -> dict[str, Any]:
    """Everything the board template reads.

    `live_count` is the length of the list already in hand, not a second
    `COUNT(*)`: the board costs a fixed number of queries however many rows it
    has, and that is a property the suite asserts.
    """
    live = Opportunity.objects.live().in_board_order()
    return {
        "opportunities": live,
        "new_pk": new_pk,
        "live_count": len(live),
        "archived_count": Opportunity.objects.archived().count(),
    }


def _board_url(new_pk: int | None) -> str:
    """Where a scriptless POST lands: the board, pointed at the row it just made (§6.6)."""
    return "/" if new_pk is None else f"/?new={new_pk}"


def _board_swap(request: HtmxHttpRequest, *, new_pk: int | None = None) -> HttpResponse:
    """Re-render the whole board, retargeted off whichever row was clicked."""
    response = render(request, "jobs/_board_swap.html", _board_context(new_pk=new_pk))
    response["HX-Retarget"] = "#board"
    response["HX-Reswap"] = "outerHTML"
    return response


def _row_swap(request: HtmxHttpRequest, opportunity: Opportunity, **extra: Any) -> HttpResponse:
    """Re-render one row, which is what `hx-target="#opportunity-<id>"` expects (§7)."""
    fresh = Opportunity.objects.filter(pk=opportunity.pk).in_board_order()[0]
    response = render(request, "jobs/_row_swap.html", {"opportunity": fresh} | extra | _counts())
    # The click that asked for this may have come from a blank card inside the
    # row, so the row says where it goes rather than trusting the target.
    response["HX-Retarget"] = f"#opportunity-{fresh.pk}"
    response["HX-Reswap"] = "outerHTML"
    return response


def _row_gone(request: HtmxHttpRequest) -> HttpResponse:
    """Answer a delete or an archive: nothing to put where the row was (§7).

    The body holds the out-of-band extras only, so htmx has nothing left for the
    swap itself and takes the row out.
    """
    return render(request, EXTRAS, _counts())


def _after_change(
    request: HtmxHttpRequest,
    opportunity: Opportunity,
    order_before: list[int],
    *,
    new_pk: int | None = None,
) -> HttpResponse:
    """The row, or the board if the change moved rows about (AGENTS.md, "Django")."""
    if not request.htmx:
        return redirect(_board_url(new_pk))
    if _order_of_the_board() != order_before:
        return _board_swap(request, new_pk=new_pk)
    return _row_swap(request, opportunity)


def _blank(request: HtmxHttpRequest, template: str, **context: Any) -> HttpResponse:
    """A blank card, in edit mode, for something that does not exist yet.

    The same markup an edit produces, because there is one way a card looks
    while it is being filled in. Without htmx it gets a page to stand on, the
    way every other partial does (§7).
    """
    full = context | {"datalists": _datalists(context["form"])}
    if request.htmx:
        return render(request, template, full)
    return render(request, "jobs/new_page.html", full | {"blank": template})


@require_GET
def new_cancel(_request: HtmxHttpRequest) -> HttpResponse:
    """Nothing was created, so cancelling a blank card is taking it away."""
    return HttpResponse(b"")


# --- The board -------------------------------------------------------------


@require_GET
def board(request: HtmxHttpRequest) -> HttpResponse:
    """The whole app: one row per live opportunity, in §4.5 order (§7).

    Archived rows are not reachable from here beyond their count — not seeing
    them is the point of archiving (§6.5). `?new=<id>` marks a row the previous
    request created, so the highlight survives a scriptless page load (§6.6).
    """
    raw = request.GET.get("new", "")
    return render(
        request, "jobs/board.html", _board_context(new_pk=int(raw) if raw.isdigit() else None)
    )


# --- Opportunities ---------------------------------------------------------


@require_GET
def opportunity_new(request: HtmxHttpRequest) -> HttpResponse:
    """The empty opportunity form (§7)."""
    return _blank(request, "jobs/_new_opportunity_row.html", form=OpportunityForm())


@require_POST
def opportunity_create(request: HtmxHttpRequest) -> HttpResponse:
    """Create an opportunity and, with it, its first step (§4.4)."""
    order_before = _order_of_the_board()
    form = OpportunityForm(data=request.POST)
    if not form.is_valid():
        return _blank(request, "jobs/_new_opportunity_row.html", form=form)

    opportunity = form.save()
    opportunity.add_first_step()
    return _after_change(request, opportunity, order_before, new_pk=opportunity.pk)


@require_POST
def opportunity_delete(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """Remove an opportunity and its steps and notes with it (§7)."""
    get_object_or_404(Opportunity, pk=pk).delete()
    return _row_gone(request) if request.htmx else redirect("/")


# --- The archive -----------------------------------------------------------


@require_POST
def opportunity_archive(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """One timestamp. That is the whole mechanism (§6.5)."""
    opportunity = get_object_or_404(Opportunity, pk=pk)
    opportunity.archived_at = timezone.now()
    opportunity.save(update_fields=["archived_at"])
    return _row_gone(request) if request.htmx else redirect("/")


@require_POST
def opportunity_unarchive(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """Clear the timestamp and the row is live again (§6.5).

    The board re-renders rather than the row: the row is not on the page to be
    swapped, because the board shows live opportunities only.
    """
    opportunity = get_object_or_404(Opportunity, pk=pk)
    opportunity.archived_at = None
    opportunity.save(update_fields=["archived_at"])
    return _board_swap(request) if request.htmx else redirect("/")


@require_POST
def archive_live(request: HtmxHttpRequest) -> HttpResponse:
    """The "I got a job" action, at the end of a burst (§6.5).

    Already-archived rows keep the timestamp that says which burst they were,
    so only the live ones are touched.
    """
    Opportunity.objects.live().update(archived_at=timezone.now())
    return _board_swap(request) if request.htmx else redirect("/")


# --- Notes -----------------------------------------------------------------


@require_GET
def note_new(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """The empty note form, opened on an opportunity."""
    opportunity = get_object_or_404(Opportunity, pk=pk)
    return _row_swap(request, opportunity, new_note_form=NoteForm(opportunity=opportunity))


@require_POST
def note_create(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """Write a note on an opportunity. Notes do not affect the sort (§4.5)."""
    opportunity = get_object_or_404(Opportunity, pk=pk)
    order_before = _order_of_the_board()
    form = NoteForm(data=request.POST, opportunity=opportunity)
    if not form.is_valid():
        return _row_swap(request, opportunity, new_note_form=form)

    form.save()
    return _after_change(request, opportunity, order_before)


@require_POST
def note_delete(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """Remove one note. The row stays, so it is re-rendered without it."""
    note = get_object_or_404(Note, pk=pk)
    opportunity = note.opportunity
    note.delete()
    return _row_swap(request, opportunity) if request.htmx else redirect("/")


# --- Editing a value in place ---------------------------------------------


# The three models a value on the board can belong to, and how to build the
# form for one of their fields. `EDITABLE` is what says which fields those are.
# kind in the URL -> the model, its form, and the partial that prints one of
# its values. The last is spelled out rather than derived from the first: the
# plural of "opportunity" is not the plural of "step".
FIELD_FORMS: dict[str, tuple[type[models.Model], Any, str]] = {
    "opportunities": (Opportunity, OpportunityForm, "jobs/_opportunity_value.html"),
    "steps": (Step, StepForm, "jobs/_step_value.html"),
    "notes": (Note, NoteForm, "jobs/_note_value.html"),
}


def _field_form(obj: Any, field: str, data: Any = None) -> Any:
    """The narrowed form for one value, or 404 if that value is not editable.

    The whitelist lives in `forms.EDITABLE`, so naming `archived_at` in a URL
    gets a 404 rather than a way round the archive action (§6.5).
    """
    form_class = FIELD_FORMS[_kind_of(obj)][1]
    kwargs: dict[str, Any] = {"instance": obj, "only": field, "data": data}
    if form_class is not OpportunityForm:
        kwargs["opportunity"] = obj if isinstance(obj, Opportunity) else obj.opportunity
    try:
        return form_class(**kwargs)
    except KeyError as unlisted:
        raise Http404(str(unlisted)) from unlisted


def _kind_of(obj: Any) -> str:
    """The URL segment a model is reached under."""
    return next(kind for kind, (model, *_) in FIELD_FORMS.items() if isinstance(obj, model))


def _value_context(obj: Any, field: str) -> dict[str, Any]:
    """What the display partial and the input partial both need."""
    kind = _kind_of(obj)
    owner = obj if isinstance(obj, Opportunity) else obj.opportunity
    return {
        "field": field,
        "url": f"/{kind}/{obj.pk}/field/{field}",
        "opportunity": owner,
        "step": obj if isinstance(obj, Step) else None,
        "note": obj if isinstance(obj, Note) else None,
    }


def _value(request: HtmxHttpRequest, obj: Any, field: str) -> HttpResponse:
    """Render the value itself — what a save or a cancel puts back."""
    return render(request, FIELD_FORMS[_kind_of(obj)][2], _value_context(obj, field))


def _input(request: HtmxHttpRequest, obj: Any, field: str, form: Any) -> HttpResponse:
    """Render the input that replaced the value."""
    context = _value_context(obj, field) | {"form": form, "datalists": _datalists(form)}
    template = "jobs/_field_form.html" if request.htmx else "jobs/field_page.html"
    return render(request, template, context)


def _fetch(kind: str, pk: int) -> Any:
    """The row a field URL names, or 404."""
    if kind not in FIELD_FORMS:
        raise Http404(kind)
    return get_object_or_404(FIELD_FORMS[kind][0], pk=pk)


@require_http_methods(["GET", "POST"])
def field(request: HtmxHttpRequest, kind: str, pk: int, field: str) -> HttpResponse:
    """One value: `GET` opens it for editing, `POST` saves it.

    The same URL for both, because they are the same thing seen twice — the
    value is what a `GET` replaces and what a `POST` puts back.

    A save re-renders the whole board instead when the change moved rows about,
    which a step's state or date can do (§4.5), and the row when the value
    belongs to a step. The value alone is swap enough for everything else.
    """
    obj = _fetch(kind, pk)
    if request.method == "GET":
        return _input(request, obj, field, _field_form(obj, field))

    order_before = _order_of_the_board()
    form = _field_form(obj, field, data=request.POST)
    if not form.is_valid():
        return _input(request, obj, field, form)

    saved = form.save()
    if not request.htmx:
        return redirect("/")
    if _order_of_the_board() != order_before:
        return _board_swap(request)
    if isinstance(saved, Step):
        # A step's card carries `data-state`, which is what CSS colours it by
        # (§6.3), and its place in the track comes from that state's group
        # (§4.5). Neither is inside the value, so swapping the value alone
        # leaves a card the wrong colour, in the wrong place, until the page is
        # reloaded. The row is the smallest thing that is certainly right.
        return _row_swap(request, saved.opportunity)
    return _value(request, saved, field)


@require_GET
def field_cancel(request: HtmxHttpRequest, kind: str, pk: int, field: str) -> HttpResponse:
    """Give the value back untouched — what Escape asks for."""
    obj = _fetch(kind, pk)
    _field_form(obj, field)  # 404s an unlisted field here too
    return _value(request, obj, field)


# --- Editing a whole card ---------------------------------------------------


def _card(request: HtmxHttpRequest, obj: Any, form: Any = None) -> HttpResponse:
    """Re-render the row, with one of its cards in edit mode if `form` is given.

    The row rather than the card, even though it is a card being edited. Edit,
    Done and Cancel all swap `#opportunity-<id>`, so whatever Edit leaves on the
    page has to carry that id or the next click has nothing to aim at. It is
    also what keeps the steps and the ad on screen while the summary is open.
    """
    owner = obj if isinstance(obj, Opportunity) else obj.opportunity
    if form is None:
        return _row_swap(request, owner)

    # Which card is open. A step names itself, so the other cards in the track
    # render as usual.
    opened = {"editing_step_pk": obj.pk} if isinstance(obj, Step) else {"editing": True}
    return _row_swap(request, owner, form=form, datalists=_datalists(form), **opened)


@require_http_methods(["GET", "POST"])
def card_edit(request: HtmxHttpRequest, kind: str, pk: int) -> HttpResponse:
    """Open a whole card for editing, and save it.

    A single value commits on blur, because there is only one of it. A card
    cannot: the fields are filled in together, so they are submitted together,
    and Done is the submit.

    This is also the only way to reach a field that is empty, since an empty
    field is not on the card at all.
    """
    obj = _fetch(kind, pk)
    if isinstance(obj, Note):
        # A note has one field, which is the note, and clicking it edits it.
        # There is nothing for a card mode to open that a click does not.
        raise Http404(kind)

    form_class = FIELD_FORMS[kind][1]
    kwargs: dict[str, Any] = {"instance": obj}
    if form_class is not OpportunityForm:
        kwargs["opportunity"] = obj.opportunity

    if request.method == "GET":
        return _card(request, obj, form_class(**kwargs))

    order_before = _order_of_the_board()
    form = form_class(data=request.POST, **kwargs)
    if not form.is_valid():
        return _card(request, obj, form)

    saved = form.save()
    if not request.htmx:
        return redirect("/")
    if _order_of_the_board() != order_before:
        return _board_swap(request)
    return _card(request, saved)


# --- Steps -----------------------------------------------------------------


@require_GET
def step_new(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """The empty step form, opened on an opportunity (§7)."""
    opportunity = get_object_or_404(Opportunity, pk=pk)
    return _blank(
        request,
        "jobs/_new_step_card.html",
        form=StepForm(opportunity=opportunity),
        opportunity=opportunity,
    )


@require_POST
def step_create(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """Add a step. A new step is the commonest thing that re-sorts the board (§4.5)."""
    opportunity = get_object_or_404(Opportunity, pk=pk)
    order_before = _order_of_the_board()
    form = StepForm(data=request.POST, opportunity=opportunity)
    if not form.is_valid():
        return _blank(request, "jobs/_new_step_card.html", form=form, opportunity=opportunity)

    form.save()
    return _after_change(request, opportunity, order_before)


@require_POST
def step_delete(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """Remove one step. The opportunity stays, so its row comes back (§7)."""
    step = get_object_or_404(Step, pk=pk)
    opportunity = step.opportunity
    order_before = _order_of_the_board()
    step.delete()
    return _after_change(request, opportunity, order_before)
