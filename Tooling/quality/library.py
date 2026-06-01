"""Library topic-hint parsing.

Historically this module also auto-promoted a proved root into
`Library/<Topic>/<problem>.lean` (a whole-root re-export). That promotion is
**retired** — Library-ization now goes through the per-decl Librarian pipeline
(`Tooling/pipeline/librarian.py`: dedup → classify → migrate → cleanup →
bridge). What remains is the small hint-parsing helper still used by the agent
Context.md builder to decide which `Library/<Topic>/INDEX.md` entries an agent
sees (`agent/context.py:_section_library_available`).
"""
from __future__ import annotations

import re

_LIBRARY_HINT_RE = re.compile(r"^Library\.([A-Za-z][A-Za-z0-9_]*)\.")


def topics_from_hints(hints: list[str]) -> list[str]:
    """All distinct `Library.<Topic>.*` topics in `hints` (order preserved).
    Used to filter which `Library/<Topic>/INDEX.md` entries the agent sees in
    Context.md."""
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        m = _LIBRARY_HINT_RE.match(h)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out
