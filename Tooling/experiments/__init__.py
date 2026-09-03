"""Operator experiments — replay tooling that never touches a live run.

`timetravel`: rewind a COPY of the DB to a cutoff instant and build a
scratch workspace around it, so a historical Strategist / judge wake can
be re-run with today's prompts and seats (2026-08-30, the fin10 replay).
"""
from __future__ import annotations


def harden_console() -> None:
    """Force UTF-8 console I/O, the way the CLI's own entry point does.

    Each runner in this package is an ENTRY POINT into the very pipeline
    `asterism run` enters — and the CLI calls `_force_utf8_io` before it
    runs anything, precisely because a framework print carries Lean
    prose (`∃`, `∉`) and status glyphs (`⚠`) that a locale-default
    Windows console cannot spell. These runners skipped that step, so
    the same UnicodeEncodeError arrived one layer in: arm C run 2 of the
    push experiment (2026-09-03) died at a length warning inside the
    wake, with its proposal written, its Adversary round spent and
    nothing committed — the incident `_force_utf8_io` already exists to
    prevent (BT 2026-05-29 g3410).

    Entering the pipeline means entering it the way the CLI does; the
    import is deferred so it resolves against the workspace the runner
    has already put on `sys.path`.
    """
    from ..core.cli import _force_utf8_io
    _force_utf8_io()
