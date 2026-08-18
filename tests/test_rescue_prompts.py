"""The parting-note channel must name a pen that writes (2026-08-18).

g8133: the dying worker had already found the right four-block cut and
wrote it to `_progress.md` — through codex's native `apply_patch`,
whose first write of a session stalls on the sandbox warm-up (#219),
so the note never landed. Five timeout retries across g8038/g8133 all
show `note=no` in dead_attempts.artifacts: every retry re-walked the
same 30-minute dead end. Each rescue template that asks for the note
must point MCP-only seats at `write_file` (the #219 bypass), or the
heartbeat gate's "decline with the cut you would make" hands back a
cut through a channel that drops it.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"

_RESCUE_TEMPLATES = (
    "_shared/force_progress.md",
    "_shared/fresh_rescue_stage2.md",
    "_shared/fresh_rescue_stage2_mint.md",
    "backward/backward_postmortem.md",
)


def test_every_rescue_template_names_write_file() -> None:
    for rel in _RESCUE_TEMPLATES:
        text = (_PROMPTS / rel).read_text(encoding="utf-8")
        assert "write_file" in text, (
            f"{rel} asks for a parting note without naming `write_file` "
            f"— on MCP-only seats the note dies in apply_patch's "
            f"first-write stall (#219, g8133)")
