# Asterism — Claude operator notes

## Read first

1. `docs/STATUS.md` — canonical handoff (proved problems, recent commits,
   ablations, pending work).
2. `docs/architecture.md` for design.
3. `git log --oneline -15` for what landed since STATUS.

Verify against the current tree before relying on prior-session memory.

## CLI

| Goal | Command |
|---|---|
| Inspect a Problem | `python -m Tooling.cli status <p> [--json]` |
| Wipe a Problem | `python -m Tooling.cli reset <p>` |
| Pre-flight | `python -m Tooling.cli doctor` |
| Init a Problem | `python -m Tooling.cli init <p>` |
| Run daemon | `python -m Tooling.cli run` |
| List orphans | `python -m Tooling.cli prune --dry-run` |

Do not write ad-hoc `python -c "import sqlite3; ..."` or `rm Problems/<p>/proofs/...`
— `status` / `reset` cover both.

## Config

`Asterism.yaml` at repo root (optional). Resolution chain (see
architecture.md §10):

```
env  >  Asterism.yaml  >  legacy env  >  built-in default
```

Built-in `(builder_threshold, shelve_threshold) = (3, 8)` for
Sonnet/Opus. Weak-tier (Haiku / Flash / mini): write `(5, 10)` in
`Asterism.yaml` explicitly. No runtime model-name auto-detection.

## Recurring traps

- `claude --session-id` requires dashed UUID — use `str(uuid.uuid4())`,
  not `.hex`.
- `.attempts/<pid>/` is per-pipeline ephemeral. `rm -rf .attempts/`
  after killing daemon when zombies pile up; `doctor` warns at > 5.

## Testing

```
python -m pytest tests/ -q --deselect \
  tests/test_dedupe.py::test_batch_isdefeq_real_lake --deselect \
  tests/test_lemma_lookup.py::test_lookup_batch_real_lake
```

The two deselected need real `lake` cache; skip in normal regression.
Full suite < 5 s, must be 100 % green before any commit.

## Updating

Record substantial changes in `docs/STATUS.md`. Update this file when
operator workflow changes (new subcommand, retired knob, new convention).

---

This file lives under `docs/` (not at repo root as `CLAUDE.md`) so the
solver agents spawned by `Tooling/cli.py run` don't auto-load it into
their system prompt. STATUS.md links here for the next operator session.
