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
class State(models.Model):
    name = models.CharField(max_length=50, unique=True)   # "UNREMARKABLE"
    group = models.CharField(max_length=20)               # ATTENTION|DUE|COMPLETE
    bg = models.CharField(max_length=7)                   # "#ffff00"
    fg = models.CharField(max_length=7)
    position = models.PositiveIntegerField()              # was column order

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
- `group` starts as a `CharField` with choices, not a separate table.
  Promote it only if groups need their own attributes.
### 6.1 Seed states

Taken from the live sheet header row, in column order. `position` is
that order and drives the tie-break in §4.5.

| position | group | name | bg | fg |
|---|---|---|---|---|
| 1 | ATTENTION | ERROR | `#cc0000` | `#ffffff` |
| 2 | ATTENTION | OVERDUE | `#ff6d01` | `#000000` |
| 3 | DUE | DUE | `#fbbc04` | `#000000` |
| 4 | DUE | TENTATIVE | `#fff2cc` | `#000000` |
| 5 | COMPLETE | ACCEPTED | `#0b8043` | `#ffffff` |
| 6 | COMPLETE | SUCCESS | `#34a853` | `#000000` |
| 7 | COMPLETE | BAD_FEELING | `#e8a598` | `#000000` |
| 8 | COMPLETE | GOING_WELL | `#b7e1cd` | `#000000` |
| 9 | COMPLETE | UNREMARKABLE | `#ffffff` | `#000000` |
| 10 | COMPLETE | GHOSTED | `#d9d9d9` | `#000000` |
| 11 | COMPLETE | FAIL | `#b7b7b7` | `#000000` |
| 12 | COMPLETE | BLACKLIST | `#434343` | `#ffffff` |

**The names, groups and order are confirmed. The hex colours are
placeholders** — plausible Google Sheets palette values, not read off
the sheet. Replace them with the real ones before the data migration
is written, or accept them as a fresh palette. Either way the migration
is the single place they live.

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
their state's `bg`/`fg` as CSS custom properties emitted from the DB.

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
- State colours driven from the DB.
- Tests: view returns 200; steps render newest-first; a row with no
  steps renders.

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

- State hex colours (§6.1) are placeholders. Read the real ones off the
  sheet header, or decide the placeholders are the new palette.
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
