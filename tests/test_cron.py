"""Cron expression parsing and matching, plus CronStore persistence."""

from __future__ import annotations

from datetime import datetime

import pytest

from qtxterm.cron import CronError, CronExpression, CronJob, CronStore


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


def test_every_minute_matches_everything() -> None:
    every = CronExpression.parse("* * * * *")

    assert every.matches(at("2026-08-16 00:00"))
    assert every.matches(at("2026-08-16 13:37"))


def test_a_fixed_time_matches_only_then() -> None:
    nine_am = CronExpression.parse("0 9 * * *")

    assert nine_am.matches(at("2026-08-16 09:00"))
    assert not nine_am.matches(at("2026-08-16 09:01"))
    assert not nine_am.matches(at("2026-08-16 10:00"))


def test_steps_lists_and_ranges() -> None:
    expression = CronExpression.parse("*/15 9-17 * * 1-5")

    assert expression.minutes == frozenset({0, 15, 30, 45})
    assert expression.hours == frozenset(range(9, 18))
    assert expression.days_of_week == frozenset({1, 2, 3, 4, 5})

    lists = CronExpression.parse("0,30 8,12,18 1,15 * *")
    assert lists.minutes == frozenset({0, 30})
    assert lists.hours == frozenset({8, 12, 18})
    assert lists.days_of_month == frozenset({1, 15})


def test_a_range_can_carry_a_step() -> None:
    assert CronExpression.parse("0-30/10 * * * *").minutes == frozenset({0, 10, 20, 30})


def test_sunday_is_both_zero_and_seven() -> None:
    """Real cron accepts either, and people write both."""
    zero = CronExpression.parse("0 12 * * 0")
    seven = CronExpression.parse("0 12 * * 7")
    sunday = at("2026-08-16 12:00")  # a Sunday

    assert sunday.weekday() == 6
    assert zero.matches(sunday)
    assert seven.matches(sunday)
    assert seven.days_of_week == zero.days_of_week


def test_weekday_numbering_follows_cron_not_python() -> None:
    monday_only = CronExpression.parse("0 12 * * 1")

    assert monday_only.matches(at("2026-08-17 12:00"))  # Monday
    assert not monday_only.matches(at("2026-08-16 12:00"))  # Sunday


def test_day_of_month_and_day_of_week_are_ored_when_both_restricted() -> None:
    """Cron's own oddity, kept because schedules in the wild depend on it: with
    both day fields restricted, either matching is enough."""
    expression = CronExpression.parse("0 12 13 * 5")  # the 13th, or any Friday

    assert expression.matches(at("2026-08-13 12:00"))  # the 13th, a Thursday
    assert expression.matches(at("2026-08-21 12:00"))  # a Friday, not the 13th
    assert not expression.matches(at("2026-08-20 12:00"))  # neither


def test_only_one_day_field_restricted_must_match() -> None:
    dom = CronExpression.parse("0 12 13 * *")
    assert dom.matches(at("2026-08-13 12:00"))
    assert not dom.matches(at("2026-08-14 12:00"))

    dow = CronExpression.parse("0 12 * * 5")
    assert dow.matches(at("2026-08-21 12:00"))  # Friday
    assert not dow.matches(at("2026-08-20 12:00"))


@pytest.mark.parametrize(
    "text, problem",
    [
        ("* * * *", "5 fields"),
        ("* * * * * *", "5 fields"),
        ("60 * * * *", "between"),
        ("* 24 * * *", "between"),
        ("* * 0 * *", "between"),
        ("* * * 13 *", "between"),
        ("bad * * * *", "not a number"),
        ("*/0 * * * *", "step"),
        ("30-10 * * * *", "backwards"),
        ("0,, * * * *", "empty"),
    ],
)
def test_bad_expressions_say_what_is_wrong(text: str, problem: str) -> None:
    with pytest.raises(CronError, match=problem):
        CronExpression.parse(text)


def test_next_run_finds_the_following_minute() -> None:
    expression = CronExpression.parse("*/15 * * * *")

    assert expression.next_run(at("2026-08-16 10:05")) == at("2026-08-16 10:15")
    # Strictly after: a schedule matching *now* still returns the next one.
    assert expression.next_run(at("2026-08-16 10:15")) == at("2026-08-16 10:30")


def test_next_run_crosses_days_and_months() -> None:
    yearly = CronExpression.parse("0 3 1 1 *")

    assert yearly.next_run(at("2026-08-16 10:00")) == at("2027-01-01 03:00")


def test_next_run_gives_up_on_a_date_that_never_comes() -> None:
    """February 31st parses fine and can never happen; the answer is None
    rather than a search that never ends."""
    impossible = CronExpression.parse("0 0 31 2 *")

    assert impossible.next_run(at("2026-08-16 10:00")) is None


def test_jobs_round_trip_through_the_store(tmp_path) -> None:
    store = CronStore(path=tmp_path / "cron.json")
    store.add(CronJob(name="Nightly", expression="0 2 * * *", preset_name="Backup"))

    reopened = CronStore(path=tmp_path / "cron.json")

    assert len(reopened.jobs) == 1
    assert reopened.jobs[0].name == "Nightly"
    assert reopened.jobs[0].preset_name == "Backup"
    assert reopened.jobs[0].enabled is True


def test_saving_emits_changed(qtbot, tmp_path) -> None:
    store = CronStore(path=tmp_path / "cron.json")

    with qtbot.waitSignal(store.changed):
        store.add(CronJob(name="a", expression="* * * * *", preset_name="p"))


def test_a_missing_file_is_an_empty_list_not_an_error(tmp_path) -> None:
    assert CronStore(path=tmp_path / "nothing.json").jobs == []


def test_unknown_fields_in_the_file_are_ignored(tmp_path) -> None:
    """A file written by a later version should cost you a field, not the app."""
    path = tmp_path / "cron.json"
    path.write_text(
        '[{"name": "a", "expression": "* * * * *", "preset_name": "p", '
        '"enabled": true, "from_the_future": 1}]',
        encoding="utf-8",
    )

    store = CronStore(path=path)

    assert len(store.jobs) == 1
    assert store.jobs[0].name == "a"
