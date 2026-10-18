# CRM Jobs

![Coverage](https://raw.githubusercontent.com/gotofritz/crm-jobs/badges/crm-jobs/coverage.svg)

Self-hosted job application tracker. Django + HTMX, SQLite, no SPA.

## Table of Contents

- [Overview](#overview)
- [User Guide](#user-guide)
- [Installation](#installation)
- [Repository settings](#repository-settings)
- [Development](#development)
- [License](#license)

## Overview

Track job opportunities from first application through final outcome. Organize by status (attention, due, complete), add notes and next steps, archive when done.

## User Guide

### Starting Out

Visit `/` to see your live opportunities. Each row shows one job:
- **Left card**: company, position, notes
- **Right cards**: steps (newest first), each with date, status, and details

Create a new opportunity with the form. Add steps to track progress. Mark status to sort on the board. A new step also has a "Previous step" pulldown, to settle the state of the step before it in the same save.

Archive opportunities when done — they move out of sight but stay searchable later.

### Statuses

**ATTENTION**: something needs action now
**DUE**: something is scheduled
**COMPLETE**: nothing pending (includes applied, rejected, ghosted, etc.)

## Installation

### Prerequisites

- Python 3.14+
- [pre-commit](https://pre-commit.com/#install) — git hook manager

### Setup

```bash
git clone https://github.com/gotofritz/crm-jobs.git
cd crm-jobs

# Create virtual environment and install dependencies
uv sync

# Set up git hooks
pre-commit install

# Run migrations
uv run python manage.py migrate

# Start development server
uv run python manage.py runserver
```

The compiled stylesheet is committed, so nothing needs building to run the app.
Editing anything in `assets/` does need a rebuild: `uv run poe css`, or
`uv run poe dev`, which watches. Either fetches the pinned Tailwind standalone
binary into `.tailwind/` the first time — no Node, no npm.

Visit `http://localhost:8000`

### Running Tests & Checks

```bash
uv run poe dev       # sync, migrate, then runserver with Tailwind watching
uv run poe migrate   # apply migrations, seeding states, sources and sectors
uv run poe css       # recompile static/css/app.css from assets/
uv run poe demo      # rebuild demo.sqlite3 with demo rows and serve it
uv run poe test      # pytest
uv run poe qa        # all checks (lint, type, test, deployment checklist)
uv run poe check-deploy  # Django's deployment checklist on production settings
```

### Configuration

Development needs no configuration. Anything host-specific comes from the
environment — see the table in
[docs/initial-context.md](./docs/initial-context.md#settings-and-secrets).
`DJANGO_SECRET_KEY` is required as soon as `DJANGO_DEBUG=false`: the process
refuses to start without it, so the marked-insecure development key in this
repository cannot reach production.

## Repository settings

`infra/` holds Terraform for the GitHub repo settings (merge options and the
`protect-main` ruleset: PR required, `qa (3.14)` and `Conventional Commit title` checks must pass). It is
applied by hand, never by CI. Needs Terraform >= 1.6 and a token with repo
admin rights in `GITHUB_TOKEN`.

```bash
cd infra
terraform init
terraform import github_repository.crm_jobs crm-jobs  # first run only
terraform plan   # review: this is a diff against the live repo
terraform apply
```

State is local and gitignored. Commit `.terraform.lock.hcl` after the first
`init`. After any change that renames a check job in `ci.yml`, update
`required_check` to match, or merges will block.

## Development

See [AGENTS.md](./AGENTS.md) for project workflow, code standards, and branching.

See [docs/plans/](./docs/plans/) for active development phases.

## License

[MIT](./LICENSE)
