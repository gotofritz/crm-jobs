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

## 7. UI

One page, `GET /`. One row per opportunity.

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
  with no per-state CSS still renders in its group's colours; every
  pair in §6.4 clears 4.5:1, asserted by a contrast test so a later
  tweak cannot quietly break legibility.

Done when: a sheet-shaped board renders from seeded data and looks
right at phone width.

### Phase 4 — Mutations

- All routes in §7, with `ModelForm`s.
- Creating an opportunity also creates its first step (§4.4).
- Delete confirmations.
- Tests: one per route, plus validation-failure re-render, plus the
  create-first-step behaviour, plus that editing the first opportunity
  updates rather than duplicates (the §4.6 bug, as a regression test).

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

- `DEFAULT_STEP_STATE` is `UNREMARKABLE`, which is in group `COMPLETE`,
  the lowest rank. So a freshly created opportunity sorts to the
  *bottom* of the board, below everything with attention or due states.
  Intended, or an accident of the sheet? If new applications should
  surface at the top, either the default state changes or new
  opportunities need their own rule.
- Is there a "pool" concept beyond one sheet? The GAS `Pool` maps to a
  single sheet and the menu item is commented out. Assumed: no. If
  several sheets are in use, `Pool` becomes a model and opportunities
  gain a foreign key to it.
- Does anything depend on an opportunity being archivable rather than
  deleted? Not in the GAS app. Add an `archived_at` field if wanted.
