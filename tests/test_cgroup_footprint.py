"""The ledger's cgroup axis must not count reclaimable page cache as
pressure. 2026-08-29 flagship (4 OCPU / 24 GB, budget 19 GB): memory.current
11.4 GB = 2.0 GB anon + 8.6 GB file (6.0 GB mmapped .olean); the axis could
never go calm (needs < budget-12 = 7 GB), dispatch stayed PAUSED and the
outlet shed the pool to one worker with 20 GB available."""
from __future__ import annotations

from Tooling.core import ram_ledger as rl

GB = 2**30


def _write(tmp_path, current: int, stat: str | None):
    (tmp_path / "memory.current").write_text(f"{current}\n", encoding="utf-8")
    if stat is not None:
        (tmp_path / "memory.stat").write_text(stat, encoding="utf-8")
    return str(tmp_path)


def test_file_pages_are_excluded(tmp_path):
    d = _write(tmp_path, int(11.44 * GB),
               f"anon {int(2.05 * GB)}\nfile {int(8.56 * GB)}\n"
               f"file_mapped {int(6.0 * GB)}\nshmem 0\n")
    got = rl._cgroup_footprint_gb(d)
    assert abs(got - (11.44 - 8.56)) < 0.01


def test_missing_stat_falls_back_to_raw_current(tmp_path):
    d = _write(tmp_path, 5 * GB, None)
    assert rl._cgroup_footprint_gb(d) == 5.0


def test_missing_current_is_none(tmp_path):
    assert rl._cgroup_footprint_gb(str(tmp_path)) is None


def test_never_negative(tmp_path):
    d = _write(tmp_path, 1 * GB, f"file {3 * GB}\n")
    assert rl._cgroup_footprint_gb(d) == 0.0


def test_flagship_incident_goes_calm_after_fix(tmp_path):
    # With cache excluded the 2026-08-29 reading (2.9 GB) sits far below the
    # calm line (19 - 8 - 4 = 7 GB); with cache included (11.4 GB) it never did.
    d = _write(tmp_path, int(11.44 * GB), f"file {int(8.56 * GB)}\n")
    budget = 19.0
    calm_line = budget - rl.DispatcherLedger.PRESSURE_HEADROOM_GB - rl.DispatcherLedger.PRESSURE_RELEASE_SLACK_GB
    assert rl._cgroup_footprint_gb(d) < calm_line
    assert 11.44 > calm_line
