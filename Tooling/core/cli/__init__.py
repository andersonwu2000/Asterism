"""CLI: asterism init <p> | asterism run [--once] | asterism reset <p>
       | asterism status <p> [--json] | asterism prune [<p>] [--dry-run]
       | asterism library-verify [--no-build].

See docs/architecture.md.

Facade re-exporting every public (and externally-referenced private)
symbol from the `Tooling/core/cli/` package (task A3, 2026-08-28: the
former `cli.py` monolith split into `run.py` / `problems.py` /
`diagnose.py` / `maint.py` / `main.py` by command domain), so
`from ..core.cli import X` / `from ..core import cli; cli.X` / the
`asterism = "Tooling.core.cli:main"` console-script entry point are all
unaffected. `dispatcher`/`fsutil` are re-imported here (not just inside
the submodules) so `cli.dispatcher` stays reachable — tests monkeypatch
`cli.dispatcher.run` directly."""
from __future__ import annotations

from .. import dispatcher, fsutil

# run.py — daemon/run lifecycle: cmd_run, daemon_status/start/stop,
# cmd_daemon, cmd_serve, the log-tee + UTF-8 console setup.
from .run import (
    LOG_DIR,
    LOG_RETENTION_KEEP,
    _Tee,
    _daemon_in_flight,
    _daemon_live_pid,
    _daemon_start_lock,
    _force_utf8_io,
    _gateway_status_once,
    _hard_exit_after_fatal,
    _log_filename,
    _open_run_log,
    _read_exit_summary,
    _retain_recent_logs,
    _utc_log_stamp,
    _write_exit_summary,
    cmd_daemon,
    cmd_run,
    cmd_serve,
    daemon_start,
    daemon_status,
    daemon_stop,
    seat_banner,
)

# problems.py — problem lifecycle: cmd_init/init-batch/reset,
# init_problem/delete_problem/wipe_problem_rows chokepoints.
from .problems import (
    PROOFS_SWEEP_PATTERNS,
    _ROOT_STATEMENT_RE,
    _SORRY_BODY_RE,
    _WRAP_BODY_RE,
    _classify_root_body,
    _extract_root_statement,
    _reset_problem_files,
    _robust_rmtree,
    _robust_unlink,
    _soft_reset,
    cmd_init,
    cmd_init_batch,
    cmd_reset,
    delete_problem,
    init_problem,
    wipe_problem_rows,
)

# diagnose.py — health-check surfaces: status/doctor/library-verify/
# review/regress/knowledge-stats/drift-check/logs/config.
from .diagnose import (
    _library_consistency_findings,
    _status_payload,
    cmd_config,
    cmd_doctor,
    cmd_doctor_cloud,
    cmd_drift_check,
    cmd_knowledge_stats,
    cmd_library_verify,
    cmd_logs,
    cmd_regress,
    cmd_review,
    cmd_status,
)

# maint.py — remaining operational commands: reject / approve-ingest /
# reject-ingest / repin / charter / word / revive /
# library-backfill-declinfo / prune / paper-add / paper-index / kb-migrate.
from .maint import (
    _claude_login_email,
    _cmd_intent_value,
    _effective_library_flag,
    _find_reject_victims,
    _resolve_reject_target,
    _rewake_strategist,
    _signoff_record,
    cmd_approve_ingest,
    cmd_charter,
    cmd_kb_migrate,
    cmd_library_backfill_declinfo,
    cmd_paper_add,
    cmd_paper_index,
    cmd_prune,
    cmd_reject,
    cmd_reject_ingest,
    cmd_repin,
    cmd_revive,
    cmd_word,
)

# main.py — the asterism argparse CLI + cmd_* dispatch wiring.
from .main import main
