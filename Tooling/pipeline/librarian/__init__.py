"""Librarian pipeline (classify -> migrate -> cleanup -> bridge).

Split out of the former 3.9k-line pipeline/librarian.py monolith into
concern submodules; this package re-exports the full public + test API
so `from ..pipeline import librarian; librarian.X` keeps working.
"""
from __future__ import annotations

from ._base import (  # noqa: F401
    ClassifyFile,
    ClassifyPlan,
    _load_json,
    CLASSIFY_FILE_LINE_BUDGET,
    MigrateResult,
    MigratedDecl,
    WORK_KINDS,
    _import_sort_key,
    _sorted_import_lines,
    _MechIntegrityError,
    _code_normalized,
)
from .astslice import (  # noqa: F401
    _COMPLEX_DECL_RE,
    _DECL_COMMENT_RE,
    _DECL_KW,
    _DECL_RE,
    _NS_RE,
    _DECL_KW_RE,
    _NOMINAL_KINDS,
    _END_RE,
    extract_decls,
    extract_decl_fq_name,
    extract_decl_kind,
    _library_module_of,
    _nominal_decl_src,
    _defs_decl_fqn,
    _DECL_HEAD_RE,
    _decl_signature,
    _variable_block_spans,
    _defs_decl_source,
    _defs_decl_namespace,
    _ns_is_operator_specified,
)
from .classify import (  # noqa: F401
    parse_classify,
    _decl_line_counts,
    verify_classify,
    _path_to_module,
    _find_cycle,
    _toposort_intra_file,
    _reorder_decls_by_intrafile_refs,
    _merge_file_sccs,
    _decl_usage,
    _plan_usage_and_canon,
    _scc_cross_file_edges,
    verify_merged_file_sizes,
    commit_classify,
    _merge_alias_map,
    _root_source,
)
from .gate import (  # noqa: F401
    _verbatim_nominal_ok,
    migrate_defeq_gate,
    _uses_sorry,
    migrate_commit_gate,
    _AX_DEP_RE,
    _AX_NONE_RE,
    _axiom_probe_text,
    _parse_axiom_diags,
    _warm_probe_verifier,
    _warm_olean_writer,
)
from .schedule import (  # noqa: F401
    file_dependency_graph,
    next_migrate_file,
    file_work_kind,
    ready_file_work,
    ready_cleanup_files,
    _harvested_decls,
    _affected_cone,
    _topo_files,
)
from .context import (  # noqa: F401
    _read_statement,
    _strategy_proofs_of,
    compile_librarian_context,
)
from .execute import (  # noqa: F401
    _inject_heartbeat_options,
    _MechAssembly,
    _reassemble,
    _extract_single_decl,
    _demote_to_hole,
    _merge_header,
    _hole_still_unfilled,
    _mechanical_migrate_file,
    _commit_migrated_file,
    _migrate_file_incremental,
    _run_migrate,
    _MIGRATE_PATHS_LOCK,
    _MIGRATE_PATHS_IN_FLIGHT,
    _run_migrate_locked,
    _NEEDS_UPSTREAM_RE,
    _parse_needs_upstream,
    _reopen_upstream_cascade,
    _decline_summary,
    _decline_or_reopen,
)
from .bridge import (  # noqa: F401
    _upsert_index_section,
    _drop_index_section,
    _INDEX_PREAMBLE,
    _write_library_index,
    _rederivation_prober,
    _commit_bridge,
    _bridge_probe_text,
    _run_bridge,
)
from .run import (  # noqa: F401
    run_librarian,
    _reachable_from_root,
    _run_keepall,
    _cleanup_scope_index,
    _advance_cleanup_decls,
    _run_cleanup,
    _classify_feedback_path,
    _classify_prior_plan_path,
    _classify_trap_budget,
    _run_structured,
)
