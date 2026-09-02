"""DB access facade — re-exports every public (and externally-referenced
private) symbol from the `Tooling/state/db/` package so `from ..state import
db` / `from ..state.db import X` / `db.insert_goal` call sites are unaffected
by the 2026-08-29 split of the former `db.py` monolith into per-section
modules (core/paths/goals/problems/reach/strategies/pipelines/queue/deaths/
library)."""
from __future__ import annotations

# core.py — DB_PATH, SCHEMA, connect/init_schema, review+signoff snapshots
from .core import (
    DB_PATH,
    SCHEMA,
    now,
    _CURRENT_USER_VERSION,
    connect,
    set_review_snapshot,
    get_review_snapshot,
    set_ingest_signoff,
    get_ingest_signoff,
    SchemaBehind,
    connect_readonly,
    init_schema,
    SCOPE_SEP,
    scope_names,
    scope_sql,
    scope_matches,
)

# paths.py — problem slug <-> filesystem path mapping
from .paths import (
    problem_dir,
    slug_from_problem_dir,
    classify_cited_slug,
)

# goals.py — Goal helpers
from .goals import (
    insert_goal,
    get_goal,
    set_alias_target,
    aliases_pointing_at,
    update_goal_status,
    set_integrity_verified,
    unverified_proved_roots,
    set_goal_detached,
    mark_deliverable,
    bind_paper,
    unbind_paper,
    paper_bindings,
    scholar_fetch_count,
    top_group_id,
    deliverables,
    set_ingest_signoff_pending,
    problem_ingest_signoff_pending,
    goal_by_slug,
    set_inject_outcome_detail,
    set_inject_decision_produced_goal,
    set_inject_decision_outcome_detail,
    propagate_inject_outcome_from_goal,
    set_inject_decision_produced_strategy,
    propagate_inject_outcome_from_strategy,
)

# problems.py — Phase 2 problem-level Strategist state
from .problems import (
    set_problem_bootstrap_done,
    set_problem_ingested,
    problem_ingested,
    all_problems_ingested,
    set_problem_strategist_directive,
    update_problem_last_strategist_at,
    update_problem_last_routine_at,
    unacknowledged_inject_batches,
    problems_needing_t1,
    groups_needing_t1,
    group_routine_due,
    problems_with_pending_review,
    null_inject_redispatch_specs,
    queue_has_decision,
    _subtree_has_live_frontier,
    BATCH_DECISION_KINDS,
    propagate_inject_outcome_from_group,
    has_active_inflight_inject,
    has_live_inflight_inject,
    open_batch_steps,
    batch_has_running_step,
    goal_reviewed_at_current_attempts,
    is_confirm_shelve_parked,
    is_human_parked,
    is_problem_stalled,
    is_group_stalled,
    groups_stalled,
    problem_quiet,
    problems_stalled,
    problem_has_awaiting_human,
    scoped_problem_names,
    dispatchable_open_goals,
    increment_goal_attempts,
)

# bench.py — the operator bench flag (v47), read + write in one home
from .bench import (
    problem_benched,
    set_benched,
)

# reach.py — Phase 6 alive-reachability CTE
from .reach import (
    ALIVE_CTE_GLOBAL,
    ALIVE_CTE_PER_PROBLEM,
    goals_reachable_excluding,
    open_goals,
    root_proved,
)

# strategies.py — Strategy helpers
from .strategies import (
    insert_strategy,
    update_strategy_scratch_path,
    mark_other_strategies_superseded,
    link_subgoal,
    update_strategy_status,
    maybe_enqueue_inject_batch_done,
    reconcile_settled_inject_outcomes,
    delete_strategy,
    strategies_ready_for_verify,
)

# pipelines.py — Pipeline helpers
from .pipelines import (
    record_pipeline_start,
    finish_pipeline,
    is_in_queue,
    queue_count,
    descendant_ids, strict_ancestor_ids, strict_ancestor_slugs,
    queue_size,
)

# queue.py — Queue helpers
from .queue import (
    enqueue,
    pop_queue,
    complete_queue_row,
    unclaim_queue_row,
    release_own_leases,
    release_expired_leases,
    flush_queue_kind,
    queue_contains,
)

# deaths.py — Dead attempt helpers
from .deaths import (
    record_dead_attempt,
    recent_dead_attempts,
)

# library.py — library_decls + Library index
from .library import (
    upsert_library_decl,
    set_library_verdict,
    set_library_classification,
    mark_library_migrated,
    mark_library_cleaned,
    set_library_renamed,
    mark_library_bridged,
    clear_library_bridged,
    problem_library_bridged,
    bridged_library_index,
    library_decl_names,
    set_library_signature,
    librarian_fail_counts_all,
    set_librarian_fail_count,
    clear_librarian_fail_count,
    clear_librarian_fail_counts_for_problem,
    library_decls_for,
)
