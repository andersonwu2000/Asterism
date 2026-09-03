"""Read-side aggregation for the serve API.

Every function here takes a read-only connection (`db.connect_readonly`)
and returns JSON-shaped dicts. Status semantics are NEVER derived here
when a state-layer predicate exists (charter §1-3): stalled =
`db.problems_stalled`, awaiting_human = `db.problem_has_awaiting_human`
(batched via one SQL pass), sign-off = `problems.ingest_signoff_pending`.

─── Package facade (2026-08-28: data.py → data/, B3) ───────────────────

Move-only split along the file's own section breaks: `status.py` (the
status-chip derivation shared by board() and problem_detail()),
`edges.py` (citation-edge extraction + `problem_detail` itself, the
biggest single read), `timeline.py` (the Timeline event log, everything
from the file's own "Timeline" section onward: Programme reads,
goal/strategy detail, inbox/review/bridged-library-index), `library.py`
(the Library chapter: bridged-module parsing for the human-facing read,
plus the trailing telemetry/papers/file-read leaves that share no call
edge with anything above them). Every name below is re-exported so
`data.X` attribute access and `from Tooling.serve import data` both
keep working unchanged for every caller (`serve/app.py`, `serve/run.py`,
`serve/chat.py`, the test suite) and the two sites that bypass the
facade with a direct name import — `serve/app.py`'s lazy `from .data
import _stmt_head`, `tests/test_serve_run.py`'s `from
Tooling.serve.data import _context_preamble, _scan_library_file` — both
resolve through this same re-export.

One call-graph adjustment from the file's literal section boundaries:
the Programme-read cluster (`_group_clause`, `_programme_events`,
`_programme_rev`, `programme`) sat between `problem_detail` and the
"Timeline" section marker, but `problem_events` (Timeline side) and
`problem_detail` (edges side) both call into it, and it in turn calls
into the groups-tree cluster (`_top_group_id`, `groups_of`,
`group_card`, `_group_lineage`) that lives on the Timeline side — a
straight line-range split would have made `edges.py` and `timeline.py`
import from each other, an unresolvable cycle. The cluster moved into
`timeline.py` whole: `problem_events` and `_decision_events` already
consumed it locally there (and a Programme's revision history feeds
the Timeline read directly), so `timeline.py` ends up self-contained —
zero import from `edges.py` — and `edges.py`'s `problem_detail` reaches
it as one outward edge instead (`_disproof_links`, `_goal_signature`,
`_programme_events`, `_programme_rev`, `_top_group_id`, `groups_of`,
all imported from `.timeline`). `_link_kind_expr` (below) is the one
true cross-cutting helper — `edges.py`'s `_goal_docs`/`problem_detail`
and `timeline.py`'s `_goal_arguments`/`goal_detail`/`strategy_detail`
all call it — so it stays here in the package header rather than
picking a side.

Two modules joined later, both for the Project shell (HID §1.4):
`projects.py` (the Project cards behind `/api/projects` — the shelf's
live running / attention / last_event numbers) and `human_inbox.py`
(`inbox` + `inbox_count`, moved out of `timeline.py` when the Project
filter arrived — see that module's header for why it is not named
`inbox.py`).

A module-level `from .x import name` COPIES the binding, so the patch
target of a shared name is the CONSUMING module, not the defining one
— there are no recorded `monkeypatch.setattr(data, ...)` (or any alias
thereof) sites anywhere in the repo (verified 2026-08-28), so this
facade carries no split patch-target risk.
"""
from __future__ import annotations

import sqlite3


# ---------------------------------------------------------------------
# strategy_subgoals.link_kind (v44) — 'minted' if the strategy CREATED
# the sub-goal, 'cited' if it only reuses one that already existed.
#
# The engine has read this since v44 (state/programme.py, agent/
# context.py, state/transitions.py all filter on it) and the read side
# did not, so every consumer here treated a reuse as parenthood. On
# union_closed's `fin4_union_closed_d_trace_type_catalog` that is seven
# separate routes citing one lemma: seven solid limbs fanning across
# the sky, and the lemma itself dragged below all seven citers by the
# layering pass. The layout engine's own comment already forbade it
# for proof-file citations — "never hierarchy, a heavily cited def
# would otherwise drag half the sky under itself" — the data just was
# not reaching it.
#
# One expression, so a pre-v44 database (older workspace, restored
# backup) reads as all-minted instead of raising.
# ---------------------------------------------------------------------

def _link_kind_expr(conn: sqlite3.Connection) -> str:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(strategy_subgoals)")}
    return "link_kind" if "link_kind" in cols else "'minted'"


from .status import (
    _awaiting_set,
    _live_daemon_pid,
    _refine_chip,
    _status_chip,
    _working,
    board,
    last_event_map,
)
from .projects import project_events, project_rows, _running_problems
from .human_inbox import inbox, inbox_count
from .timeline import (
    _already_said,
    _asked_for,
    _attempt_events,
    _BRICKS_SHOWN,
    _charter_snippet,
    _CHARTER_SNIP,
    _decision_events,
    _DECISION_VERB,
    _disproof_links,
    _ev,
    _goal_arguments,
    _goal_signature,
    _goal_source,
    _group_clause,
    _group_lineage,
    _LANDED_OUTCOMES,
    _LIFE_RANK,
    _logged_transitions,
    _mtime_or,
    _MINT_READERS,
    _programme_events,
    _programme_rev,
    _programme_title,
    _SAME_ACT_SEC,
    _SETTLED,
    _SIG_CACHE,
    _TERMINAL_GOAL_STATES,
    _TO_STATUS_VERB,
    _transition_events,
    goal_detail,
    goal_workarea_draft,
    group_card,
    groups_of,
    library,
    problem_events,
    programme,
    review,
    signoff_with_seal,
    strategy_detail,
    _top_group_id,
)
from .verdict import programme_verdict
from .edges import (
    _CITE_RE,
    _cite_file_cache,
    _citation_edges,
    _comment_block,
    _goal_docs,
    _scan_proof_file,
    _USE_BLOCK_COMMENT_RE,
    _USE_NOISE_RE,
    _uses_name,
    problem_detail,
)
from .library import (
    _chapter_scan_cache,
    _context_preamble,
    _CTX_LINE_RE,
    _DECL_RE,
    _DOCSTRING_RE,
    _IMPORT_RE,
    _MODULE_DOC_RE,
    _scan_library_file,
    _scanned_library_file,
    _stmt_head,
    library_chapter,
    problem_papers_detail,
    read_problem_file,
    telemetry_usage,
)

# `library.py` (this facade name's submodule, the Library-chapter parser)
# and `library()` (the function — bridged-decls index, defined in
# timeline.py alongside `library_chapter`'s sibling reads) collide on
# this one name. Importing the `.library` submodule above makes CPython
# bind it as this package's own `library` attribute — a submodule import
# always shadows a same-named attribute on its parent, independent of
# import order elsewhere in this file — so the explicit `from .timeline
# import (..., library, ...)` above is not guaranteed to be the name's
# last writer. Reassert the function explicitly, once, so `data.library
# (conn)` keeps calling the read, not the module object (caught live:
# `_data.library(conn)` raised `TypeError: 'module' object is not
# callable` in `serve/app.py`'s `/api/library` route before this line).
from . import timeline  # noqa: E402 — explicit for the line below

library = timeline.library
