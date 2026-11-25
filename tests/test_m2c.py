"""Slice 2c: a repeating schedule made with an old start waits for its grid. Until now making one whose start was
past sent a message at once (to make up for what was "missed"), while changing a schedule's times waited for the next
time of the grid. Making now follows changing; a start within the last minute still counts as now.

    python -m pytest tests/test_m2c.py -q
"""
from __future__ import annotations

import datetime
import time

import pytest

from test_m1b import build_world, until
from test_m1c2 import ENVS, change, made, posted, remove, schedule, schedules

UTC = datetime.timezone.utc
HOUR = datetime.timedelta(hours=1)


@pytest.fixture(scope="module")
def w(tmp_path_factory):
    world = build_world(tmp_path_factory.mktemp("data2c"), ENVS)
    yield world
    world.srv.stop()


def iso(at: datetime.datetime) -> str:
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


def at(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).replace(microsecond=0)


def test_a_repeating_schedule_made_with_an_old_start_waits_for_its_grid(w):
    now = datetime.datetime.now(UTC).replace(microsecond=0)
    old = now - 2.5 * HOUR
    sch = made(schedule(w.alice, text="on the grid [g1]", every_s=3600, start_at=iso(old)))
    assert at(sch["next_at"]) == old + 3 * HOUR, "the first time of its grid that is not past"
    time.sleep(1.5)
    assert posted(w.alice, "[g1]") == [], "nothing is sent at once"
    assert at(schedules(w.alice)[sch["id"]]["next_at"]) == old + 3 * HOUR

    # Changing its times follows the same rule (it did before).
    older = now - 5.25 * HOUR
    assert at(made(change(w.alice, sch["id"], start_at=iso(older)))["next_at"]) == older + 6 * HOUR
    assert remove(w.alice, sch["id"]).status_code == 200

    # A start within the last minute is now: it runs at once and is then on its grid.
    just = datetime.datetime.now(UTC).replace(microsecond=0) - datetime.timedelta(seconds=20)
    sch = made(schedule(w.alice, text="from now [g2]", every_s=3600, start_at=iso(just)))
    assert until(lambda: posted(w.alice, "[g2]"), 6), "it runs at once"
    assert len(posted(w.alice, "[g2]")) == 1
    assert at(schedules(w.alice)[sch["id"]]["next_at"]) == just + HOUR
    assert remove(w.alice, sch["id"]).status_code == 200
