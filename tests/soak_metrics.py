"""Process-level health metrics for the soak test.

Deliberately dependency-free (ctypes, not psutil): a soak test that only
runs when an extra package happens to be installed is a soak test nobody
runs. Every reading degrades to 0 rather than raising, so an unsupported
platform loses a signal instead of the whole test.
"""

from __future__ import annotations

import ctypes
import gc
import os
import sys
import time
from dataclasses import dataclass

_GDI_OBJECTS = 0
_USER_OBJECTS = 1


def _current_process():
    """The process pseudo-handle, as a real HANDLE.

    Without the explicit restype ctypes hands back a C int, which on 64-bit
    Windows is silently truncated when passed as a HANDLE - every call then
    fails and every metric reads zero, which looks exactly like a perfectly
    healthy process.
    """
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    return kernel32.GetCurrentProcess()


def rss_bytes() -> int:
    """Resident set size - the number that matters for "is it leaking?"."""
    if sys.platform == "win32":

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_uint32),
                ("PageFaultCount", ctypes.c_uint32),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_info.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
        if not get_info(_current_process(), ctypes.byref(counters), counters.cb):
            return 0
        return int(counters.WorkingSetSize)

    try:
        with open(f"/proc/{os.getpid()}/statm", encoding="utf-8") as handle:
            return int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        return 0


def _gui_resources(kind: int) -> int:
    """GDI/USER handle count.

    Worth watching separately from memory: Windows caps these per process
    (10k by default), and a GUI that leaks a handle per window it opens dies
    of that limit long before it runs out of memory - as a refusal to draw
    anything new, which reads as the app "going weird" after a day.
    """
    if sys.platform != "win32":
        return 0
    get_resources = ctypes.windll.user32.GetGuiResources
    get_resources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    get_resources.restype = ctypes.c_uint32
    return int(get_resources(_current_process(), kind))


def gdi_objects() -> int:
    return _gui_resources(_GDI_OBJECTS)


def user_objects() -> int:
    return _gui_resources(_USER_OBJECTS)


def open_handles() -> int:
    """Every kernel handle the process holds: files, pipes, events, threads.

    A PTY that is closed but not reaped shows up here before it shows up
    anywhere else.
    """
    if sys.platform != "win32":
        try:
            return len(os.listdir(f"/proc/{os.getpid()}/fd"))
        except OSError:
            return 0
    count = ctypes.c_uint32()
    get_count = ctypes.windll.kernel32.GetProcessHandleCount
    get_count.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    if not get_count(_current_process(), ctypes.byref(count)):
        return 0
    return int(count.value)


@dataclass(frozen=True)
class Sample:
    """One reading of everything that could drift over a long session."""

    cycle: int
    seconds: float
    rss: int
    gdi: int
    user: int
    handles: int
    py_objects: int
    widgets: int
    terminals: int
    latency_ms: float

    def line(self) -> str:
        return (
            f"cycle {self.cycle:>4}  "
            f"{self.seconds:>7.1f}s  "
            f"rss {self.rss / 1e6:>8.1f}MB  "
            f"gdi {self.gdi:>5}  user {self.user:>5}  handles {self.handles:>5}  "
            f"objs {self.py_objects:>8}  widgets {self.widgets:>5}  "
            f"terms {self.terminals:>3}  lag {self.latency_ms:>6.1f}ms"
        )


def collect(
    cycle: int, started: float, widgets: int, terminals: int, latency_ms: float
) -> Sample:
    # Collected before sampling so a cycle's garbage is charged to that
    # cycle, not blamed on the next one.
    gc.collect()
    return Sample(
        cycle=cycle,
        seconds=time.monotonic() - started,
        rss=rss_bytes(),
        gdi=gdi_objects(),
        user=user_objects(),
        handles=open_handles(),
        py_objects=len(gc.get_objects()),
        widgets=widgets,
        terminals=terminals,
        latency_ms=latency_ms,
    )


def _slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of ys against xs.

    A fitted slope, not last-minus-first: the working set wobbles by tens of
    megabytes as Chromium's caches fill and drain, and a single noisy final
    reading should not be able to declare a leak (or hide one).
    """
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def growth_per_cycle(samples: list[Sample], value) -> float:
    """Growth of `value` per cycle of work - the unit the thresholds use.

    Deliberately not per *hour*: the workload is measured in cycles, and a
    per-hour figure fitted over a decelerating curve shrinks the longer you
    measure (4241 MB/h over 30s, 95 MB/h over 8 minutes, for the same
    perfectly healthy process). Per-cycle growth is independent of how long
    the run happened to be, so one threshold works for a 20-cycle smoke test
    and a 24-hour soak alike.
    """
    return _slope([float(s.cycle) for s in samples], [float(value(s)) for s in samples])


def growth_per_hour(samples: list[Sample], value) -> float:
    """Per-hour growth, for the report only.

    Useful for answering "what would a day of this look like?", and
    misleading as a pass/fail - see growth_per_cycle.
    """
    if len(samples) < 2:
        return 0.0
    xs = [s.seconds for s in samples]
    ys = [float(value(s)) for s in samples]
    return _slope(xs, ys) * 3600


def write_csv(path, samples: list[Sample]) -> None:
    """Dump every sample, so a long run leaves a curve behind to look at.

    The pass/fail answers "is it leaking?"; the curve answers "is it
    plateauing, and when?", which is the question you actually have at 3am
    on hour nine of a soak.
    """
    import csv
    import dataclasses

    fields = [f.name for f in dataclasses.fields(Sample)]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        for sample in samples:
            writer.writerow([getattr(sample, name) for name in fields])
