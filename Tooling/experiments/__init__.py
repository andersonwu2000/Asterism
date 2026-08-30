"""Operator experiments — replay tooling that never touches a live run.

`timetravel`: rewind a COPY of the DB to a cutoff instant and build a
scratch workspace around it, so a historical Strategist / judge wake can
be re-run with today's prompts and seats (2026-08-30, the fin10 replay).
"""
