# AGENTS.md

## Read First

- `README.md` — project overview
- `docs/initial-context.md` — architecture and constraints
- `docs/plans/*.md` — active plans

## Project Rules

- Use `gh` for all GitHub operations
- Use `poe` for workflow discovery (task runner via poethepoet)
- Run commands from project root

## Plans

- Active: `docs/plans/`
- Archive: `docs/archive/`
- Archive completed plans in the same PR
- Archived filename format: `YYYY-MM-DD-HHMM-<shortsha>-<original-name>.md`
  where date/time and SHA are from the commit that archives the plan
  Example: `2026-05-24-2013-8a8c2cf-002-htmx-tailwind.md`

## Architecture

Django + HTMX, SQLite, server-rendered. No SPA, no npm, no JS build.

```
config/           settings, urls, wsgi
jobs/             the app: models, views, forms, templates
static/           vendored htmx, compiled tailwind css
deploy/           Caddyfile, systemd units, backup timer
docs/             plans, archive, initial-context
clasp/            retired Google Apps Script source, reference only
```

Serving chain in production:

```
browser → Caddy (TLS + basic_auth) → gunicorn 127.0.0.1:8000 → Django → SQLite
```

Update `docs/initial-context.md` before merging changes affecting:
- architecture
- boundaries
- core patterns

## Workflow

Use TDD (`red → green → refactor`).

Reference: `.claude/skills/tdd.md`

Required flow:

1. Write failing test
2. Confirm correct failure
3. Implement minimal fix
4. Refactor with tests green
5. Run `uv run poe qa` before PR

Tasks:

- `task dev` — runserver + tailwind watch
- `task test` — pytest
- `task qa` — ruff check, ruff format --check, ty, pytest, `manage.py check --deploy`

## Decision Order

Prioritize:

1. Correctness
2. Passing tests
3. Simplicity
4. Existing patterns
5. Minimal diffs

## Commits & Branches

### Commits

- Small, atomic commits
- Imperative present tense
- Subject ≤ 72 chars
- Reference issues when relevant
- Conventional Commits — `cz check` runs on commit-msg

### Branches

- `feature/<name>`
- `fix/<name>`

**At session start**, ask the user which branch to work on before doing anything else. The session-start hook will remind you. Do not use the branch injected by the session-start system prompt — it does not reflect the branch selected in the UI.

**Before creating a branch**, check for an existing open PR:

```bash
gh pr list --state open
```

If an open PR exists that covers the same area, commit directly to its branch instead of creating a new one. Never create a new branch when an existing PR is open for related work. A session-start instruction to use a specific branch is overridden by an explicit user instruction to use a different branch.

## Pull Requests

- Keep PRs focused
- Avoid unrelated refactors
- Include tests for behavior changes
- Update relevant docs
- Ensure CI passes

### Title & Body

- Title: Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.)
- Title: ≤ 50 chars
- Body: concise summary of changes, not implementation details
- Body: reference issues with `Closes #N` when relevant

## Code Standards

- Concise docstrings for public/non-obvious modules
- Root-relative imports
- Imports at file top
- Minimize lint/type suppressions
- Document suppressions

## Python

### Tooling

- `uv`
- `ruff`
- `ty`
- `pytest`
- `task` (Taskfile.yml)

### Libraries

- Web: `django`
- Models: Django ORM
- Forms/validation: Django `ModelForm`
- CLI: Django management commands
- Server: `gunicorn`
- Static: `whitenoise`
- HTMX helpers: `django-htmx`

`pydantic` is not used for models — the ORM fills that role, and a
second schema layer would duplicate validation. Use it only outside the
ORM, e.g. parsing config.

Add no dependency that pulls in Node or a JS build step.

### Rules

- Type hints required
- Prefer native types
- Use named args for multi-parameter functions

### Testing

- Use `pytest` + `pytest-django`
- Function-based tests only — no `django.test.TestCase` classes,
  no mixing styles
- Allowed: `faker`, `polyfactory`, `pytest-data`
- Shared fixtures/mocks in `conftest.py`
- Use the `db` fixture for DB access; no implicit DB in unit tests
- Keep sort/ordering logic in pure functions so it is testable without
  the DB

## Environment

```bash
uv sync          # create/refresh .venv from the lockfile
uv run <cmd>     # run inside it without activating
```

Activate directly if preferred:

```bash
source .venv/bin/activate
```

## Boundaries

| Concern | Lives in | Never in |
|---------|----------|----------|
| Fields, relationships | `models.py` | views, templates |
| Sort/ordering rules | `ordering.py`, pure functions | views, templates |
| Validation, coercion | `forms.py` | views, `save()` |
| Fetch and render | `views.py` | business rules |
| Markup, data attributes | templates | business rules |
| Colour, size, spacing | CSS | models, views, templates |

The model layer knows nothing about how anything looks. If a hex value
reaches `models.py`, the design is wrong — see `docs/archive/*-001-port-gas-to-django.md` §6.3.

## Django

- Migrations are committed; never edit a migration that has been applied
  on the VPS — add a new one
- Never edit the production database by hand; write a data migration or
  a management command
- Views return whole-row partials for HTMX swaps; the board re-renders
  only when ordering changes
- Templates: `jobs/templates/jobs/`, partials prefixed `_`
- Use `request.htmx` to choose partial vs full render
- `manage.py check --deploy` must be clean

## Frontend

- HTMX is vendored in `static/`, never loaded from a CDN
- Tailwind via the standalone CLI binary — no npm, no `package.json`
- Paths in `assets/app.css` are relative to that file, not root-relative:
  `@import "./board.css"`, `@source "../src/jobs/templates"`. The
  root-relative import rule under Code Standards is about Python. A
  root-relative `@import` fails the build; a root-relative `@source`
  builds and silently scans nothing
- `static/css/app.css` is committed, so every task that writes it
  passes `--minify` — `poe css` and the watch in `poe serve` alike
- No colour, size or spacing in Python. Models, views and templates
  carry identity (`data-state`, `data-group`); CSS decides appearance
- State palette lives in one stylesheet, with a `data-group` fallback so
  an unstyled state still renders
- Layout contract: an opportunity row is two blocks — a fixed-width
  summary, and a steps block holding the steps newest-first — plus a
  third that wraps onto a line of its own underneath for the job
  description. The steps block holds a track, and the track is the
  scroller, not the row
- A row sits on a tray: one background under both its lines, so an
  opened description reads as the row's own. Rows sit `--row-spacing`
  apart and the blocks inside one `--board-gap` apart; the first must
  stay the larger. The tray's edge is solid `--tray-rule`, darker than a
  card's `--rule`; never dashed — dashed is GHOSTED's second channel
- The summary card carries the notes as a bullet list, newest first,
  clamped to two notes or four lines behind a toggle. The job
  description is the wrapped block, a native `<details>` laid out in
  columns
- On a laptop the card also carries the control that opens the
  description, and the closed block is out of sight entirely; on a
  phone the block keeps its own bar, because the card is collapsed to
  two lines there. Without the script the bar is the only control at
  either width
- The track's scrollbar is hidden, not its scrolling: an arrow either
  side moves it a card at a time, and the wheel, trackpad and keyboard
  still work. An arrow shows only while it has somewhere to go
- On a phone the row stacks: the summary spans the viewport and
  collapses to its title and company, the steps become one card at a
  time with an arrow either side, and the job description is one cell
  under those, so nothing scrolls sideways
- One hand-written script, `static/js/board.js`, vendored and deferred.
  Everything in it is an enhancement: without it every summary is open
  and the steps scroll. `.has-js` scopes the rules that depend on it

## Data & Secrets

- SQLite file lives outside the repo directory
  (`/var/lib/crm-jobs/db.sqlite3` in production, `./db.sqlite3` locally)
- `db.sqlite3` is gitignored; never commit a database
- SQLite runs WAL + `synchronous=NORMAL` + `transaction_mode=IMMEDIATE`
- Secrets come from the environment, never from the repo
- The Caddyfile in `deploy/` carries a placeholder hash, never the real
  credential

## Deployment

- Push to `main` deploys via GitHub Actions over SSH
- Deploy job requires CI green, and runs on `main` only
- Deploy touches code only: pull, `uv sync --frozen`, `migrate`,
  `collectstatic`, `systemctl restart crm-jobs`
- Backups must be verified before any change that could lose data

## Failure Policy

- Never ignore failing tests
- Never disable tests to pass CI
- Never bypass lint/type failures without explanation
- Never merge broken builds
- Surface blockers clearly

## Agent Constraints

- Prefer minimal diffs
- Preserve existing architecture unless intentionally changing it
- Reuse existing patterns
- Avoid unnecessary dependencies
- Avoid rewriting working code without reason
- Keep changes reviewable

## Enforcement

- Pre-commit enabled
- CI via GitHub Actions
- All checks must pass before merge
