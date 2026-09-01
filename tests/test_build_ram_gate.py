"""#234 — cold builds join the RAM ledger (SP7 autopsy 2026-09-01).

A promotion-gate lean compile peaked at 3.7G on a 6.8G machine whose
budget modeled only worker slots and NL spawns: the build rode on top
of a fat idle slot and the desktop, swap (4G) filled to 100%, and the
box thrashed to a crawl. `build_threads_fit` SHRINKS thread counts but
a single-threaded heavy module still peaks multi-GB — thread shrinking
cannot cap a module-level peak. The lease counter is the chokepoint
every daemon-side `lake build` already passes through, so the RAM gate
lives there: refuse the lease while measured available RAM is under
the build's need, poke the idle-fat slot recycle, and let the client's
existing 409/poll loop wait it out."""
from __future__ import annotations

import pytest

import Tooling.core.ram_ledger as rl
from Tooling.lsp.gateway import elab


def test_build_need_gb_default_and_env(monkeypatch):
    monkeypatch.delenv("ASTERISM_BUILD_NEED_GB", raising=False)
    assert rl.build_need_gb() == pytest.approx(rl.BUILD_NEED_GB_DEFAULT)
    monkeypatch.setenv("ASTERISM_BUILD_NEED_GB", "5.5")
    assert rl.build_need_gb() == pytest.approx(5.5)


def test_build_lease_held_when_ram_short(monkeypatch):
    monkeypatch.delenv("ASTERISM_BUILD_NEED_GB", raising=False)
    monkeypatch.setattr(rl, "available_gb", lambda: 2.0)
    poked = []
    monkeypatch.setattr(elab, "_poke_idle_recycle", lambda: poked.append(1))
    assert elab.build_lease_acquire(4, "t-ram") is None
    assert poked, "a RAM-held lease must poke the idle-fat recycle"
    # lanes must NOT leak on a RAM refusal: with RAM back, a full grant
    monkeypatch.setattr(rl, "available_gb", lambda: 50.0)
    lease = elab.build_lease_acquire(2, "t-ram")
    assert lease is not None and lease["threads"] >= 1
    elab.build_lease_release(lease["token"])
