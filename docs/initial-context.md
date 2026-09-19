# Architecture & Setup

## Development

### Initial Setup

After installation (see [README](../README.md)), create a superuser:

```bash
uv run poe superuser
```

This creates a login for Django admin at `/admin/`.

### Database

Development uses SQLite at `./db.sqlite3` (gitignored), at the repository root
rather than inside `src/`; `DJANGO_DB_PATH` moves it, and the VPS points it at
`/var/lib/crm-jobs/db.sqlite3`. The connection runs WAL with
`synchronous=NORMAL` and `transaction_mode=IMMEDIATE`, so a read can run while
a write is in flight and a write takes its lock up front rather than half way
through a transaction.

`migrate` also seeds the picklists — twelve states, five sources, eighteen
sectors — so a fresh checkout has a usable board without a fixture step.

### Settings and secrets

Nothing host-specific lives in the repo. `src/config/settings.py` reads it from
the environment through `src/config/env.py`, whose readers are deliberately
strict: `DJANGO_DEBUG=maybe` stops the process rather than quietly picking a
side, and a missing `DJANGO_SECRET_KEY` with `DEBUG` off stops it at boot
rather than on the first signed cookie.

| Variable | Default | Notes |
|----------|---------|-------|
| `DJANGO_DEBUG` | `true` | `1/true/yes/on` or `0/false/no/off` |
| `DJANGO_SECRET_KEY` | a dev key marked `django-insecure-` | required once `DEBUG` is off |
| `DJANGO_ALLOWED_HOSTS` | empty | comma separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | comma separated, with scheme |
| `DJANGO_HSTS_SECONDS` | `31536000` (one year) | ignored while `DEBUG` is on |
| `DJANGO_DB_PATH` | `./db.sqlite3` | `/var/lib/crm-jobs/db.sqlite3` on the VPS |

Secure cookies and HSTS follow `DEBUG`, so production is one switch rather than
six. `uv run poe qa` ends with `check-deploy`, which runs Django's deployment
checklist against production-shaped settings at `--fail-level WARNING`. CI runs
`poe qa`, so the checklist cannot go quietly red.

What is still outstanding from plan 001 phase 5 is WhiteNoise and
`collectstatic`; they wait for phase 3, when there are static files to serve.

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
src/config/       settings, environment readers, urls, wsgi
src/jobs/         the one app: models, ordering, admin, views, templates
tests/            mirrors src/, one directory per package
static/           vendored htmx, compiled tailwind css
deploy/           Caddyfile, systemd units, backup timer
docs/             plans, archive, this file
clasp/            retired Google Apps Script source, reference only
```

This is the one deviation from the layout in plan 001 §5, which put `config/`
and `jobs/` at the repository root.

Tests live in `tests/`, not beside the code the way `startapp` generates them.
Two trees rather than one means the wheel built from `src/` carries no test
code, and `--cov=src/` measures the application instead of measuring the tests
along with it. pytest runs with `--import-mode=importlib`, so `tests/jobs/` and
`tests/config/` need no `__init__.py` and two test modules may share a
basename. `ty` checks both trees, and `tests/conftest.py` holds the shared
fixtures.

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
  as data. `Group` stays an enum rather than a table, because code branches on
  the three buckets. Where they rank is a sort rule, so `GROUP_RANK` lives in
  `ordering.py` rather than beside the enum.

Deletion rules are deliberate: `Opportunity.company` and `Step.state` are
`PROTECT`, `source` and `contact` are `SET_NULL`, `Step.opportunity` and
`Employment` are `CASCADE`.

Every model is registered in the Django admin. That is the CRUD backdoor while
the real UI is built, the place duplicate contacts and companies get merged,
and — until search exists — the only way to look at archived opportunities.

### Ordering

`src/jobs/ordering.py` ports the sort rules of the retired GAS app (plan 001
§4.5) and is the one piece of real domain logic here. It defines two orders,
and they are not the same order:

- **Steps inside an opportunity** — by group rank descending, then by
  `date` + `time`: ascending for `ATTENTION` and `DUE`, descending for
  `COMPLETE`. The inversion is deliberate. With something pending, the oldest
  is the most urgent; with nothing pending, only the most recently touched is
  worth looking at (plan 001 §6.2).
- **Opportunities on the board** — keyed on the step that sort leaves at the
  front. An opportunity with no steps sorts first, then group rank descending,
  then the state's `sort_order` ascending, then the same inverted date rule.

The functions take steps, not querysets, so every rule is tested without a
database. `Opportunity.objects.live().in_board_order()` is the entry point. It
returns a list rather than a queryset, because the date tie-break flips on the
state's group and SQL cannot express that in one `ORDER BY`. It prefetches
`steps__state`, so the sort costs three queries however many rows there are,
and a test asserts that count. Archived rows have their own order,
`in_archive_order()`, most recently archived first (plan 001 §6.5).

Keeping `GROUP_RANK` here leaves `ordering.py` importing nothing from the
models at runtime: the dependency runs one way, models → ordering. A test
asserts the ranking covers every `Group`, so adding a group without deciding
where it ranks fails loudly.

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

`forms.py` arrives in phase 4; the rows above are the contract it is written
against.

### Deviations from AGENTS.md

- **`pydantic` is not used for models.** Django's ORM fills that role, and a
  second schema layer would duplicate validation for no gain. Pydantic stays
  available for anything outside the ORM, such as parsing config (plan 001 §5).
- **`django-types` is a dev dependency.** `ty` cannot see the attributes
  Django's metaclass adds at runtime, so without stubs every `objects` call is
  a type error. The package is stubs only — no runtime code, no Node. Reverse
  accessors it still cannot infer (`opportunity.steps` and friends) are
  declared under `if TYPE_CHECKING:` on the model that owns the far side.
- **Migrations are outside qa.** ruff, ty and coverage all skip
  `src/jobs/migrations/`: Django writes those files, so checking them yields
  nothing but rules to suppress. They are still run, and what they produce is
  tested — `test_seed.py` asserts the seeded picklists.
- **`wsgi.py` and `asgi.py` are outside coverage.** Four lines each, written by
  `startproject` and executed by gunicorn rather than imported by anything.
  Counting them as missed said nothing about the code.
- **One scoped lint ignore**, in `.ruff.toml` with the reason inline: `ARG001`
  in `src/jobs/conftest.py`, because a pytest fixture requested by argument
  name is never referenced.
- **One silenced Django check**, `security.W008`. It asks Django to redirect
  http to https. Caddy already does that one hop earlier, and Django repeating
  it would either achieve nothing or loop, unless Django were also told to
  trust a proxy header (plan 001 §5). `SECURE_SSL_REDIRECT` therefore stays
  `False`, and a test asserts the two halves stay in step.
