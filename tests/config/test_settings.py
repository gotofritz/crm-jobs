"""Settings that AGENTS.md and plan 001 §5 pin down, asserted rather than assumed."""

from pathlib import Path

from django.conf import settings


def test_sqlite_runs_in_wal_mode_with_immediate_transactions() -> None:
    """AGENTS.md "Data & Secrets": WAL + synchronous=NORMAL + IMMEDIATE (plan 001 §5)."""
    options = settings.DATABASES["default"]["OPTIONS"]

    assert "journal_mode=WAL" in options["init_command"]
    assert "synchronous=NORMAL" in options["init_command"]
    assert options["transaction_mode"] == "IMMEDIATE"


def test_the_database_file_sits_outside_the_code() -> None:
    """The SQLite file lives at the repository root locally, not inside `src/` (AGENTS.md).

    `DATABASES["default"]["NAME"]` is no use here: the test runner replaces it
    with an in-memory database, which is the point of `DATABASE_PATH`.
    """
    assert settings.DATABASE_PATH.name == "db.sqlite3"
    assert settings.DATABASE_PATH.parent == Path(settings.BASE_DIR).parent


def test_the_secret_key_does_not_come_from_the_repository() -> None:
    """Secrets come from the environment; what is left in the file is marked unusable."""
    assert settings.SECRET_KEY.startswith("django-insecure-")
    assert "3bzxztl" not in settings.SECRET_KEY


def test_django_never_redirects_to_https_itself() -> None:
    """Caddy terminates TLS and redirects one hop earlier (plan 001 §5), so W008 is silenced."""
    assert settings.SECURE_SSL_REDIRECT is False
    assert "security.W008" in settings.SILENCED_SYSTEM_CHECKS
