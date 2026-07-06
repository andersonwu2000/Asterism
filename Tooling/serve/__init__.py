"""Asterism serve — the localhost web UI's engine-side API.

Charter (docs/internal/frontend_design.md) iron rules enforced here:
DB reads go through `db.connect_readonly` only; every write goes
through an existing CLI/state chokepoint function; the UI speaks HTTP
to this process and nothing else.
"""
