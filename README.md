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

Create a new opportunity with the form. Add steps to track progress. New opportunities and steps are dated today by default. Mark status to sort on the board. A new step also has a "Previous step" pulldown, to settle the state of the step before it in the same save.

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

GitHub settings for this repo live in Terraform, in `infra/`:

- squash merge only, with the PR title as the commit title; auto-merge allowed
- head branches deleted after merge; PRs behind `main` offer "Update branch"
- a ruleset on `main`: changes go through a PR, no force pushes or
  deletion, and the `qa (3.14)` and `Conventional Commit title` checks
  must pass on a branch that is up to date with `main`

It is applied by hand, never by CI.

### Setup

1. Install Terraform >= 1.6 from HashiCorp's tap:
   `brew install hashicorp/tap/terraform`.
2. Create a [fine-grained personal access
   token](https://github.com/settings/personal-access-tokens/new) for the
   `crm-jobs` repo only (Repository access: Only select repositories). Under
   repository permissions, add **Administration** and switch its access
   from the default Read-only to **Read and write**, then export it:

   ```bash
   export GITHUB_TOKEN=github_pat_...
   ```

3. Initialise, then import the settings that already exist, so Terraform
   manages them instead of trying to create them:

   ```bash
   cd infra
   terraform init
   terraform import github_repository.crm_jobs crm-jobs
   # only if the ruleset already exists; its ID is in the ruleset's URL
   terraform import github_repository_ruleset.main crm-jobs:<ruleset-id>
   cd ..
   ```

4. From the project root, run `uv run poe infra`. It runs `terraform init`,
   shows the plan and applies it only if you answer `yes`; anything else is
   a dry run.

   Read the plan before applying: it should only change settings, never
   destroy the repository (`prevent_destroy` blocks that anyway).

### State

State is local, in `infra/terraform.tfstate`, and gitignored. It holds no
secrets but is needed to manage the settings later; if it is lost, run the
imports in step 3 again. `infra/.terraform.lock.hcl` is committed, to pin the
provider version.

### Changes later

Edit the `.tf` files, then `uv run poe infra`. A plan with no edits shows
drift, for example a setting changed in the GitHub UI. A ruleset made by
hand in the UI sits beside the managed one and both apply, so delete it once
`protect-main` is in place.

After any change that renames a check job in `ci.yml` or `pr-title.yml`,
update `required_check` to match. Apply the ruleset only once both checks
have run on a PR to `main`, or PRs wait for checks that never report.

## Development

See [AGENTS.md](./AGENTS.md) for project workflow, code standards, and branching.

See [docs/plans/](./docs/plans/) for active development phases.

## License

[MIT](./LICENSE)
