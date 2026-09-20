# 002 — Deploy to a VPS

Status: proposed
Date: 2026-09-20
Follows: `docs/archive/2026-09-20-2221-05dd166-001-port-gas-to-django.md`

## 1. Goal

Put the app on a VPS and keep it there:

- reachable over HTTPS at a domain I own, behind one password
- deployed by pushing to `main`, with no step done by hand
- backed up daily, off the box, with a restore that has been done once
  rather than assumed

Everything here was phases 5 to 7 of plan 001. Phase 5 shipped with the
ordering work; the rest never started.

## 2. Non-goals

- Containers, or anything that orchestrates them
- Zero-downtime deploys. A restart drops one request and nobody notices
- A staging environment. The demo database is what a risky change gets
  tried against
- Postgres. SQLite is the store and D2 in plan 001 says why
- Any auth code in Django. D5 says why

## 3. Decisions carried from plan 001

| # | Decision | Choice |
|---|----------|--------|
| D3 | Remote access | Public domain, Caddy reverse proxy, TLS via Let's Encrypt |
| D5 | Auth gate | Caddy `basic_auth`. No auth code in Django |
| D6 | Deploy | GitHub Actions, SSH to VPS, `git pull` + migrate + restart |

### Why `basic_auth` is still the answer

One shared credential over TLS, no logout, no audit trail. Acceptable
for a single-user job tracker, and the only option costing zero
application code. The gate is one layer in the chain, so swapping it for
a forward-auth proxy later touches the `Caddyfile` and nothing else.

### Why the deploy is `git pull` and not an artefact

There is no build. Python is not compiled, Tailwind's output is
committed (`static/css/app.css`), and HTMX is vendored. A pull is
already a complete deployment, so a registry, an image and a tag would
be three moving parts buying nothing.

## 4. The serving chain

```
browser ── HTTPS ──▶ Caddy (TLS + basic_auth) ──▶ gunicorn ──▶ Django
   :443                    127.0.0.1:8000                       │
                                                                ▼
                                            /var/lib/crm-jobs/db.sqlite3
```

One VPS, two systemd units (`caddy`, `crm-jobs`) and one timer. Django
serves its own static files through WhiteNoise, so Caddy needs no
static-file configuration and the two never disagree about which file
wins.

Three paths, and they stay apart on purpose:

| Path | Holds | Deploy touches it |
|------|-------|-------------------|
| `/srv/crm-jobs` | the checkout | yes, every deploy |
| `/var/lib/crm-jobs/db.sqlite3` | the data | never |
| `/etc/crm-jobs/env` | the secrets, mode 0600 | never |

A deploy that could reach the database is a deploy that can lose it.
That is why the file is not under the checkout, and why nothing below
runs `rm -rf` on anything.

## 5. Phase 1 — Production settings — done

Shipped in #5. Recorded here because the rest of the plan rests on it,
not because there is work left.

- `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` read
  from the environment. With `DEBUG=false` and no key, the process stops
  at boot rather than serving with a key from the repo.
- `SECURE_HSTS_SECONDS` a year, `SECURE_SSL_REDIRECT=False` because
  Caddy already redirects, `SESSION_COOKIE_SECURE` and
  `CSRF_COOKIE_SECURE` on whenever `DEBUG` is off.
- `security.W008` silenced, with the reason in the file: Django
  redirecting as well would loop unless told to trust a proxy header.
- WhiteNoise in the middleware directly after `SecurityMiddleware`.
- SQLite `OPTIONS`: `journal_mode=WAL`, `synchronous=NORMAL`,
  `transaction_mode=IMMEDIATE`.
- `poe check-deploy` runs `manage.py check --deploy --fail-level WARNING`
  against production-shaped settings, and `poe qa` runs it, so CI fails
  on a regression.

The environment variables the box has to supply, all of them read in
`src/config/settings.py`:

| Variable | Value on the VPS |
|----------|------------------|
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | 64 random bytes, generated on the box |
| `DJANGO_ALLOWED_HOSTS` | the domain |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://` + the domain |
| `DJANGO_DB_PATH` | `/var/lib/crm-jobs/db.sqlite3` |
| `DJANGO_HSTS_SECONDS` | unset once the certificate is settled; lower it while it is not |

## 6. Phase 2 — The files in `deploy/`

Secrets never in the repo. The `Caddyfile` carries a placeholder hash
and the real one is edited in on the box.

**`deploy/crm-jobs.service`**

gunicorn, 2 workers, bound to `127.0.0.1:8000`, running as an
unprivileged `crm` user, `EnvironmentFile=/etc/crm-jobs/env`,
`WorkingDirectory=/srv/crm-jobs`, `Restart=on-failure`.

Two workers rather than one because a slow request should not block the
board from loading, and rather than four because the box is small and
SQLite takes one writer at a time regardless.

**`deploy/Caddyfile`**

```
crm.example.com {
    basic_auth {
        fritz <bcrypt hash from `caddy hash-password`>
    }
    reverse_proxy 127.0.0.1:8000
}
```

**`deploy/crm-jobs-backup.service`** and **`deploy/crm-jobs-backup.timer`**

The daily backup, §9.

**`gunicorn` is a dependency now.** It is named in plan 001 §5 and in
AGENTS.md but is not in `pyproject.toml` — the app has only ever run
under `runserver`. Adding it is part of this phase, not an oversight to
discover on the box.

## 7. Phase 3 — The deploy workflow

`.github/workflows/deploy.yml`, on push to `main`, `needs:` the existing
`qa` job in `ci.yml`, so a red build never deploys.

```
ssh deploy@host:
  cd /srv/crm-jobs
  git pull --ff-only
  uv sync --frozen
  uv run manage.py migrate
  uv run manage.py collectstatic --noinput
  sudo systemctl restart crm-jobs
```

- The deploy user is `deploy`, not root. Its sudoers entry permits
  exactly `systemctl restart crm-jobs` and nothing else.
- The checkout on the box is owned by `deploy`; the service runs as
  `crm`, which needs read on `/srv/crm-jobs` and write on
  `/var/lib/crm-jobs` and nowhere else.
- `--ff-only`, so a box someone has committed on fails the deploy
  instead of merging on a server at two in the morning.
- `uv sync --frozen`, so the lockfile is what is installed and a deploy
  cannot resolve a different version from CI.
- Secrets for the SSH key and host go in repository secrets.

`ci.yml` currently triggers on `push` to `main` and on pull requests. It
stays as it is; `deploy.yml` is a second workflow that waits on it
rather than a job appended to it, so a failed deploy never reopens a
question about whether the tests passed.

## 8. Phase 4 — Provision the box

Done by hand, once, and written down here as it is done so the next box
is not archaeology.

- Users: `crm` (runs the app, no shell), `deploy` (pulls, no sudo beyond
  the one restart).
- Directories: `/srv/crm-jobs` owned by `deploy`, `/var/lib/crm-jobs`
  owned by `crm`, `/etc/crm-jobs` root-owned with `env` at 0600 readable
  by `crm`.
- Python 3.14 via `uv`, the same version as `requires-python` and the CI
  matrix, so the three cannot drift.
- Firewall: 80, 443 and SSH. Port 8000 is never exposed — Caddy reaches
  it over loopback.
- Caddy installed from its own repository, `caddy hash-password` run on
  the box, the hash pasted into `/etc/caddy/Caddyfile`.
- DNS `A` record before the first `caddy reload`, or the certificate
  request fails and Let's Encrypt starts counting attempts.

## 9. Phase 5 — Backups, and a restore that has been done

This gates retiring the sheet. Until a restore has been performed, the
SQLite file is the only copy of the data and the sheet is the backup.

- systemd timer, daily:
  `sqlite3 /var/lib/crm-jobs/db.sqlite3 ".backup /var/backups/crm-$(date +%F).sqlite3"`
- `.backup` rather than `cp`: it is safe against a concurrently written
  WAL database, and `cp` is not.
- Keep 14 days on the box, push off-box with restic or rsync. A backup
  that only exists on the machine that can die is not a backup.
- Restore once, by hand, into a scratch path, and open the board against
  it. Note in `docs/` that it was done, and when.

## 10. What is testable, and what is not

Most of this is configuration, and TDD does not apply to a unit file.
Saying so up front, so nobody either skips the checks that do exist or
invents tests that assert nothing.

Machine-checkable, and worth adding to CI:

- `systemd-analyze verify deploy/crm-jobs.service` — catches a typo in a
  directive name, which is otherwise found by a failed restart.
- `caddy validate --config deploy/Caddyfile` — same, for the proxy.
- `poe check-deploy`, already in `poe qa`, which is what stops a
  settings regression reaching the box.

Checked by hand, once, and recorded:

- The site answers over HTTPS behind the password prompt.
- A push to `main` lands on the box and the board reflects it.
- The restore in §9.

Not checked at all, deliberately: nothing here asserts that the VPS is
reachable from CI. A deploy that fails says so by failing.

## 11. Risks

| Risk | Mitigation |
|------|-----------|
| SQLite file is the only copy of the data | §9, and it gates retiring the sheet |
| Deploy clobbers the database | Data lives outside the checkout; the deploy runs as a user with no write access to `/var/lib/crm-jobs` |
| Shared basic-auth credential, no logout | Accepted for one user; the gate is swappable without touching the app |
| A bad migration reaches production | CI runs the suite against the migrations; the daily backup is the way back |
| Let's Encrypt rate limits during setup | Get DNS right before the first reload; use the staging endpoint while fiddling |
| SQLite writer lock under concurrent writes | WAL + `IMMEDIATE`; a single user will not reach it |

## 12. Done when

- A push to `main` lands on the VPS with no hand step, and the board
  answers over HTTPS behind the password prompt.
- `/var/lib/crm-jobs/db.sqlite3` survives a deploy, demonstrably.
- A backup has been restored by hand and the fact is written in `docs/`.
- `deploy/` holds the unit, the `Caddyfile` and the timer, with no real
  credential in any of them.

Retiring the GAS app — exporting the sheet, deleting `clasp/` — is not
here. It waits on this plan and on 003, and it is #11.
