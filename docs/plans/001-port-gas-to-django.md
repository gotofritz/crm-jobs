# 001 — Port CRM from Google Apps Script to a self-hosted Django app

Status: proposed
Date: 2026-09-17
Supersedes: the Google Apps Script app in `clasp/`

## 1. Goal

Replace the spreadsheet-backed Google Apps Script CRM with a small
Django app that:

- runs locally with one command, no Google account involved
- stores data in SQLite
- is reachable from any browser over HTTPS at a domain I own
- keeps the horizontal "summary card + steps pushed rightwards" layout
- deploys from GitHub on push to `main`

## 2. Non-goals

- Multi-user, roles, or sharing
- Any sync back to Google Sheets
- Spreadsheet-like editing (cell selection, formulas, drag-fill)
- Native mobile app; responsive web is enough
- Migrating existing sheet data — see decision D4

## 3. Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Language / framework | Python + Django 5.x + HTMX |
| D2 | Store | SQLite, file outside the repo directory |
| D3 | Remote access | Public domain, Caddy reverse proxy, TLS via Let's Encrypt |
| D4 | Data | Start fresh. Old sheet stays as a read-only archive |
| D5 | Auth gate | Caddy `basic_auth`. No auth code in Django |
| D6 | Deploy | GitHub Actions, SSH to VPS, `git pull` + migrate + restart |

### Notes on D5

`basic_auth` is one shared credential over TLS with no logout and no
audit trail. Acceptable for a single-user job tracker, and it is the
only option that costs zero application code. The gate is one layer in
front of the app, so swapping it later for a Django login view or
oauth2-proxy touches no application code. Revisit if a second person
ever needs access.

### Notes on D2

The SQLite file is the only copy of the data once the sheet is retired.
Backups (§10) are not optional and must be working before the sheet is
abandoned.

## 4. What the GAS app does today

Read from `clasp/`. Recording it here because the source is compiled
TypeScript output and is hard to read.

### 4.1 Sheet layout

```
        col 1          col 2          col 3        col 4      col 5
row 1                                 STATE DEFS   STATE DEFS STATE DEFS
row 2   metadataHead   metadataBody   step (new)   step       step (old)
row 3   metadataHead   metadataBody   step (new)   step
```

- Row 1, columns 3+ define the available states. Cell text is
  `"GROUP / NAME"`; the cell's background and font colours *are* the
  state's colours.
- Rows 2+ are opportunities, one per row.
- Column 1 (`metadataHead`, yellow) holds company, position, comments.
- Column 2 (`metadataBody`, yellow) holds date, source, contact.
- Columns 3+ hold steps, newest in column 3, older pushed right.
- A step's state is encoded as its cell's background colour, matched
  back to a state by hex string.

### 4.2 Field packing

Each cell holds several fields concatenated into one rich-text string,
separated by literal separators, with per-field text styles:

| Cell | Fields (separator after each) |
|------|-------------------------------|
| metadataHead | `company` ` / `, `position` `\n\n`, `comments` |
| metadataBody | `date` `\n\n`, `source` `\n`, `contact` |
| step | `date` ` __ `, `time` `\n\n`, `title` `\n`, `contact` `\n\n`, `comments` |

`StateToSheetBridge` builds a regexp from those separators to parse the
string back into fields. `Field` handles defaults and emptiness.

**This whole layer disappears in the port.** Fields become columns.
`Field`, `StateToSheetBridge`, `App`, and the colour-matching in
`StatesManager` have no equivalent in the target. The parsing regexp is
the single largest source of fragility in the current app.

### 4.3 Defaults

| Thing | Default |
|-------|---------|
| company | `????` |
| position | `[TBC]` |
| opportunity date | today |
| source | `LinkedIn` |
| contact (opportunity and step) | `(Contact unknown)` |
| step title | `Applied via site` |
| step state | `UNREMARKABLE` |
| timezone | `Europe/Berlin` |

### 4.4 Behaviour worth keeping

- Creating an opportunity also creates its first step automatically,
  using the opportunity's date and contact and the default step title.
- New steps are prepended (`steps.unshift`), so the newest step sits
  leftmost, next to the summary, pushing older ones right. This is the
  layout to preserve.
- Comments are editable on their own, through a separate dialog, for
  both opportunities and steps.

### 4.5 Ordering rules — port these exactly

Group ranking: `ATTENTION` 3, `DUE` 2, `COMPLETE` 1, anything else -1.

**Steps within an opportunity** (`Opportunity.sortSteps`):

1. By group rank, descending.
2. Tie: by `date` + `time` ascending — *except* when the state's group
   is `COMPLETE`, where it is descending.

**Opportunities within the pool** (`Pool.sortOpportunities`), keyed on
each opportunity's *first* (newest) step:

1. Opportunities with no steps sort first.
2. By group rank, descending.
3. Tie: by the state's position in the header row, ascending.
4. Tie: by `date` + `time` ascending — again inverted for `COMPLETE`.

### 4.6 Bugs in the current app — do not port

- `handleCreateOpportunity` and `handleCreateStep` test `if (data.id)`.
  Index `0` is falsy, so editing the *first* opportunity, or the first
  step of an opportunity, silently creates a duplicate instead of
  updating. Using real primary keys removes the class of bug.
- `dieUnlessSelection` calls leftover debug functions `a()` and `b()`,
  which pop up message boxes.
- A step's state is stored only as a cell colour. Changing the
  spreadsheet theme rewrites the data.
- `Pool.updateUI` deletes and re-inserts every row on every change.

### 4.7 Pools are a spreadsheet workaround

`Pool` maps to one sheet. The workflow it supported: one sheet is the
live one, another is the current archive, older archives sit behind
them. On landing a job, everything live gets archived; before the next
search, the archive is itself archived and a fresh one started.

The only reason for the generations is that long sheets are unwieldy.
That is a property of spreadsheets, not of the work. A table with an
index does not get slower or harder to read because old rows are in it.

So `Pool` does not become a model. The whole concept collapses to one
nullable timestamp on `Opportunity` (§6.5), and the generations
disappear entirely — `archived_at` already orders archived
opportunities by when they were put away, which is what the
generations were approximating.

### 4.8 What the sample export shows

`clasp/Crm-clasp-2 - Sheet2.csv` is one exported opportunity row. Three
things came out of checking it against the code above.

**Steps really are newest-first.** Left to right: 2025-07-21, 07-18,
07-15, 07-11, 07-08. Confirms §4.4 and the layout in §7.

**The stored text does not match the parser.** Rebuilding the regexps
from §4.2 and running them over the row: all three cell types fail to
match. `metadataHead` expects a literal `" / "` between company and
position that is nowhere in the cell; `metadataBody` and the step cells
have single newlines where the code expects doubled ones. A failed
match means `loadTextDataFromSheet` returns early and every field keeps
its default, so such a row would read back as `????` / `[TBC]`.

Either the sheet drifted from the code, or these cells were typed and
pasted by hand rather than entered through the form — the job
description in the sample is clearly pasted from a job ad. The cause
does not much matter. What it shows is that the packed-string format is
not actually load-bearing, which is the §4.2 fragility argument turning
up in real data.

**A CSV export cannot carry state at all.** A step's state is its
cell's background colour (§4.1), and CSV has no formatting, so the
export drops it entirely. Nothing in the sample says whether any step
is `DUE`, `GHOSTED` or `ACCEPTED`. Recovering that would need the
Sheets API to read cell backgrounds.

This is the §6.3 argument made concrete: data encoded as presentation
survives only inside the tool that drew it. It also confirms D4 — a
"start fresh" decision made for convenience turns out to be the only
cheap option, since a CSV-based import would silently produce rows with
default fields and no states.

No decision changes. Two details for the port, though:

- The opportunity `comments` field holds the whole job ad — 1870
  characters in this one sample. The summary card has to cope with
  that (§7).
- `position` carries more than a job title: `"Staff Software Engineer -
  Distributed AI\nBased in Edinburgh, remote. £125k"`. Location and
  salary are in there by convention. Splitting them into their own
  fields is an obvious improvement and deliberately not done now —
  noted in §13.

## 5. Target architecture

```
browser ── HTTPS ──▶ Caddy (TLS + basic_auth) ──▶ gunicorn ──▶ Django
   :443                    127.0.0.1:8000                       │
                                                                ▼
                                            /var/lib/crm-jobs/db.sqlite3
```

- One VPS, two systemd units (`caddy`, `crm-jobs`).
- Django serves its own static files through WhiteNoise, so Caddy needs
  no static-file configuration.
- HTMX vendored as a static file, not loaded from a CDN. No npm, no JS
  build step.
- Tailwind via the standalone CLI binary, which needs no Node.

Repo layout:

```
crm-jobs/
  pyproject.toml          uv-managed
  Taskfile.yml            task qa, task dev, task test
  manage.py
  config/                 settings, urls, wsgi
  jobs/                   the one app: models, views, templates
  static/                 htmx.min.js, compiled tailwind css
  deploy/                 Caddyfile, crm-jobs.service, backup timer
  .github/workflows/      ci.yml, deploy.yml
  clasp/                  kept read-only as reference until phase 7
```

### Deviation from AGENTS.md worth recording

AGENTS.md names `pydantic` for models. Django's ORM models fill that
role here; adding pydantic on top would duplicate validation for no
gain. Pydantic stays available for anything outside the ORM, such as
parsing config. Record this in `docs/initial-context.md` in phase 1.

## 6. Data model

```python
class Group(models.TextChoices):
    ATTENTION = "ATTENTION"
    DUE = "DUE"
    COMPLETE = "COMPLETE"

GROUP_RANK = {Group.ATTENTION: 3, Group.DUE: 2, Group.COMPLETE: 1}

class State(models.Model):
    slug = models.SlugField(unique=True)          # "bad-feeling" — CSS hook
    name = models.CharField(max_length=50)        # "BAD_FEELING" — display
    group = models.CharField(max_length=20, choices=Group)
    sort_order = models.PositiveIntegerField()    # tie-break, §4.5 rule 3

class Opportunity(models.Model):
    company = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    date = models.DateField()
    source = models.CharField(max_length=100, default="LinkedIn")
    contact = models.CharField(max_length=200, default="(Contact unknown)")
    comments = models.TextField(blank=True, default="")
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Step(models.Model):
    opportunity = models.ForeignKey(Opportunity, related_name="steps",
                                    on_delete=models.CASCADE)
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    title = models.CharField(max_length=200, default="Applied via site")
    contact = models.CharField(max_length=200, default="(Contact unknown)")
    comments = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

- `time` is nullable because the GAS app treats `":"` as empty.
- `group` is a `TextChoices` field, not a separate table. Promote it
  only if groups need their own attributes.
- **No colour anywhere in the model.** See §6.3.
- `archived_at` is the whole of what `Pool` used to be. See §6.5.
- `slug` exists so presentation has a stable key. Renaming the display
  `name` from `BAD_FEELING` to `Bad feeling` must not repaint the board.
- `sort_order` replaces the sheet's column position. It is domain, not
  layout: it is the third tie-break in §4.5.
- `GROUP_RANK` lives next to the enum, not in the database. It is a
  business rule, and a rule that has never changed.
### 6.1 Seed states

Taken from the live sheet header row, in column order. `sort_order` is
that order and drives the tie-break in §4.5.

| sort_order | group | name | slug |
|---|---|---|---|
| 1 | ATTENTION | ERROR | `error` |
| 2 | ATTENTION | OVERDUE | `overdue` |
| 3 | DUE | DUE | `due` |
| 4 | DUE | TENTATIVE | `tentative` |
| 5 | COMPLETE | ACCEPTED | `accepted` |
| 6 | COMPLETE | SUCCESS | `success` |
| 7 | COMPLETE | BAD_FEELING | `bad-feeling` |
| 8 | COMPLETE | GOING_WELL | `going-well` |
| 9 | COMPLETE | UNREMARKABLE | `unremarkable` |
| 10 | COMPLETE | GHOSTED | `ghosted` |
| 11 | COMPLETE | FAIL | `fail` |
| 12 | COMPLETE | BLACKLIST | `blacklist` |

No colours here. The sheet's hex values were a storage format, not a
design; the palette is chosen fresh in CSS (§6.3).

Only three groups occur, matching `GROUPS_RANKED` in the GAS source
exactly: `ATTENTION` 3, `DUE` 2, `COMPLETE` 1.

### 6.2 What the groups actually mean

`COMPLETE` is a misnomer inherited from the sheet. It holds
`GOING_WELL`, `BAD_FEELING` and `UNREMARKABLE`, which are ongoing, not
finished. The real meaning of the three groups is:

| group | meaning |
|-------|---------|
| ATTENTION | something is wrong, act now |
| DUE | something is scheduled |
| COMPLETE | nothing is pending |

That also explains the date inversion in §4.5: for `ATTENTION` and
`DUE`, oldest first, because the most overdue thing is the most urgent.
For `COMPLETE`, newest first, because with nothing pending the only
useful order is most-recently-touched.

Keep the group names as they are — they match the existing mental
model and the seeded data. Record the meaning here rather than
renaming.

`StatesManager.sortByGroup` carries a `TODO: calculate this by position
in header row`. With `position` stored, group rank is derivable from
the first position at which each group appears. Not worth doing: three
groups, explicit ranking is clearer.

### 6.3 Where colour lives, and why not in the model

The GAS app stored a step's state as its cell's background colour
because in a spreadsheet the cell *is* the storage. There is no such
constraint here, and carrying it over would put presentation inside the
domain: the model would know hex values, the admin would let you edit
them, and a designer changing the palette would be writing a migration.

Split it by what each layer legitimately knows:

| Layer | Knows |
|-------|-------|
| Model | that a step has a state, that a state belongs to a group, and that groups rank |
| Template | the state's `slug` and `group`, emitted as data attributes |
| CSS | what those slugs and groups look like |

The model never names a colour. The stylesheet never encodes a rule.

Template emits identity, not appearance:

```html
<article class="card card--step"
         data-state="{{ step.state.slug }}"
         data-group="{{ step.state.group|lower }}">
```

One stylesheet owns the palette:

```css
/* jobs/static/jobs/states.css
   the only file in the project that knows what a state looks like */

.card--step { background: var(--state-bg); color: var(--state-fg); }

/* group fallback: a new state with no rule of its own still renders */
[data-group="attention"] { --state-bg: #b3261e; --state-fg: #ffffff; }
[data-group="due"]       { --state-bg: #ffd54f; --state-fg: #1a1a1a; }
[data-group="complete"]  { --state-bg: #f5f5f5; --state-fg: #1a1a1a; }

/* per-state, later in the cascade so it wins */
[data-state="error"]        { --state-bg: #b3261e; --state-fg: #ffffff; }
[data-state="overdue"]      { --state-bg: #e8710a; --state-fg: #1a1a1a; }
[data-state="due"]          { --state-bg: #ffd54f; --state-fg: #1a1a1a; }
[data-state="tentative"]    { --state-bg: #fff3cd; --state-fg: #1a1a1a; }
[data-state="accepted"]     { --state-bg: #1b5e20; --state-fg: #ffffff; }
[data-state="success"]      { --state-bg: #a5d6a7; --state-fg: #1a1a1a; }
[data-state="going-well"]   { --state-bg: #c8e6c9; --state-fg: #1a1a1a; }
[data-state="unremarkable"] { --state-bg: #f5f5f5; --state-fg: #1a1a1a; }
[data-state="bad-feeling"]  { --state-bg: #e28fae; --state-fg: #1a1a1a; }
[data-state="ghosted"]      { --state-bg: #e0e0e0; --state-fg: #424242;
                              border-style: dashed; }
[data-state="fail"]         { --state-bg: #d7ccc8; --state-fg: #4e342e; }
[data-state="blacklist"]    { --state-bg: #37474f; --state-fg: #ffffff; }
```

Two things fall out of this that the GAS version could not do:

- Adding a state is a data change. It renders in its group's colours
  immediately, with no CSS written, and no broken card.
- Dark mode is a media query, not a second set of columns. Not built
  now; the hook is there if wanted.

### 6.4 The palette

Fixed. It is not expected to change, and nothing in the app reads it at
runtime, so it needs no admin screen and no table.

Shape: `ATTENTION` is loud, because it means act now. `DUE` is warm and
mid-weight. `COMPLETE` is quiet — eight of the twelve states live there,
and a board of eight saturated blocks is unreadable. Within `COMPLETE`,
lightness carries the outcome: dark green for `ACCEPTED`, pale green
through neutral grey to brown-grey for `FAIL`, near-black for
`BLACKLIST`.

Every pair below was checked against WCAG AA for body text (4.5:1):

| state | bg | fg | ratio |
|-------|----|----|------:|
| ERROR | `#b3261e` | `#ffffff` | 6.54 |
| OVERDUE | `#e8710a` | `#1a1a1a` | 5.63 |
| DUE | `#ffd54f` | `#1a1a1a` | 12.33 |
| TENTATIVE | `#fff3cd` | `#1a1a1a` | 15.71 |
| ACCEPTED | `#1b5e20` | `#ffffff` | 7.87 |
| SUCCESS | `#a5d6a7` | `#1a1a1a` | 10.59 |
| GOING_WELL | `#c8e6c9` | `#1a1a1a` | 12.94 |
| UNREMARKABLE | `#f5f5f5` | `#1a1a1a` | 15.96 |
| BAD_FEELING | `#e28fae` | `#1a1a1a` | 7.27 |
| GHOSTED | `#e0e0e0` | `#424242` | 7.61 |
| FAIL | `#d7ccc8` | `#4e342e` | 7.20 |
| BLACKLIST | `#37474f` | `#ffffff` | 9.65 |

Worst case 5.63:1, against a 4.5:1 requirement.

Two deliberate choices in there:

- `BAD_FEELING` is darker than a pastel pink would be. At equal
  lightness, pink and green are the classic red-green collision, and
  `SUCCESS` sitting next to `BAD_FEELING` looking identical is the one
  confusion that actually matters. Darkening it separates them by
  lightness as well as hue.
- `GHOSTED` gets a dashed border. Some pairs in `COMPLETE` are close in
  lightness and colour alone will not always separate them — the state
  name is printed on every card, so colour is never the only channel,
  and `GHOSTED` gets a second visual one because it is the state you
  scan for.

The sticky summary card is deliberately outside this scheme: neutral
white with a hard right border, so it reads as a different kind of
object rather than another state.

Colour is the obvious case; the same split applies to the rest:

| Concern | Lives in | Never in |
|---------|----------|----------|
| Field values, relationships | `jobs/models.py` | views, templates |
| Sort rules (§4.5) | `jobs/ordering.py`, pure functions | views, templates, DB ordering hacks |
| Validation, coercion | `jobs/forms.py` | views, models' `save()` |
| Fetch and render | `jobs/views.py` | business rules |
| Markup, data attributes | templates | branching on business rules |
| Every colour, size, spacing | CSS | models, views, templates |

Phase 2 keeps the sort key a pure function precisely so it can be
tested without a database and cannot drift into a view.

### 6.5 Archiving

An opportunity is live while `archived_at` is `NULL`, archived once it
is set. That is the whole mechanism.

```python
class OpportunityQuerySet(models.QuerySet):
    def live(self):     return self.filter(archived_at__isnull=True)
    def archived(self): return self.exclude(archived_at__isnull=True)
```

Explicit querysets, not a default manager that hides archived rows. A
manager that silently filters is convenient for a week and then bites
in the admin, in a data migration, and in search — the one place that
must see everything.

Three actions, matching how the app is used in bursts:

| Action | Effect |
|--------|--------|
| Archive one | `archived_at = now()` |
| Unarchive one | `archived_at = None` |
| Archive everything live | the "I got a job" action, at the end of a burst |

Nothing is deleted, so all three are reversible and none needs a scary
confirmation — though bulk archive touches every live row at once, so
it gets one anyway, with the count in it.

Two consequences worth stating:

- The board (§7) shows live opportunities only. Archived ones are not
  reachable from it beyond a count, by design: not seeing them is the
  point of archiving.
- Until search exists, the Django admin is how archived opportunities
  get looked at. It is already registered in phase 1, so this costs
  nothing.

The ordering rules in §4.5 apply to the live board. Archived
opportunities sort by `archived_at` descending — "which burst was this"
is the only question worth asking of them, and urgency ranking is
meaningless once nothing is pending.

### 6.6 Why a new opportunity is UNREMARKABLE

`DEFAULT_STEP_STATE` is `UNREMARKABLE`, in group `COMPLETE`, the
lowest-ranked group. That looks like an accident — new things sinking
to the bottom — but reading the full sort says otherwise.

`UNREMARKABLE` is `sort_order` 9 of 12, so a new opportunity lands here:

```
ATTENTION   ERROR, OVERDUE              act now
DUE         DUE, TENTATIVE              scheduled
COMPLETE    ACCEPTED, SUCCESS,          nothing pending,
            BAD_FEELING, GOING_WELL,    best outcome first
            UNREMARKABLE   ← new one, newest first within the state
            GHOSTED, FAIL, BLACKLIST
```

Mid-pile, above everything dead. And it is the semantically right
group: you applied, the ball is in their court, nothing is pending on
you — which is what `COMPLETE` means (§6.2). The `sort_order` ranking
inside the group reads as "how alive is this", with `ACCEPTED` on top
because an offer matters most even when nothing is due.

**Decision: keep it. The sort is not changed.**

The original worry — new opportunities getting buried — was a symptom
of the sheet having no archive, so the dead tail grew without limit.
The board now shows live opportunities only (§6.5), so that tail is
short and a new row lands near the top of it.

What is left of the worry is "I added something and it moved" — a
presentation problem, answered in presentation: after a create, the new
row is highlighted and scrolled to (§7). Floating new rows to the top
of the board instead would mean new-but-unremarkable outranking
`GOING_WELL`, and a board whose position no longer tracks how alive
something is.

If it turns out to grate in real use, the clean fix is a distinct
`APPLIED` state at a higher `sort_order` — a data change — not a
special case inside the sort function.

## 7. UI

One page, `GET /`. One row per live opportunity (§6.5), with an
archived count in the header and nothing else about the archive.

```
-------------------------------------------------
| SUMMARY | STEP 3 | STEP 2 | STEP 1 |
-------------------------------------------------
   ^ sticky            ^ newest first, oldest right
```

```css
.opportunity     { display: flex; gap: .5rem; overflow-x: auto; }
.card--summary   { position: sticky; left: 0; flex: 0 0 18rem; z-index: 1; }
.card--step      { flex: 0 0 16rem; }
```

The summary card collapses `comments` to a few lines behind a native
`<details>`, because it holds the pasted job ad — 1870 characters in
the sample export (§4.8) — and an 18rem card cannot show that inline.
No JavaScript needed for the toggle.

Each row scrolls horizontally on its own, so a long-running opportunity
does not force the whole page sideways. The summary card stays pinned
at the left edge while its steps scroll under it. Step cards carry
`data-state` and `data-group`; CSS turns those into colours (§6.3).

### HTMX routes

| Method | Path | Returns |
|--------|------|---------|
| GET | `/` | full board |
| GET | `/opportunities/new` | form partial |
| POST | `/opportunities/` | new row partial, prepended to board |
| GET | `/opportunities/<id>/edit` | form partial |
| POST | `/opportunities/<id>/` | row partial |
| POST | `/opportunities/<id>/delete` | empty, swaps row out |
| GET | `/opportunities/<id>/comments/edit` | comments form partial |
| POST | `/opportunities/<id>/comments` | row partial |
| GET | `/opportunities/<id>/steps/new` | form partial |
| POST | `/opportunities/<id>/steps/` | row partial |
| GET | `/steps/<id>/edit` | form partial |
| POST | `/steps/<id>/` | row partial |
| POST | `/steps/<id>/delete` | row partial |
| POST | `/opportunities/<id>/archive` | empty, swaps row out |
| POST | `/opportunities/<id>/unarchive` | row partial |
| POST | `/opportunities/archive-live` | full board, now empty |

Every mutation returns the affected opportunity row and swaps it with
`hx-target="#opportunity-<id>" hx-swap="outerHTML"`. Re-sorting the
whole board re-renders the board. `django-htmx` gives `request.htmx` for
partial-vs-full rendering; it is one small dependency and earns its
place.

Forms use Django `ModelForm`, rendered into a drawer on the right,
mirroring the GAS sidebar. Validation errors re-render the form partial
with its messages, no page reload.

## 8. Phases

TDD throughout, per AGENTS.md: failing test, confirm the failure is the
expected one, minimal implementation, refactor green. `task qa` before
every PR.

### Phase 0 — Scaffolding

- `uv init`, Python 3.13, Django, pytest, pytest-django, ruff, ty.
- `Taskfile.yml` with `task dev`, `task test`, `task qa`
  (`ruff check` + `ruff format --check` + `ty` + `pytest`).
- Add ruff and ty hooks to `.pre-commit-config.yaml`, which currently
  has no Python linters.
- `config/` project, `jobs/` app, `/healthz` returning 200.
- `.github/workflows/ci.yml` running `task qa` on PRs and `main`.

Done when: `task qa` green in CI, `/healthz` returns 200 locally.

### Phase 1 — Models

- Tests for model defaults and constraints first.
- `State`, `Opportunity`, `Step` + migrations.
- Data migration seeding the 12 states from §6.1.
- Guard test: `State` exposes no colour field, so the boundary in
  §6.3 fails loudly rather than eroding.
- Django admin registered for all three: a free CRUD backdoor while the
  real UI is being built, and a permanent escape hatch.
- Fill in `docs/initial-context.md` (architecture, boundaries, the
  pydantic deviation from §5).

Done when: states seeded, admin can create an opportunity with steps.

### Phase 2 — Ordering

The one piece of real domain logic. Port §4.5 exactly.

- Table-driven tests covering: group ranking, the `COMPLETE` inversion,
  step-position tie-break, opportunities with no steps, equal
  timestamps, null `time`.
- Implement as a queryset/manager method plus a pure sort key function.
  Keep the key function pure and directly unit-testable.

Done when: ordering tests pass and the rules in §4.5 are each covered
by a named test.

### Phase 3 — Read-only board

- Board view, row partial, summary card, step card.
- Tailwind standalone CLI wired into `task dev` in watch mode.
- Sticky summary + per-row horizontal scroll (§7).
- State palette from §6.4 in one stylesheet, keyed on `data-state` /
  `data-group`.
- Tests: view returns 200; steps render newest-first; a row with no
  steps renders; cards emit `data-state` and `data-group`; a state
  with no per-state CSS still renders in its group's colours; a 2000
  character comment does not blow out the summary card; every
  pair in §6.4 clears 4.5:1, asserted by a contrast test so a later
  tweak cannot quietly break legibility.

Done when: a sheet-shaped board renders from seeded data and looks
right at phone width.

### Phase 4 — Mutations

- All routes in §7, with `ModelForm`s.
- Creating an opportunity also creates its first step (§4.4).
- Archive, unarchive, and archive-everything-live (§6.5).
- After a create, highlight the new row and scroll it into view (§6.6).
- Delete confirmations; bulk archive confirms with its count.
- Tests: one per route, plus validation-failure re-render, plus the
  create-first-step behaviour, plus that editing the first opportunity
  updates rather than duplicates (the §4.6 bug, as a regression test),
  plus that the board excludes archived opportunities and that
  unarchiving puts one back.

Done when: everything the GAS menus did is doable in the browser.

### Phase 5 — Production settings

- `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
  from environment.
- `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT=False` (Caddy already
  redirects), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- WhiteNoise, `collectstatic`.
- SQLite `OPTIONS`: `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`,
  `transaction_mode="IMMEDIATE"`.
- `manage.py check --deploy` clean, asserted in CI.

Done when: `check --deploy` reports no issues.

### Phase 6 — Deploy

Files in `deploy/`, secrets never in the repo.

- `crm-jobs.service`: gunicorn, 2 workers, bound to `127.0.0.1:8000`,
  running as an unprivileged `crm` user, `EnvironmentFile=/etc/crm-jobs/env`.
- `Caddyfile`:
  ```
  crm.example.com {
      basic_auth {
          fritz <bcrypt hash from `caddy hash-password`>
      }
      reverse_proxy 127.0.0.1:8000
  }
  ```
- `.github/workflows/deploy.yml`: on push to `main`, needs the CI job,
  SSHes in and runs pull → `uv sync --frozen` → `migrate` →
  `collectstatic` → `systemctl restart crm-jobs`.
- Deploy user is `deploy`, not root. Its sudoers entry permits exactly
  `systemctl restart crm-jobs`.
- Paths: code `/srv/crm-jobs`, data `/var/lib/crm-jobs/db.sqlite3`,
  secrets `/etc/crm-jobs/env` mode 0600. Deploy touches code only.
- Firewall: 80, 443, and SSH. Port 8000 never exposed.

Done when: push to `main` lands on the VPS and the site answers over
HTTPS behind the password prompt.

### Phase 7 — Retire the GAS app

- Confirm backups have been running and a restore has been tested.
- Export the sheet to CSV and keep it outside the repo as the archive.
- Delete `clasp/`, or move it to `docs/archive/` if it is worth keeping
  as history.
- Archive this plan per AGENTS.md:
  `docs/archive/YYYY-MM-DD-HHMM-<shortsha>-001-port-gas-to-django.md`.

## 9. Local development

```bash
uv sync
task dev          # runserver + tailwind watch
task test
task qa
```

SQLite file lives at `./db.sqlite3` locally, gitignored.

## 10. Backups

Required before phase 7.

- systemd timer, daily:
  `sqlite3 /var/lib/crm-jobs/db.sqlite3 ".backup /var/backups/crm-$(date +%F).sqlite3"`
- Keep 14 days locally, push off-box with restic or rsync.
- Test a restore once, by hand, and note in `docs/` that it was done.

`.backup` is used rather than `cp` because it is safe against a
concurrently written WAL database.

## 11. Risks

| Risk | Mitigation |
|------|-----------|
| SQLite file is the only copy of the data | §10, tested before the sheet is retired |
| Shared basic-auth credential, no logout | Accepted for one user; gate is swappable without app changes |
| SQLite writer lock under concurrent writes | WAL + `IMMEDIATE` transactions; a single user will not hit it |
| Ordering rules ported subtly wrong | Phase 2 is test-first, with each rule in §4.5 named in a test |
| Deploy clobbers the database | Data lives outside the deploy directory |

## 12. Open questions

None outstanding. Resolved along the way:

| Was | Resolved in |
|-----|-------------|
| State list, groups, order | §6.1 |
| Palette | §6.4 |
| Whether `Pool` becomes a model | §4.7, §6.5 |
| Archive vs delete | §6.5 |
| Whether the `UNREMARKABLE` default is a bug | §6.6 |

## 13. After the port

Not in scope here. Listed so the port does not block them.

### Search — the named first follow-up

Search is what makes the archive usable, and it is the archive's only
UI (§6.5). Nothing in this plan should get in its way:

- Searchable text lives in ordinary columns — `company`, `position`,
  step `title`, both `comments` fields — not packed into one string as
  the sheet did (§4.2).
- `archived_at` is a filter, not a partition. Search spans live and
  archived in one query and can scope either way. This is why §6.5
  refuses a default manager that hides archived rows.
- Start with `icontains` across those columns. For a few hundred
  opportunities on SQLite that is instant, and it is about fifteen
  lines. Move to FTS5 only if it actually gets slow — that means a
  virtual table and triggers in a raw-SQL migration, which is real
  weight to carry for a personal tracker.
- Results reuse the existing row partial, so the summary-plus-steps
  layout works in search with no new templates.

### Possible later, not committed

- Split `location` and `salary` out of `position` (§4.8). They are
  already there by convention, and separate fields make them
  filterable. Left out of the port to keep the model a like-for-like
  move; worth doing once search exists.
- Dark mode: a media query over §6.4, no model change.
- Per-state colour editing without a deploy: a `theme` table read by a
  template tag, keeping hex out of `State`. Only if the palette turns
  out to change, which it is not expected to.
