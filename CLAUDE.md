# Asterism — Claude operator notes

Claude is the primary CLI operator here; the human user rarely runs
commands directly.

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
- Gemini free-tier quota exhausts as rc=0 + empty output;
  `gemini_cli.py` already detects this.
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

## Don't

- Push without explicit user instruction.
- Reintroduce model-name substring tier — write to `Asterism.yaml`.
- Add `run:` section to Manifest.md — Manifest is data only.
- Add `README.md` / quickstart unless asked.

## Updating

Record substantial changes in `docs/STATUS.md`. Update this file when
operator workflow changes (new subcommand, retired knob, new convention).
