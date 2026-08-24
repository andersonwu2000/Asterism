The previous session was killed mid-think after exceeding the wall-clock budget. __LOG_NOTE__

All output files must be written into `__ATTEMPTS_DIR__/` — use absolute paths in your Write calls. The framework only reads files from there. On MCP-only seats use `write_file` for this — a blocked `apply_patch` loses the note.

Then ship ONE of the following — use what's already in the log:
(a) `__ATTEMPTS_DIR__/patch.lean` + `__ATTEMPTS_DIR__/new_<slug>.lean` stubs (`:= by sorry` ok)
(b) `__ATTEMPTS_DIR__/patch.lean` alone with a sorry-free direct proof (leaf-bypass)
(c) `__ATTEMPTS_DIR__/patch.lean` rewritten to PROVE the statement's negation, with `-- decline: disprove` above the theorem (the framework kernel-checks it — a bare claim of falsity terminates nothing)
(d) bail — write `__ATTEMPTS_DIR__/_progress.md` only, exit. No `patch.lean`. Capture in ≤200 words: shape converging to, sub-pieces with clear name+statement, the specific blocker, alternative direction (≤60 words).

Act now. __RESCUE_MIN__ minutes left.
