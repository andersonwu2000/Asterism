# Asterism — Claude operator notes

You (Claude) are the primary CLI operator for this repo; the human user
rarely runs commands directly. Follow the conventions below so each
session inherits the same workflow.

## First moves in a new session

1. `docs/STATUS.md` is the canonical handoff note. **Read it before
   anything else** — it carries proved-problems table, recent commits,
   ablations / dead ends, current pending work.
2. `docs/architecture.md` for design (DB schema, pipeline kinds,
   resolution chain, etc.).
3. `git log --oneline -15` to see what landed since STATUS was written.

Don't act on memory of the codebase from prior sessions until you've
verified against the current tree — F-numbers and architecture have
shifted often.

## Operator workflow

| Goal | Use |
|---|---|
| Inspect a Problem's state | `python -m Tooling.cli status <p>` (add `--json` for piping) |
| Wipe a Problem to retest | `python -m Tooling.cli reset <p>` |
| Pre-flight before a run | `python -m Tooling.cli doctor` |
| Initialize a new Problem | `python -m Tooling.cli init <p>` (auto-writes Root.lean sorry-stub) |
| Launch the daemon | `python -m Tooling.cli run` (logs auto-tee to `.asterism/logs/`) |
| List orphan proof files | `python -m Tooling.cli prune --dry-run` |

**Do not** write ad-hoc `python -c "import sqlite3; ..."` one-liners
to inspect DB state. `asterism status --json` covers it. Same for
filesystem cleanup: `asterism reset` over manual `rm`.

## Per-Problem configuration

Project defaults live in `Asterism.yaml` at repo root (optional).
Schema and resolution chain are documented in `docs/architecture.md`
§10. Quick recap:

```
env var  >  Asterism.yaml  >  legacy env  >  built-in default
```

Built-in `(builder_threshold, shelve_threshold) = (3, 8)` is tuned for
Sonnet/Opus. Weak-tier models (Haiku / Flash / mini) want roughly
`(5, 10)` — write it explicitly in `Asterism.yaml`. There is no
runtime model-name auto-detection (the haiku-substring tier was
retired; a model→threshold table is documentation, not code).

## Recurring traps

- `claude --session-id` requires dashed UUID (`str(uuid.uuid4())`),
  not `.hex`. Already fixed in pipeline.py; don't reintroduce.
- Gemini free-tier quota exhausts silently (rc=0 + empty output).
  `Tooling/llm/gemini_cli.py` detects this and surfaces rc=126.
- The dispatcher's daemon log filename uses `ASTERISM_AGENT_MODEL` for
  the `<model>` slug — cosmetic; doesn't affect resolution chain.
- `.attempts/<pid>/` is per-pipeline ephemeral. Never assume it's
  cleaned up across daemons; `asterism doctor` warns on > 5 stale
  dirs and `rm -rf .attempts/` is the correct response when no
  daemon is running.

## Testing

```
python -m pytest tests/ -q --deselect \
  tests/test_dedupe.py::test_batch_isdefeq_real_lake --deselect \
  tests/test_lemma_lookup.py::test_lookup_batch_real_lake
```

The two deselected tests need a real `lake` cache and run for minutes;
skip in normal regression. Otherwise the full suite is fast (< 5 s)
and should be 100% green at HEAD before any commit.

## Don't

- Push to GitHub without the user explicitly saying "push".
- Reintroduce model-name substring matching for tier defaults — write
  to `Asterism.yaml` instead.
- Write a per-Problem `run:` section in Manifest.md — Manifest is for
  data only (statement / axioms / forbidden_lemmas / strategic notes);
  run-time config lives in `Asterism.yaml`.
- Add `README.md` / quickstart docs under `docs/` unless asked. The
  human user does not consume those; STATUS.md + this file are the
  handoff layer that actually gets read.

## What to update after substantial work

- `docs/STATUS.md` — record ablations, new feature commits, anything a
  future session needs to know that isn't trivially derivable from
  `git log` or the code itself.
- This file (`CLAUDE.md`) when an operator workflow changes (new CLI
  subcommand, retired knob, new convention).
