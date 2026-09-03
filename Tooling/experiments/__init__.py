"""Operator experiments — replay tooling that never touches a live run.

`timetravel`: rewind a COPY of the DB to a cutoff instant and build a
scratch workspace around it, so a historical Strategist / judge wake can
be re-run with today's prompts and seats (2026-08-30, the fin10 replay).
"""
from __future__ import annotations

import json
import sys


def print_json(payload) -> None:
    """Dump a runner's result blob to stdout, whatever the console's
    codec is.

    Every runner here ends with this dump, and it runs AFTER the replay
    has committed and written its own JSON artefact — so a codec that
    cannot spell the payload must cost characters, not the run. A cp950
    console met `∉` in an Inject's Lean prose and killed arm C run 1
    (2026-09-03) on its very last line, with everything already on disk.

    Round-tripping through the console's own encoding with `replace`
    substitutes exactly the characters it cannot spell and leaves the
    rest — the operator still reads the blob, and the file beside it is
    always the faithful copy.
    """
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    stream = sys.stdout
    enc = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(enc, "replace").decode(enc, "replace"))
    stream.write("\n")
    stream.flush()
