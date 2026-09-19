# CRM Jobs

![Coverage](https://raw.githubusercontent.com/gotofritz/crm-jobs/badges/crm-jobs/coverage.svg)

Self-hosted job application tracker. Django + HTMX, SQLite, no SPA.

## Table of Contents

- [Overview](#overview)
- [User Guide](#user-guide)
- [Installation](#installation)
- [Development](#development)
- [License](#license)

## Overview

Track job opportunities from first application through final outcome. Organize by status (attention, due, complete), add notes and next steps, archive when done.

## User Guide

### Starting Out

Visit `/` to see your live opportunities. Each row shows one job:
- **Left card**: company, position, notes
- **Right cards**: steps (newest first), each with date, status, and details

Create a new opportunity with the form. Add steps to track progress. Mark status to sort on the board.

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

Visit `http://localhost:8000`

### Running Tests & Checks

```bash
uv run poe dev       # runserver with auto-reload
uv run poe test      # pytest
uv run poe qa        # all checks (lint, type, test)
```

## Development

See [AGENTS.md](./AGENTS.md) for project workflow, code standards, and branching.

See [docs/plans/](./docs/plans/) for active development phases.

## License

[MIT](./LICENSE)
