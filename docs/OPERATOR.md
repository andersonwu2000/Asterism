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

### Environment variables

The chain above covers `dispatch.*`, `builder.*`, `backward.*`. These
extra env vars are env-only (no Asterism.yaml binding):

| Var | Effect | Default |
|---|---|---|
| `ASTERISM_VERIFY_RETRY` | F41: when Verify Step-1 lake build fails, ask LLM ONCE to rewrite the strategy patch (sub-goals untouched). Set `0` to disable. | `1` (on) |
| `ASTERISM_BUDGET_SEC` | Daemon wall-clock cutoff. | `1800` (30 min) |
| `ASTERISM_LLM_API_KEY` | OpenAI provider auth. Required when `ASTERISM_LLM_PROVIDER=openai`. | unset |
| `ASTERISM_LLM_BASE_URL` | OpenAI-compatible endpoint (LiteLLM proxy etc). | OpenAI default |
| `ASTERISM_LLM_MAX_TOKENS` | OpenAI provider per-call cap. | `8000` |
| `ASTERISM_LLM_TEMPERATURE` | OpenAI provider sampling temp. | `0` |
| `ASTERISM_CLAUDE_TOOLS` | Override `--tools` list passed to claude CLI. | `Read Write Edit Grep Bash` |
| `ASTERISM_CLAUDE_ALLOWED_TOOLS` | Replace the per-spawn computed allowlist (see F54/M1). Empty string (`""`) drops the flag. | derived from `req.problem_dir` |
| `ASTERISM_CLAUDE_ALLOWED_BASH` | Override only the Bash subset of the allowlist. | `Bash(python -m Tooling.loogle *)` |
| `ASTERISM_POOL` | Worker pool size (mirrors `dispatch.pool`). | `12` (from yaml default) |
| `ASTERISM_BUILDER_THRESHOLD` | Mirrors `builder.threshold`. | `3` |
| `ASTERISM_SHELVE_THRESHOLD` | Goal attempts cap before shelve. | `8` |
| `ASTERISM_LLM_PROVIDER` | Default provider for both kinds (claude/gemini/openai). | `claude` |
| `ASTERISM_BUILDER_PROVIDER` / `ASTERISM_BACKWARD_PROVIDER` | Per-kind provider override (F39). | follows `ASTERISM_LLM_PROVIDER` |
| `ASTERISM_BUILDER_MODEL` / `ASTERISM_BACKWARD_MODEL` | Per-kind model override (mirrors `builder.model` / `backward.model`). | follows yaml then `ASTERISM_AGENT_MODEL` |
| `ASTERISM_AGENT_MODEL` | Legacy provider-wide model fallback. | `claude-sonnet-4-6` |
| `ASTERISM_GEMINI_MODEL` | Gemini provider model. | gemini default |

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
