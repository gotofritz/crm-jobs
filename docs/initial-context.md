# Architecture & Setup

## Development

### Initial Setup

After installation (see [README](../README.md)), create a superuser:

```bash
uv run python manage.py createsuperuser
```

This creates a login for Django admin at `/admin/`.

### Database

Development uses SQLite at `./db.sqlite3` (gitignored). `migrate` also seeds
the picklists — twelve states, five sources, eighteen sectors — so a fresh
checkout has a usable board without a fixture step.

### Architecture

Django, server-rendered, with HTMX for partial swaps. No SPA, no npm, no JS
build step. SQLite is the only datastore.

```
browser ── HTTPS ──▶ Caddy (TLS + basic_auth) ──▶ gunicorn ──▶ Django
   :443                    127.0.0.1:8000                       │
                                                                ▼
                                            /var/lib/crm-jobs/db.sqlite3
```

Django serves its own static files through WhiteNoise, so Caddy needs no
static-file configuration. HTMX is vendored into `static/`, never loaded from
a CDN. Tailwind is compiled by the standalone CLI binary, which needs no Node.

Code lives under `src/`, which is on the path via `pythonpath` in
`pyproject.toml`:

```
src/config/       settings, urls, wsgi
src/jobs/         the one app: models, admin, views, templates
static/           vendored htmx, compiled tailwind css
deploy/           Caddyfile, systemd units, backup timer
docs/             plans, archive, this file
clasp/            retired Google Apps Script source, reference only
```

This is the one deviation from the layout in plan 001 §5, which put `config/`
and `jobs/` at the repository root.

### Data model

Seven tables plus one `TextChoices` enum, described in full in plan 001 §6:

- `Company`, `Contact`, `Source`, `Sector` — the entities that recur across
  opportunities. Everything on `Company` but the name is optional, because a
  company is usually created mid-flow.
- `Employment` — one row per stint, so a contact can move between companies
  without the old opportunity losing them. A `NULL` bound means open, not
  unknown-and-excluded; `Employment.objects.on(day)` reads it that way.
- `Opportunity` — one application, live while `archived_at` is `NULL`.
  `Opportunity.objects.live()` and `.archived()` are asked for explicitly;
  no manager filters archived rows away silently.
- `Step` — something that happened, in one `State`.
- `State` — the vocabulary (`slug`, `name`, `group`, `sort_order`), extensible
  as data. `Group` stays an enum with `GROUP_RANK` next to it, because adding
  a group means deciding where it ranks — a code change either way.

Deletion rules are deliberate: `Opportunity.company` and `Step.state` are
`PROTECT`, `source` and `contact` are `SET_NULL`, `Step.opportunity` and
`Employment` are `CASCADE`.

Every model is registered in the Django admin. That is the CRUD backdoor while
the real UI is built, the place duplicate contacts and companies get merged,
and — until search exists — the only way to look at archived opportunities.

### Boundaries

| Concern | Lives in | Never in |
|---------|----------|----------|
| Fields, relationships | `src/jobs/models.py` | views, templates |
| Sort/ordering rules | `src/jobs/ordering.py`, pure functions | views, templates, DB ordering hacks |
| Validation, coercion | `src/jobs/forms.py` | views, models' `save()` |
| Fetch and render | `src/jobs/views.py` | business rules |
| Markup, data attributes | templates | business rules |
| Colour, size, spacing | CSS | models, views, templates |

The model layer knows that a step has a state and that a state belongs to a
group. It never knows what either looks like: templates emit `data-state` and
`data-group`, and one stylesheet decides what those mean. A `State` therefore
has no colour field, and a test asserts it stays that way — if a hex value
reaches `models.py`, the design is wrong (plan 001 §6.3).

`ordering.py` and `forms.py` arrive in phases 2 and 4; the rows above are the
contract they are written against.

### Deviations from AGENTS.md

- **`pydantic` is not used for models.** Django's ORM fills that role, and a
  second schema layer would duplicate validation for no gain. Pydantic stays
  available for anything outside the ORM, such as parsing config (plan 001 §5).
- **`django-types` is a dev dependency.** `ty` cannot see the attributes
  Django's metaclass adds at runtime, so without stubs every `objects` call is
  a type error. The package is stubs only — no runtime code, no Node. Reverse
  accessors it still cannot infer (`opportunity.steps` and friends) are
  declared under `if TYPE_CHECKING:` on the model that owns the far side.
- **Two scoped lint ignores**, both in `.ruff.toml` with the reason inline:
  `RUF012` in `src/jobs/migrations/` because Django writes those files itself,
  and `ARG001` in `src/jobs/conftest.py` because a pytest fixture requested by
  name is never referenced.
