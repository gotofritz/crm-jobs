"""Reading settings out of the environment — plan 001 §5, AGENTS.md "Data & Secrets"."""

import pytest

from config.env import MissingSettingError, as_bool, as_list, as_required


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", " yes ", "on"])
def test_as_bool_reads_the_usual_true_spellings(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    """A deploy script writes `1`, a human writes `true`; both have to mean the same."""
    monkeypatch.setenv("FLAG", raw)

    assert as_bool("FLAG", default=False) is True


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", " no ", "off"])
def test_as_bool_reads_the_usual_false_spellings(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    """The same spellings on the other side, so `DJANGO_DEBUG=0` turns DEBUG off."""
    monkeypatch.setenv("FLAG", raw)

    assert as_bool("FLAG", default=True) is False


@pytest.mark.parametrize("raw", ["", "   "])
def test_as_bool_falls_back_to_the_default_when_blank(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """An exported-but-empty variable is not an answer, so it does not count as one."""
    monkeypatch.setenv("FLAG", raw)

    assert as_bool("FLAG", default=True) is True


def test_as_bool_falls_back_to_the_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer checkout sets nothing and still gets a working machine."""
    monkeypatch.delenv("FLAG", raising=False)

    assert as_bool("FLAG", default=True) is True


def test_as_bool_refuses_anything_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DJANGO_DEBUG=maybe` must stop the process, not quietly pick a side."""
    monkeypatch.setenv("FLAG", "maybe")

    with pytest.raises(ValueError, match="FLAG"):
        as_bool("FLAG", default=False)


def test_as_list_splits_on_commas_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOWED_HOSTS arrives as one string and has to come back as hosts."""
    monkeypatch.setenv("HOSTS", "crm.example.com, www.example.com")

    assert as_list("HOSTS") == ["crm.example.com", "www.example.com"]


def test_as_list_drops_blank_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trailing comma is a typo, not an empty host that matches nothing."""
    monkeypatch.setenv("HOSTS", "crm.example.com,,")

    assert as_list("HOSTS") == ["crm.example.com"]


@pytest.mark.parametrize("raw", ["", "  ,  "])
def test_as_list_is_empty_when_it_says_nothing(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    """Empty means empty: Django's own checks decide whether that is allowed."""
    monkeypatch.setenv("HOSTS", raw)

    assert as_list("HOSTS") == []


def test_as_list_is_empty_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same answer when the variable was never exported at all."""
    monkeypatch.delenv("HOSTS", raising=False)

    assert as_list("HOSTS") == []


@pytest.mark.parametrize("raw", ["", "   "])
def test_as_required_stops_the_process_when_blank(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """A missing SECRET_KEY has to fail at boot, not on the first signed cookie."""
    monkeypatch.setenv("KEY", raw)

    with pytest.raises(MissingSettingError, match="KEY"):
        as_required("KEY")


def test_as_required_stops_the_process_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never exported is the same as exported empty."""
    monkeypatch.delenv("KEY", raising=False)

    with pytest.raises(MissingSettingError, match="KEY"):
        as_required("KEY")


def test_as_required_returns_the_value_it_was_given(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whitespace around a pasted value is not part of it."""
    monkeypatch.setenv("KEY", "  s3cret  ")

    assert as_required("KEY") == "s3cret"
