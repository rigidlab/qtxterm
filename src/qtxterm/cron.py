"""Cron schedules, evaluated in-process while the app is running.

Deliberately not a re-implementation of crond: there is no catch-up. A job
whose time passed while qtxterm was closed does not run at launch - see
SPEC.md. What is faithful is the *expression* syntax, because that is the
part people already know.

Five fields, standard order and ranges:

    minute (0-59)  hour (0-23)  day-of-month (1-31)  month (1-12)  day-of-week (0-6)

Each field is `*`, a number, a range `a-b`, a list of either, or any of those
with a `/step`. Day-of-week 0 and 7 both mean Sunday.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from pathlib import Path

import platformdirs

from qtxterm.config_store import ConfigStore

# (name, low, high) per field, in the order they are written.
_FIELDS = [
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day of month", 1, 31),
    ("month", 1, 12),
    ("day of week", 0, 7),
]

_MINUTE, _HOUR, _DOM, _MONTH, _DOW = range(5)

# How far ahead next_run() will look before giving up. A schedule like
# "30 4 31 2 *" (February 31st) can never match, and the alternative to a
# bound is a UI that hangs.
_SEARCH_LIMIT_DAYS = 366 * 4


class CronError(ValueError):
    """An expression that cannot be parsed, with a reason worth showing."""


def _parse_field(text: str, low: int, high: int, name: str) -> set[int]:
    values: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"empty value in the {name} field")

        step = 1
        if "/" in part:
            part, _, step_text = part.partition("/")
            try:
                step = int(step_text)
            except ValueError:
                raise CronError(
                    f"'{step_text}' is not a whole number of steps"
                ) from None
            if step < 1:
                raise CronError(f"step must be 1 or more in the {name} field")

        if part == "*":
            start, end = low, high
        elif "-" in part.lstrip("-"):
            start_text, _, end_text = part.partition("-")
            start, end = _as_int(start_text, name), _as_int(end_text, name)
        else:
            start = end = _as_int(part, name)
            if step > 1:
                # "5/15" is meaningless in cron; a step needs a range to walk.
                end = high

        if start > end:
            raise CronError(f"{start}-{end} is backwards in the {name} field")
        if start < low or end > high:
            raise CronError(
                f"{name} must be between {low} and {high}, got {start}-{end}"
            )

        values.update(range(start, end + 1, step))
    return values


def _as_int(text: str, name: str) -> int:
    try:
        return int(text.strip())
    except ValueError:
        raise CronError(
            f"'{text.strip()}' is not a number in the {name} field"
        ) from None


@dataclasses.dataclass(frozen=True)
class CronExpression:
    """A parsed five-field cron expression."""

    text: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]
    # Kept because the day-of-month/day-of-week rule below depends on whether
    # each was written as "*", not on which values it expanded to.
    dom_restricted: bool
    dow_restricted: bool

    @classmethod
    def parse(cls, text: str) -> CronExpression:
        parts = text.split()
        if len(parts) != 5:
            raise CronError(
                f"expected 5 fields (minute hour day-of-month month day-of-week), "
                f"got {len(parts)}"
            )

        parsed = [
            _parse_field(part, low, high, name)
            for part, (name, low, high) in zip(parts, _FIELDS)
        ]
        # 7 is Sunday too, and it is the same day as 0.
        days_of_week = parsed[_DOW]
        if 7 in days_of_week:
            days_of_week = (days_of_week - {7}) | {0}

        return cls(
            text=" ".join(parts),
            minutes=frozenset(parsed[_MINUTE]),
            hours=frozenset(parsed[_HOUR]),
            days_of_month=frozenset(parsed[_DOM]),
            months=frozenset(parsed[_MONTH]),
            days_of_week=frozenset(days_of_week),
            dom_restricted=parts[_DOM].strip() != "*",
            dow_restricted=parts[_DOW].strip() != "*",
        )

    def matches(self, moment: datetime) -> bool:
        """Whether `moment` (to the minute) is a firing time.

        The day rule is cron's own oddity, kept because people rely on it:
        when *both* day-of-month and day-of-week are restricted, a day
        matching either one counts. Restrict only one and it must match.
        """
        if moment.minute not in self.minutes or moment.hour not in self.hours:
            return False
        if moment.month not in self.months:
            return False

        # Python: Monday=0..Sunday=6. Cron: Sunday=0..Saturday=6.
        dow = (moment.weekday() + 1) % 7
        day_matches_dom = moment.day in self.days_of_month
        day_matches_dow = dow in self.days_of_week

        if self.dom_restricted and self.dow_restricted:
            return day_matches_dom or day_matches_dow
        if self.dom_restricted:
            return day_matches_dom
        if self.dow_restricted:
            return day_matches_dow
        return True

    def next_run(self, after: datetime) -> datetime | None:
        """The first firing time strictly after `after`, or None if never.

        Walks minute by minute, skipping a whole day at a time when the date
        cannot match - which is what makes "0 3 1 1 *" cheap to answer.
        """
        moment = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
        limit = after + timedelta(days=_SEARCH_LIMIT_DAYS)
        while moment <= limit:
            if not self._day_matches(moment):
                moment = (moment + timedelta(days=1)).replace(hour=0, minute=0)
                continue
            if moment.hour in self.hours and moment.minute in self.minutes:
                return moment
            moment += timedelta(minutes=1)
        return None

    def _day_matches(self, moment: datetime) -> bool:
        if moment.month not in self.months:
            return False
        dow = (moment.weekday() + 1) % 7
        day_matches_dom = moment.day in self.days_of_month
        day_matches_dow = dow in self.days_of_week
        if self.dom_restricted and self.dow_restricted:
            return day_matches_dom or day_matches_dow
        if self.dom_restricted:
            return day_matches_dom
        if self.dow_restricted:
            return day_matches_dow
        return True


@dataclasses.dataclass
class CronJob:
    """A schedule pointing at a preset, by name.

    By name rather than by index: presets are reordered and rewritten by
    their editor, and a job that silently starts running a different command
    because a list shifted would be a nasty way to find out. A name that no
    longer resolves is reported, not guessed at.
    """

    name: str
    expression: str
    preset_name: str
    enabled: bool = True
    # Optional, and used exactly as a preset's group is: jobs that share one
    # are nested under it in the menu. A trading setup ends up with a job per
    # feed per session, which is more than a flat list wants to hold.
    group: str | None = None

    def schedule(self) -> CronExpression:
        return CronExpression.parse(self.expression)


def default_cron_path() -> Path:
    return Path(platformdirs.user_config_dir("qtxterm", appauthor=False)) / "cron.json"


class CronStore(ConfigStore):
    """Loads/saves cron jobs as JSON, the same shape PresetStore uses."""

    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path or default_cron_path())
        self.jobs: list[CronJob] = []
        self.load()

    def _apply_missing(self) -> None:
        self.jobs = []

    def _apply_payload(self, raw: list) -> None:
        # Unknown keys are dropped rather than raising: a file written by a
        # later version should cost you a field, not the whole app.
        fields = {f.name for f in dataclasses.fields(CronJob)}
        self.jobs = [
            CronJob(**{k: v for k, v in item.items() if k in fields}) for item in raw
        ]

    def _build_payload(self) -> list:
        return [dataclasses.asdict(job) for job in self.jobs]

    def add(self, job: CronJob) -> None:
        self.jobs.append(job)
        self.save()

    def update(self, index: int, job: CronJob) -> None:
        self.jobs[index] = job
        self.save()

    def delete(self, index: int) -> None:
        del self.jobs[index]
        self.save()
