"""Writing a parsed export into the database — plan 003 §5, §7."""

from jobs.importer import database_for


def test_the_demo_flag_picks_the_demo_alias() -> None:
    """The whole of `--demo`: a database chosen by name, not a path mutated at runtime."""
    assert database_for(demo=True) == "demo"


def test_without_the_flag_the_live_database_is_written() -> None:
    """The default is the database the app itself runs on."""
    assert database_for(demo=False) == "default"
