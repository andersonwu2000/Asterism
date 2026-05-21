# Asterism feature ID history (snapshot)

One-time catalog of feature shorthand IDs used during early development
(2026-04-29 → 2026-05-14). After the cleanup pass following this snapshot,
the code and current docs reference features by prose, not by ID. This
file is the decoder ring for any lingering ID references in git history
(commit messages, archived docs, BRIEF.md history).

Lookup logic: introduction commit (subject leads with the ID) preferred,
first-mention commit as fallback.

## Feature IDs

| ID | Commit | Subject |
|---|---|---|
| F1 | `2608ecc` | F1: shorten sub-goal slug to s<sid>_sub_<N> |
| F2 | `dceb587` | F2: rmtree orphan .attempts/<pid>/ dirs at daemon startup |
| F3 | `78472d1` | F3: sweep orphan .backup/.verify_backup/.tmp at daemon startup |
| F4 | `e648a5f` | F4: Dedupe upgrade — Lean kernel isDefEq via batched lake subprocess |
| F7 | `b7c1053` | F7 step 1: extract LLM dispatch into Tooling/llm/ provider registry |
| F8 | `5482f28` | F8: provider-side markdown-fence strip + collect _raw_response.txt |
| F9 | `7768b20` | F11+F9: daemon idle-exit + structured lake-stderr → actionable hints |
| F11 | `7768b20` | F11+F9: daemon idle-exit + structured lake-stderr → actionable hints |
| F12 | `7f27840` | Three confirmed-bug fixes: F14 dedupe correctness, F12 zombie strategy, F13 stderr truncation |
| F13 | `7f27840` | Three confirmed-bug fixes: F14 dedupe correctness, F12 zombie strategy, F13 stderr truncation |
| F14 | `7f27840` | Three confirmed-bug fixes: F14 dedupe correctness, F12 zombie strategy, F13 stderr truncation |
| F15 | `a7caf1a` | [F15] Root.lean lifecycle hardening — init guard + architecture §3.5 |
| F16 | `b6c3896` | [F16] Symmetric cascade: kill own strategies on goal-shelve |
| F17 | `6dfd7ce` | [F17] Hint regex case-insensitive + auto-inject `import Mathlib` |
| F18 | `8881383` | [F18] Configurable BUILDER/SHELVE thresholds, defaults 5/8 |
| F20 | `1011f1f` | [F20] Lemma signature lookup — inject Mathlib ground truth into Context.md |
| F22 | `f766707` | [F22] Per-problem playbook — agent-curated success idiom accumulation |
| F23 | `34644c0` | [F23] Batch lake build for run_backward — single multi-target invocation |
| F24 | `efd0236` | [F24] Cascade race fix — guard shelved goal + pipeline early abort |
| F26 | `1ec26ec` | [F26] Lazy-load Context — externalize bulky failure detail to companion files |
| F27 | `0091561` | [F27] Trim claude CLI system-prompt overhead |
| F28 | `531dedd` | [F28] Daemon log path → .asterism/logs/<problem>_<model>_<ts>.log |
| F29 | `af3f575` | [F29] PROPOSAL.md anti-fluff directive |
| F30 | `1933c83` | [F30] PAST_ATTEMPTS.md / PAST_VERIFIES.md smart-truncate failure_detail |
| F31 | `83304d7` | [F31] Model-aware default thresholds — Sonnet 3/7 vs Haiku 5/8 |
| F32 | `d1bd0ff` | [F32] Strip lake noise lines from failure_detail outright |
| F33 | `46c73c9` | [F33] Same-session Builder retry — claude --resume across attempts |
| F34 | `7db1603` | [F34] Expand TACTIC_TRY_LIST — domain closers + Lean 4.30 grind |
| F35 | `433d87d` | [F35] lemma_lookup: accept `@`-prefixed name from `#check @<lemma>` |
| F36 | `a7cb787` | [F36] Restore proof-sketch latitude in Backward PROPOSAL.md |
| F37 | `49a848a` | [F37] OR-parallel → passive sequential strategy retry |
| F38 | `5a0ed10` | [F38] Gemini CLI provider via Code Assist free tier |
| F39 | `4710987` | [F39] Per-pipeline provider/model selection |
| F40 | `2b6ff1a` | [F40] Two-phase Builder delivery (opt-in) |
| F41 | `7f7f293` | [F41] Verify-time patch retry — one-shot LLM repair on Step 1 fail |
| F42 | `45f1b68` | F42 — cross-strategy sub-goal reuse via orphan-aware dedupe |
| F43 | `db37bee` | [F43] Inline PAST_ATTEMPTS / PAST_VERIFIES into Context.md (kind-aware) |
| F44 | `d4f9321` | [F44] Anchor agent cwd at problem_dir (soft sandbox) |
| F45 | `77156f8` | F45 — inline prompt body into -p (fix F44 regression) |
| F46 | `5941c56` | F46 — defense against claude.exe instant-fail loop |
| F47 | `248837b` | F47 — move builder_threshold from dispatch.* to builder.* in Asterism.yaml |
| F48 | `2cc86bf` | F48 — Builder decline channel |
| F49 | `ee158c4` | F49 — Library promotion + lemma_hints unification |
| F50 | `9901b04` | F50 — Lemma discovery tools: Grep + Loogle for agents |
| F51 | `1214fa7` | F51 — retry prompt enrichment for unknown-constant lake errors |
| F52 | `c1aec12` | F52 — skeleton-driven strategy patches + def-alias promotion |
| F53 | `c0ef661` | F53 — same-session Backward retry (mirror of F33 for Builder) |
| F54 | `89ffa56` | F54 — Context.md cleanup, path-scoped allowlist, generic retry hints |
| F55 | `cdb03b5` | F55 — partial-output persistence so timed-out spawns don't lose work |
| F56 | `27d46bb` | F55 redesign + F56 — kill Verify pipeline; postmortem-spawn replaces incremental save |

F5, F6, F10, F19, F21, F25: numbers were skipped; never assigned.

## Audit phases

P-phases mark refactoring / cleanup sweeps separate from feature work.

| ID | Commit | Subject |
|---|---|---|
| P0-#1 | `b7e79ce` | P0-#1 — _promote_to_alias race + per-goal Verify serialization |
| P0-#2 | `5d6c1a0` | P0-#2 — reconcile_proved_goals stops undoing F52 |
| P0-#3 | `5a544f9` | P0-#3 — F53/A reuse path clears stale strategy_subgoals |
| P0-#4 | `6bd22c5` | P0-#4 — Fix F54 Builder regressions (sandbox + dead-strategy dedupe) |
| P1-#5 | `8ebb964` | P1-#5/#6/#7 — commit + sqlite timeout + post-spawn session_id |
| P1-#6 | _(no committed reference)_ | _(only mentioned in code comments at snapshot time)_ |
| P1-#7 | _(no committed reference)_ | _(only mentioned in code comments at snapshot time)_ |
| P1-#8 | `9e8e413` | P1-#8 — log filename respects per-pipeline model resolution |
| P1-#9 | `ec20379` | P1-#9 — F54 nits (sorry-hint scope, placeholder, dead code) |
| P2-#1 | `6242ec7` | P2-#1 — first end-to-end dispatcher integration test |
| P2-#2 | `7480e19` | P2-#2 — direct run_builder entry-point tests |
| P2-#3 | `ea366eb` | P2-#3 — isolate lemma_lookup CACHE_FILE per-test |
| P2-#4 | `317d475` | P2-#4 — extract Tooling/recovery.py from dispatcher.py |
| P2-#5 | `7334346` | P2-#5 — drop cross-module private leaks + spawn_claude alias |
| P2-#6 | _(no committed reference)_ | _(only mentioned in code comments at snapshot time)_ |

P1-#6, P1-#7: batched into the P1-#5/#6/#7 commit at `8ebb964` (sqlite
timeout + post-spawn session_id, alongside P1-#5).

## Mathlib-allowlist (M) series

A short companion series for fixes to the agent's mathlib read/grep
allowlist, separate from the main F-ID stream.

| ID | Commit | Subject |
|---|---|---|
| M1 | `1014d91` | M1+M2 — widen mathlib allowlist + force lemma-name verification |
| M2 | `1014d91` | M1+M2 — widen mathlib allowlist + force lemma-name verification |
| M3 | `d045e15` | M3 — add `--add-dir <packages>` so allowlist on Mathlib actually works |

## Early framework checkpoints (W series)

Pre-F-series structural milestones from the first iteration: worker
kind split, defensive hardening, test coverage, reopen rule, etc.

| ID | Commit | Subject |
|---|---|---|
| W1 | `99b864d` | W1: split Builder/Verify, add Strategy.proposal_md, trim schema enums |
| W2 | `ca74f3c` | W2: defensive hardening — sorry-stub guard, WorkArea, WAL, balanced parser |
| W3 | `b75a545` | W3: pytest coverage for pure functions |
| W4 | `be338ea` | W4: fix stuck-attempting goal + surface Verify failures in goal Context |
| W6 | `05a1d6e` | W6: fix Verify thrashing + cli auto-import Defs.lean |

W5, W7, W8: introduction commits don't use the `W<n>:` prefix; locate via `git log --grep=W<n>`.
