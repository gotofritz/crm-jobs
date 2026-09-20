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
| `DJANGO_DB_PATH` | `./db.sqlite3` | `/var/lib/crm-jobs/db.sqlite3` on the VPS; `poe demo` pins it to `./demo.sqlite3` |

Secure cookies and HSTS follow `DEBUG`, so production is one switch rather than
six. `uv run poe qa` ends with `check-deploy`, which runs Django's deployment
checklist against production-shaped settings at `--fail-level WARNING`. CI runs
`poe qa`, so the checklist cannot go quietly red.

### Static files

There is no Node and no `package.json`. Tailwind is the standalone CLI binary,
which `uv run poe tailwind-install` fetches into `.tailwind/` at a pinned
version; `uv run poe dev` fetches it if it is missing and then runs it in watch
mode beside `runserver`.

```
assets/            app.css (Tailwind input), board.css, states.css — the source
static/css/app.css the compiled stylesheet, committed, and what is served
static/js/board.js the one hand-written script, served as written
staticfiles/       what collectstatic writes on deploy; not in the repository
```

Paths inside `assets/app.css` are relative to that file — `@import "./board.css"`,
`@source "../src/jobs/templates"` — not root-relative. The root-relative import
rule in AGENTS.md is about Python, and CSS has no notion of a project root: a
root-relative `@import` fails the build outright (`Can't resolve
'/assets/board.css'`), and a root-relative `@source` is worse, because it builds
without complaint and scans nothing, so a utility used in a template would
quietly never reach the stylesheet. A test pins both forms.

Every task that writes the compiled file passes `--minify`, `poe css` and the
watch inside `poe serve` alike. They disagreed for a while, so whichever ran
last decided whether the committed artifact was one line or four hundred, and
every diff carried the difference. A test now fails if it arrives unminified.

The compiled file is committed so that neither CI nor the deploy needs the
binary — deploy still touches code only. That makes it possible for it to go
stale, so a test compares the palette in `assets/states.css` with the palette in
`static/css/app.css`: editing a colour without running `uv run poe css` fails
the suite rather than the board.

WhiteNoise serves `STATIC_ROOT`, directly after `SecurityMiddleware`, so Caddy
needs no static-file configuration. The storage backend is
`CompressedStaticFilesStorage` rather than the manifest variant: hashed
filenames would make every rendered `{% static %}` tag depend on `collectstatic`
having run first, which means the test suite and any `DEBUG=False` run would
need a build step before they could render a page. One page behind `basic_auth`
gains little from far-future caching; the gzip and brotli copies are the part
worth having.

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
assets/           hand-written css and the tailwind input, compiled from here
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

Nine tables plus one `TextChoices` enum, described in full in plan 001 §6:

- `Company`, `Contact`, `Source`, `Sector` — the entities that recur across
  opportunities. Everything on `Company` but the name is optional, because a
  company is usually created mid-flow.
- `Employment` — one row per stint, so a contact can move between companies
  without the old opportunity losing them. A `NULL` bound means open, not
  unknown-and-excluded; `Employment.objects.on(day)` reads it that way.
- `Opportunity` — one application, live while `archived_at` is `NULL`.
  `Opportunity.objects.live()` and `.archived()` are asked for explicitly;
  no manager filters archived rows away silently. `job_description` holds the
  pasted ad and nothing else; remarks about the application are `Note` rows.
- `Note` — a remark written on an opportunity, "not sure about this" and why.
  A row rather than a line of prose, so each one is dated, read newest first,
  and removable on its own. `created_at` is a `default`, not `auto_now_add`:
  the latter is unwritable, and the demo seed dates its notes by hand so a
  re-run cannot reorder them.
- `Step` — something that happened, in one `State`.
- `State` — the vocabulary (`slug`, `name`, `group`, `sort_order`), extensible
  as data. `slug` is the key: it is what the code looks up and what the
  stylesheet hooks on, which leaves `name` free to be the words printed on a
  card. `UNREMARKABLE`'s name is empty, so its card carries the step and no
  label (plan 001 §6.1). `Group` stays an enum rather than a table, because code
  branches on the three buckets. Where they rank is a sort rule, so `GROUP_RANK`
  lives in `ordering.py` rather than beside the enum.

Deletion rules are deliberate: `Opportunity.company` and `Step.state` are
`PROTECT`, `source` and `contact` are `SET_NULL`, and `Step.opportunity`,
`Note.opportunity` and `Employment` are `CASCADE`.

Every model is registered in the Django admin. That is the CRUD backdoor while
the real UI is built, the place duplicate contacts and companies get merged,
and — until search exists — the only way to look at archived opportunities.

### Demo data

`migrate` seeds picklists and nothing else. Opportunities are the user's data, so
they are never written behind their back. `src/jobs/demo.py` holds a board worth
looking at — every group represented, one row with no steps, one archived, five
with a job ad long enough to need a description row, and notes covering all four
cases the summary card renders: none, two, more than two, and one long enough to
be clamped on its own.

```bash
uv run poe demo   # rebuild demo.sqlite3 from scratch and serve it
uv run poe dev    # db.sqlite3, your own rows, untouched
```

Two databases, and `poe demo` owns one of them outright: it deletes
`demo.sqlite3`, migrates it, seeds it and runs the server against it, so it is a
reset rather than an accumulation and nothing needs undoing. `DJANGO_DB_PATH` is
pinned for that task rather than defaulted, because a task that deletes a file by
name must not be pointed somewhere else. `manage.py seed_demo` also refuses to
run with `DEBUG` off, so it cannot reach the VPS.

`tests/conftest.py` exposes the same rows as the `demo_board` fixture, for tests
that want a full board rather than the two rows they built themselves. That is
not the same database, and it cannot be: Django runs SQLite tests against
`file:memorydb_default?mode=memory&cache=shared`, which exists only inside the
pytest process and only for the length of the run. `demo.sqlite3` is the
file-backed equivalent for a browser to look at.

### Ordering

`src/jobs/ordering.py` ports the sort rules of the retired GAS app (plan 001
§4.5) and is the one piece of real domain logic here. It defines three orders,
and no two of them are the same order:

- **Steps inside an opportunity** — by group rank descending, then by
  `date` + `time`: ascending for `ATTENTION` and `DUE`, descending for
  `COMPLETE`. The inversion is deliberate. With something pending, the oldest
  is the most urgent; with nothing pending, only the most recently touched is
  worth looking at (plan 001 §6.2).
- **Opportunities on the board** — keyed on the step that sort leaves at the
  front. An opportunity with no steps sorts first, then group rank descending,
  then the state's `sort_order` ascending, then the same inverted date rule.
- **Notes inside an opportunity** — newest first, the row's own id breaking a
  tie. The simple one, and not a port: the GAS app had no notes.

The functions take steps, not querysets, so every rule is tested without a
database. `Opportunity.objects.live().in_board_order()` is the entry point. It
returns a list rather than a queryset, because the date tie-break flips on the
state's group and SQL cannot express that in one `ORDER BY`. It prefetches
`steps__state` and the notes, and joins the company, source and contact the
summary card needs, so the sort costs four queries however many rows there are,
and a test asserts that count. Archived rows have their own order,
`in_archive_order()`, most recently archived first (plan 001 §6.5).

Keeping `GROUP_RANK` here leaves `ordering.py` importing nothing from the
models at runtime: the dependency runs one way, models → ordering. A test
asserts the ranking covers every `Group`, so adding a group without deciding
where it ranks fails loudly.

### The board

`GET /` is the whole application. It renders one row per live opportunity in
`in_board_order()`, with the archived count in the header and nothing else about
the archive — not seeing archived rows is the point of archiving (plan 001 §6.5).

```
---------------------------------------------------
| SUMMARY | | STEP 3 | STEP 2 | STEP 1 |          |
|         | |<------- scrolls ------------------->|
---------------------------------------------------
| > Job description                               |
---------------------------------------------------
   ^ fixed        ^ newest first, oldest right
```

A row is two blocks, and a third when there is an ad to show. The summary is one
and holds its place by being there; the steps sit in a block of their own,
holding a track and an arrow either side of it. The track is the scroller, so a long-running opportunity does not drag the
page sideways or its neighbours with it. Making the row itself scroll instead —
which is what the first cut did — runs the scrollbar under the summary card too.
`min-width: 0` on the track is load-bearing: a flex item defaults to
`min-width: auto`, so without it the track sizes to its steps and pushes the row
wide rather than scrolling. `tests/jobs/test_layout.py` asserts both against the
stylesheet.

A row sits on a tray of its own — one background under both of its lines. That
is what says an opened job description belongs to the opportunity above it
rather than the one below; without it the ad is a bar floating between two rows
and which owns it is a guess. Two spacings carry the grouping: `--board-gap`
between the blocks inside a row, `--row-spacing` between rows, and the second
has to be the larger or the tray groups nothing. The page is the darker of the
two colours so the tray reads against it — tinting the tray instead would put it
among the pale end of the state palette, where UNREMARKABLE is `#f5f5f5` and
GHOSTED `#e0e0e0`. The fill is faint by design, so the edge is what carries the
grouping: 1px solid in `--tray-rule`, `#444444`, darker than the `#d4d4d4` a
card's edge uses because the two do different jobs — a card's rule separates two
things sitting on one tray, the tray's separates the rows. It is not dotted: a
1px dotted line is never read as dots, only as a fainter version of the same
line, which is the opposite of what the edge is for. It is not dashed either,
and a test holds that: GHOSTED wears `border-style: dashed` as its second
channel (plan 001 §6.4), so a dashed tray would be that signal again where it
means nothing.

A row is one height all the way across: it stretches its two blocks, the steps
block stretches the track, and the track stretches the cards, so the summary and
the steps end level however much more one of them has to say. Centring anywhere
along that chain leaves the steps shrinkwrapped to their own content.

What is hidden is the scrollbar, not the scrolling. A row with more steps than
fit grows an arrow at each end of its track, which moves it a card at a time; a
row whose steps already fit grows neither. The wheel, the trackpad and the
keyboard still scroll it, and the arrows follow, because on a laptop they read
the scroll position rather than a count of clicks — an index would go stale the
moment the trackpad was used.

The pasted job ad — 1870 characters in the sample export — is the row's third
block rather than something inside the summary card. The row is
`flex-wrap: wrap` and the block is `flex: 0 0 100%`, so it lands on a line of
its own underneath rather than squeezing in beside the other two and shrinking
both. Its body is laid out in `columns: 22rem` — the block is as wide as the
board, and one measure that wide is unreadable. Giving `columns` a width rather
than a count leaves the number of them to the viewport instead of a breakpoint.

Where the control for it lives depends on the width, and on whether the script
ran. The block is a native `<details>` with its own bar, which is what a browser
running no JavaScript gets at either width. Once the script runs, a laptop hides
that bar *and* the closed block — the row shows nothing at all until it is asked
for — and a `Job description` button in the summary card opens it instead. A
phone keeps the bar, because the summary card it would live in is itself
collapsed to two lines there, so a control inside it would be a tap out of
reach. Both controls drive the same element, and a delegated `toggle` listener
writes `aria-expanded` back from it rather than from a count of clicks.

The summary card carries the notes too: a bullet list in `ordered_notes`
order, newest at the top. The stylesheet clamps it to the first two notes or
four lines, whichever bites first — `nth-child(n + 3)` for the one limit and a
`max-height` for the other, since a single long note reaches four lines before a
third note does. Both are scoped to `.has-js`, because the toggle that puts the
rest back is the script's.

On a phone the row stacks instead:

```
-------------------------------------
| Staff Backend Engineer          › |   <- tap to expand downwards
| Northwind Analytics               |
-------------------------------------
| ‹ |   STEP 2 (one at a time)  | › |
-------------------------------------
```

The summary spans the viewport and collapses to the two lines that identify the
row; the steps become one card at a time with an arrow either side, and the
track stops scrolling so nothing is swiped sideways or left half visible. The
job description is one cell under those, `columns: 1`, opening downwards —
two columns at 30rem is two columns an inch wide.

The arrows behave differently at the two widths, for a reason worth keeping. A
laptop card is a fixed width, so an arrow can leave without moving anything: it
shows only while it has somewhere to go. A phone card is the width of the track,
so hiding an arrow would resize the card under the reader's thumb — there the
ends grey out instead, and only a row with nothing to page through loses them.

Templates live in `src/jobs/templates/jobs/`, partials prefixed `_`:
`board.html` includes `_opportunity_row.html`, which is the summary card, a
`.opportunity__steps` block holding the arrows and a `.opportunity__track` with
one `_step_card.html` per step, and `_job_description.html` when the opportunity
has an ad. The track is there whether or not it has steps in it yet, because
phase 4 swaps into it.

Notes are read-only on the board. Adding and removing one is the admin's job
until phase 4 brings the mutation routes and the `+` and `−` controls with
them.

### The one script

`static/js/board.js` is the only hand-written JavaScript in the project: about
two hundred lines, vendored, deferred, no build step and no npm. It collapses the
summaries, drives the step arrows and clamps the notes, all of which need state
that CSS cannot hold on its own.

The notes clamp is the one measured decision in it. A third note is arithmetic,
but four lines is a height the browser works out, so the script collapses the
list, asks whether anything is left over, and only then takes `hidden` off the
toggle. A collapsed summary card has no height to measure, so a phone re-runs
that the moment the card is opened rather than at load.

Everything in it is an enhancement. The markup ships with every summary expanded
(`aria-expanded="true"`, no `data-collapsed`) and the track scrollable, and the
phone rules that take the scrolling away are scoped to `.has-js`, a class the
script adds to `<html>`. A browser that never runs it gets the laptop board at
phone width, which is usable rather than broken.

It is wired by one delegated `click` listener on the document rather than per
element, so rows HTMX swaps in during phase 4 are live without re-running
anything. There is no JavaScript test runner and no npm to add one, so
`tests/jobs/test_progressive_enhancement.py` checks the contract instead: it
reads the script, collects every `[data-…]` hook it selects on, and fails if one
is missing from the rendered board. Renaming a hook in one file and not the
other is otherwise silent. Step cards carry `data-state` and
`data-group` and nothing else about appearance; `assets/states.css` is the only
file that decides what those mean.

Ordering does not happen in the template. `Opportunity.ordered_steps` reads the
rows `in_board_order()` already prefetched and hands them over sorted, and
`ordered_notes` does the same for the notes, so the whole board costs five
queries — opportunities, steps, states, notes and the archived count — however
many rows it has, and a test asserts that.

The palette itself is checked rather than trusted: `tests/jobs/test_palette.py`
reads the stylesheet, measures every pair against WCAG AA for body text, and
asserts each ratio matches the one plan 001 §6.4 publishes. A separate test
fails if a hex value appears in any `.py` or `.html` file under `src/`.

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
against. Templates carry semantic class names and data attributes only — never
Tailwind utilities, because a utility class in a template is spacing and colour
in a template.

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
