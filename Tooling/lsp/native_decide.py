"""The `native_decide` soft gate — one definition, every write channel.

`native_decide` proves through the `Lean.ofReduceBool` axiom, which the
commit axiom gate never whitelists (ruling 2026-08-18): a proof carrying
it cannot land, and the native compilation it triggers runs for minutes
outside the heartbeat budget — 133 of 1,000 worker reports in the
union_closed ring (2026-08-29) were that wait, paid before any gate
spoke. So the bill is shown BEFORE the write, once per content, and the
identical resend is the confirmation: not a hard block, a price tag.

The semantics live here and not in one of the callers because the
formalizer has TWO write channels and a gate on one of them is a gate
with a door beside it. `gateway/rpc.py::_native_decide_gate` holds the
set in its LSP session; `knowledge/workspace_query.py::run_write` has
no session at all (the MCP tools server is a separate process, and in
the shim one process serves many spawns), so its set is a sidecar in
the spawn's own attempts dir. Same regex, same words, same "asked once,
confirmed by the resend" — `hold` is where that behaviour is written
down.

A leaf on purpose: stdlib only, so the tools server can import it
without dragging in the gateway (whose package `__init__` builds an
HTTP server at import time).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

#: Word-bounded so a longer identifier that merely contains the token
#: does not trip it. `Tooling/state/programme.py` carries the same test
#: for the STRATEGIST's proposal notice, whose message is deliberately
#: different (prose that mentions the tactic plans nothing).
PATTERN = re.compile(r"\bnative_decide\b|Lean\.ofReduceBool")

#: What the agent is told, on either channel. It ends with the way out,
#: because a gate message that does not name a reachable action gets an
#: invented action instead.
TEACHING = (
    "This write uses `native_decide` (or `Lean.ofReduceBool`). It proves "
    "through the `Lean.ofReduceBool` axiom, which is NOT on the axiom "
    "whitelist — the commit gate rejects every such brick "
    "unconditionally (ruling 2026-08-18), so this proof cannot land. It "
    "also compiles natively: the check runs for minutes outside the "
    "heartbeat budget and the elaboration wall will kill it. What works: "
    "kernel `decide` on an instance small enough to reduce, `omega`/"
    "`simp` with the finite case split written out, or lift the heavy "
    "check into its own `new_<slug>.lean` as smaller bricks. — Resend "
    "this identical write to confirm and it is written to the file for "
    "diagnostics only; the commit gate still refuses it. Changing the "
    "content asks again."
)

#: The tools-server side's confirmed set, per spawn. Named like the
#: framework's other attempts-dir sidecars (`_audit_roots.json`,
#: `_parser_state.json`): leading underscore, JSON, never an agent
#: deliverable.
ASKED_FILE = "_native_decide_asked.json"


def content_key(content: str) -> str:
    return hashlib.sha1((content or "").encode("utf-8")).hexdigest()


def hold(content: str, confirmed: "set[str]") -> "str | None":
    """The teaching text to bounce back, or None to let the write land.

    Mutates `confirmed`: the first ask records the content, so the
    identical resend passes and a changed one asks again.
    """
    if not PATTERN.search(content or ""):
        return None
    key = content_key(content)
    if key in confirmed:
        return None
    confirmed.add(key)
    return TEACHING


def hold_write(attempts_dir: "Path | str", content: str) -> "str | None":
    """`hold` with the confirmed set kept in the spawn's attempts dir.

    Sidecar rather than process memory because the tools server has no
    session to hang it on and may be restarted under the spawn; the
    attempts dir is the spawn, so the file scopes itself. An unreadable
    or corrupt sidecar starts empty — one extra ask is the safe way to
    be wrong.
    """
    if not PATTERN.search(content or ""):
        return None
    p = Path(attempts_dir) / ASKED_FILE
    try:
        keys = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        keys = []
    confirmed = {str(k) for k in keys} if isinstance(keys, list) else set()
    msg = hold(content, confirmed)
    if msg is None:
        return None
    try:
        p.write_text(json.dumps(sorted(confirmed), indent=1),
                     encoding="utf-8")
    except OSError:
        # Nowhere to record the ask: let the write land rather than ask
        # forever. A gate that cannot remember must not become a wall.
        return None
    return msg
