# Asterism v2 — Current Status

Updated 2026-05-04 (post P0/P1/M/P2 + critical regression caught).
HEAD = `be940d5`, 550 unit tests + 24 lake-integration green.

## Live test queued (post-compact action item)

Daemon stopped. Operator about to /compact and run **Sonnet** on
the next testbed. P0/P1/M validated last run (proj_nonexpansive
Sonnet ~58 min, 0 dead, 0 naming_violation). Suggested order:

1. **inner_zero_iff_smul** (difficulty 4, ~15-20 min) — short
   smoke test for the post-batch state.
2. **proj_nonexpansive** (difficulty 5, ~58 min Sonnet baseline)
   — already proved this run, useful as regression baseline if
   thinking-length / Builder-retry numbers drift.
3. **gen_generates** — restart fresh:
   `python -m Tooling.cli reset gen_generates && python -m Tooling.cli init gen_generates`
4. **localization_euclidean** / **cantor_xi_measure** — stress
   tests (60+ min each).

Launch:
```
python -m Tooling.cli reset <problem>
python -m Tooling.cli init <problem>
ASTERISM_BUDGET_SEC=3600 python -m Tooling.cli run
```
(daemon log auto-tees to `.asterism/logs/<problem>_<model>_<ts>.log`;
no `>` redirect needed.)

New CLI affordances this batch:
- `python -m Tooling.cli logs [--tail N]` — list / tail framework logs
- `python -m Tooling.cli config` — print resolved config (pool / thresholds / models)
- `python -m Tooling.cli reset <p> --soft` — surgical recovery from
  spawn_fast_fail cascades (provider quota exhaust)

What to watch for (P0/P1/M signals):
- 0 `naming_violation` in cascade log (P0-#3 / F53/A)
- 0 `patch_signature_mismatch` (F52)
- 0 cross-problem reads in claude session jsonls (F54+M1)
- 0 Mathlib Grep denied (M1 widened to `.lake/packages/**/*.lean`)
- F33/F53 `--resume` warm spawns active (look for `--resume` in claude.exe argv)

> **Daemon state**: stopped, no live PIDs. DB carries proj_nonexpansive
> = proved. Other problems' state unchanged from pre-run.

## 2026-05-04 batch (today)

Audit-driven cleanup, 25+ commits in one day. Headline:

**Bugs fixed (P0/P1)**:
- P0-#1 `_promote_to_alias` race + per-goal Verify serialization
- P0-#2 `reconcile_proved_goals` no longer undoes F52 (was rewriting parents back to binder-stripping form every prune)
- P0-#3 F53/A reuse path clears stale `strategy_subgoals`
- P0-#4 F54 Builder regressions (sandbox empty + over-pruned dedupe)
- P1-#5/#6/#7 `_propagate_shelve` commit + sqlite timeout=30 + post-spawn session_id
- P1-#8/#9 cli log mixed-model + F54 nits

**Prompt/agent (M)**: M1 widened `.lake/packages/**` allowlist
(Sonnet rerun showed 18 denied Grep ops/run); M2 added "verify
lemma names via Loogle/Grep" directive.

**Architecture (P2)**: pipeline.py → `pipeline/` package with
`_lake.py` + `_skeleton.py`; `Tooling/context.py` extracted from
agent.py (575 LOC out of 700); `Tooling/recovery.py` extracted
from dispatcher.py; `SpawnRC` IntEnum replaces magic numbers;
private cross-module symbols promoted (`_collect_artifacts` →
`collect_artifacts`, `_render_*` → `render_*`,
`_resolve_gemini_executable` / `_resolve_model` likewise).

**Tests (P2)**: first true e2e test (`test_e2e_dispatcher.py`)
+ direct `run_builder` entry-point tests + `lemma_lookup`
CACHE_FILE isolated per-test. 529 → 550.

**Docs (P2)**: `docs/architecture.md` §0/§3 refreshed;
`docs/OPERATOR.md` env-var table now lists 17 vars (was 0).

**Critical regression caught by review (commit `be940d5`)**:
P2-#1's pipeline-package conversion broke `PROMPT_DIR` —
`Path(__file__).parent / "prompts"` resolved to the now-non-existent
`Tooling/pipeline/prompts/`. Live runs would silently spawn with
`(prompt file unavailable)`. All 549 unit tests miss this because
they monkeypatch `agent.spawn_llm`. Fixed + e2e test now asserts
`prompt_path.exists()` inside its fake_spawn so the next analogous
regression fails immediately.

Deferred follow-ups (low ROI, not blocking):
- `cmd_logs --tail` could use deque instead of `readlines()[-N:]`
- `cmd_config` could annotate value source (env / yaml / default)
- `_soft_reset` revives F12-cascaded shelves; self-stabilizes after
  one bounce but noisy
- F33/F53 retry boilerplate (~120 LOC dup between Builder+Backward)
  could move to a `_spawn.py` helper

## Earlier sessions

Compactness rerun on Sonnet exposed two cascading framework gaps and
finished proved on Opus:

1. **F45** (commit `77156f8`) — F44's cwd narrowing left
   `Tooling/prompts/*.md` unreachable to claude (outside `--add-dir`),
   so Backward's first 7.5min just generated the title `"Unable to
   access file system"` with no PROPOSAL.md. Fix: inline the prompt
   body into `-p` so the agent never needs cross-boundary file reads.
2. **F46** (commit `5941c56`) — Sonnet's compactness rerun then hit
   account quota mid-cascade. claude.exe started returning rc=1 in
   ~2s with stdout `"You've hit your limit"`. The dispatcher had no
   defense: 25+ instant failures within 30s burned every reachable
   goal's attempts cap and shelved root via cascade. Fix is three-layer:
   - Provider writes captured stderr to `attempts_dir/_spawn.stderr`
     on rc≠0 → real diagnosis instead of "agent rc=1".
   - Pipeline times the spawn; rc≠0 in <10s → failure_reason
     `spawn_fast_fail`. cascade_one looks that up via DB and skips
     `increment_goal_attempts`. Goal cap untouched by infra blips.
   - Dispatcher cooldown_until dict + global counter: per-(target,
     kind) 30s back-off after fast-fail, daemon exits cleanly after
     10 consecutive fast-fails (any target).

After F46, **Opus closed compactness in 25.2 min** (post-restore — see
"Compactness 2026-05-02 timeline" below). Wilson Sonnet baseline
unaffected. 431 unit tests green.

## Compactness 2026-05-02 timeline (representative case)

| Phase | Wall-clock | Outcome |
|---|---|---|
| Sonnet round 1 | 83 min | shelved (account quota exhaust → cascade) |
| F45 + F46 dev | ~30 min | tests green, commits pushed |
| Sonnet round 2 | <1 min | F46 caught quota in 10 spawn_fast_fails, exited rc=2 |
| Manual restore | seconds | 4 goals + 3 strategies revived, 20 spurious dead_attempts pruned |
| Opus rerun | 25.2 min | **proved**; axioms `[propext, Classical.choice, Quot.sound]` |

The restore script rule of thumb (only needed if a daemon shelved
goals from infra rather than agent failure):

```python
# 1. fast_fail_pids = pipelines whose duration < 10s on the affected goals
# 2. DELETE FROM dead_attempts + DELETE FROM pipelines for those pids
# 3. UPDATE goals SET attempts = (real attempts), status = (open/attempting)
# 4. UPDATE strategies SET status='proposed' for ones cascade-killed by the fake-shelve
```

A future enhancement could fold this into `asterism reset --soft <problem>`
or a daemon flag, but a one-off was sufficient here.

> **Operator workflow** — see `docs/OPERATOR.md` for CLI subcommands,
> `Asterism.yaml` schema, recurring traps. Kept under `docs/` so solver
> agents (claude / gemini subprocesses) don't auto-load it.

> **User preferences** are in the operator's global memory, not here.

## Proved problems

| Problem | Commit | Prover | Wall-clock | Axioms |
|---------|--------|--------|-----------|--------|
| compactness | 46c8941 | Sonnet | ~60 min | propext, Classical.choice, Quot.sound |
| compactness (Opus) | (HEAD) | Opus  | ~25 min tail | propext, Classical.choice, Quot.sound |
| gen_generates | 4c6f423 | Sonnet | ~30 min | propext, Quot.sound |

(wilson + cantor problems removed 2026-05-03 — operator has external
solutions cache, no longer needs them in-tree as testbeds.)

## Ablations / dead ends (don't re-investigate)

- **F40** Two-phase Builder delivery (`ASTERISM_BUILDER_TWO_PHASE=1`,
  commit `2b6ff1a` reverted at `232a3e0`). Hypothesis: weak models miss
  the patch.lean deliverable. Empirics on Haiku Builder + Sonnet
  Backward: 18 Builder pipelines / 30 min, 3 succeeded, 15 failed, of
  which **11 lake_build_error** (Phase B wrote a patch but Lean rejected
  it — hallucinated lemmas, wrong tactics, syntax errors) vs only **4
  phase_a_no_proposal**. PROPOSAL content was fine; patch quality is the
  bottleneck. F40 doesn't lift Lean reasoning quality. Don't reintroduce
  unless a model's dominant fail mode is documented as deliverable miss.
  Gemini path unverified (quota exhausted on first dispatch).
- **F31 substring tier** (`if "haiku" in model: ...`) retired together
  with the `Asterism.yaml` introduction. Brittle by design (vendor
  naming drift). Weak-tier projects now write `builder.threshold: 5`
  + `dispatch.shelve_threshold: 10` in `Asterism.yaml` explicitly.

## Operator notes from compactness Opus run

- **Opus respects builder.md's "return early" hatch** — line 21 of the
  Builder prompt says "if the goal genuinely needs multi-step
  decomposition, return early without a viable patch." Opus follows
  this literally: writes nothing for genuinely-hard sub-goals, framework
  escalates to Backward after `BUILDER_THRESHOLD` no-op attempts.
  Sonnet ignores the hatch and writes a (frequently broken) patch
  anyway. Net effect on opus: the 3 no-op attempts before Backward
  cost ~30-90s wall-clock per goal, but the eventual Backward
  decomposition is good. Don't tighten BUILDER_THRESHOLD for Opus to
  "skip" the no-ops — those reads might correctly find a 1-step proof
  on easier siblings.
- **Quota exhaust is silent at the CLI layer** — claude.exe returns
  rc=1 with the quota message on **stdout** (not stderr). F46
  combines both into `_spawn.stderr` so this remains visible. If a
  future provider hides the quota message differently, look for
  *consistent* fast-fail across all targets (vs sporadic) as the tell.

## Architectural delta this session (2026-05-02 batch)

Driven by compactness telemetry on the prior run + a Manifest-hint experiment:

- **Manifest hint mechanism** verified (commit `ed877a3`). Adding a
  `### Recommended root decomposition` block under `## Strategic notes`
  in Manifest.md steers Sonnet's Backward to follow the suggested 4-sub
  shape verbatim. Useful when the operator knows a tractable proof
  structure (e.g. baseline reproductions). Does NOT generalize to true
  conjectures where no ground-truth decomp exists — see F41 below.
- **Per-Problem TREE.md** (commit `5b3489c`). Every cascade auto-writes
  `Problems/<p>/TREE.md` with the AND/OR proof tree (slug-named, dead
  strategies annotated with cause). Replaces `python -c 'import sqlite3; ...'`
  inspection during runs.
- **F43 Inline PAST_*.md** (commit `db37bee`). Telemetry showed Sonnet
  Read PAST_VERIFIES.md zero times across 59 sessions despite the
  prompt pointer — so re-Backward never learned from prior Verify
  failures, and the same type-drift kept recurring. Switched to
  framework-driven eager inlining; kind-asymmetric (Builder gets
  PAST_ATTEMPTS only, Backward gets PAST_VERIFIES only).
- **F44 cwd → problem_dir** (commit `d4f9321`). Soft-sandbox the agent's
  cognitive frame to the active Problem. Doesn't enforce reads (claude
  CLI's `--add-dir` doesn't), but reduces wandering reads to other
  Problems / workspace files. Effect uncertain ahead of time;
  measurable post-compactness rerun.
- **F41 Verify-time patch retry** (commit `7f7f293`). When Verify Step 1
  lake build fails (the dominant type-drift trigger), one cold LLM call
  rewrites ONLY the strategy patch with sub-goal proofs as fixed
  reference. On success, Verify continues to Step 2 saving every
  sub-goal's prove cost; on failure, restore + standard cascade. Off
  via `ASTERISM_VERIFY_RETRY=0`.
- **`asterism reset` pipelines bug** (commit `141a5e2`). Reset was
  leaking pipeline rows pointing to deleted goals/strategies. Fixed.
  Surfaced during F41 investigation (looked like a dead_attempt
  recording bug at first).

## Recent commits

| Commit | Topic |
|---|---|
| f211823 | Add localization_euclidean + cantor_xi_measure stress testbeds |
| ffe5637 | Add proj_nonexpansive + inner_zero_iff_smul HW testbeds |
| c8b7d87 | STATUS trim — wilson + cantor problem entries removed |
| 93bcba5 | Remove wilson + cantor problems (operator has external cache) |
| 1214fa7 | F51 — retry prompt enrichment for unknown-constant lake errors |
| 1289cff | F50 follow-up: hint Mathlib path + fix allowed-tools wildcard |
| 5c07254 | F50 follow-up: trim lemma discovery prompt verbosity |
| 9901b04 | F50 — Lemma discovery tools: Grep + Loogle for agents |
| 2cc86bf | F48 — Builder decline channel |
| 248837b | F47 — move builder_threshold to builder.* in Asterism.yaml |
| 1d234ae | compactness proved by Opus + STATUS update |
| 5941c56 | F46 — defense against claude.exe instant-fail loop |
| 77156f8 | F45 — inline prompt body into -p (fix F44 regression) |
| a0fc91f | STATUS: F41/F43/F44 batch + post-compact action item |
| 7f7f293 | F41 — Verify-time patch retry (one-shot LLM repair) |
| 141a5e2 | Fix asterism reset leaking stale pipelines table rows |
| d4f9321 | F44 — anchor agent cwd at problem_dir (soft sandbox) |
| db37bee | F43 — inline PAST_ATTEMPTS / PAST_VERIFIES into Context.md |
| ed877a3 | compactness Manifest hint (verified-easy 4-sub root decomp) |
| b2a706b | STATUS: bump test count |
| b1072ce | Revert STATUS F41 prose entry (task tracker is canonical) |
| 5b3489c | Per-Problem TREE.md auto-rendered on every cascade |
| f98c473 | Asterism.yaml: drop redundant Examples block |
| 8922cc2 | Move CLAUDE.md → docs/OPERATOR.md (out of solver agent auto-load) |
| 6123dab | OPERATOR.md: trim narrative |
| 655d907 | (was) CLAUDE.md — operator notes (see 8922cc2 rename) |
| b64f58f | asterism doctor — pre-flight diagnostic |
| d7af009 | Asterism.yaml + 4-step resolution chain; retire haiku-substring tier |
| 44385dd | asterism reset / status — replace ad-hoc per-Problem ops |
| e63932c | STATUS: F40 ablation conclusion + uuid sub-fix |
| 232a3e0 | Revert "[F40] Two-phase Builder delivery (opt-in)" |
| a4bbeb5 | Fix F33 cold-spawn rc=1: --session-id requires dashed UUID |
| 4710987 | F39 — per-pipeline provider/model selection |
| 382e23c | Provider-neutral failure_detail + dispatcher worker-exception recovery |
| 5a0ed10 | F38 — Gemini CLI provider via Code Assist free tier |
| 49a848a | F37 — OR-parallel → passive sequential strategy retry |
| 945c8d4 | F33 follow-up: inline retry error in prompt |
| 46c73c9 | F33 — same-session Builder retry |
| 2c541aa | Reorder Context.md sections |
| a7cb787 | F36 — restore proof-sketch latitude |
| 433d87d | F35 — lemma_lookup `@`-prefix parser |
| 7db1603 | F34 — expand TACTIC_TRY_LIST |
| d1bd0ff | F32 — strip lake noise |
| 83304d7 | F31 — model-aware thresholds (later retired) |
| 531dedd | F28 — daemon log auto-path |
| 1933c83 | F30 — companion file smart_truncate |
| af3f575 | F29 — PROPOSAL anti-fluff (partially reverted) |
| 0091561 | F27 — CLI flag trim |
| 1ec26ec | F26 — lazy-load Context.md |
| a7caf1a | F15 — Root.lean lifecycle |

## Next pending

- **#227 F10**: Sonnet + Dedupe v4 live-validation. v4 is verified safe
  after F14 but doesn't fire on wilson / compactness (max depth 2-3, no
  ancestor reuse). Either retire as "validated safe" or wait for a
  deeper-recursion problem. (F42 since done — this may now redirect to
  testing on the new deeper testbeds.)
- **#250 F38 live smoke**: Gemini provider live test pending Gemini
  quota reset. Lower priority since claude path is well-exercised.

## Test count

472 unit tests + 24 lake-integration tests (lemma_lookup; skipped if
`lake` missing). All green at HEAD f211823.
