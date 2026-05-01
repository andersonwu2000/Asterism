# Asterism v2 — Current Status

Updated 2026-05-01 (post-F37 OR-passive). Compaction-safe handoff note.

## Proved problems (4 + 1 weak-model variant)

| Problem | Commit | Prover | Wall-clock | Axioms |
|---------|--------|--------|-----------|--------|
| wilson | 9c2c2a0 | Haiku | 39.5 min | propext, Classical.choice, Quot.sound |
| wilson (Sonnet, replaced) | 6b0cf3b | Sonnet | ~15 min | propext, Classical.choice, Quot.sound |
| compactness | 46c8941 | Sonnet | ~60 min | propext, Classical.choice, Quot.sound |
| cantor | 6bd6c15 | Sonnet | ~5 min | [] (constructive) |
| gen_generates | 4c6f423 | Sonnet | ~30 min | propext, Quot.sound |

**Latest regression check** (post-F35/F36 fixes): wilson re-proved by Sonnet in **15.7 min**, axioms identical to baseline. Sub_1 used the same `Nat.prime_iff_fac_equiv_neg_one` shortcut the original baseline relied on.

## Architectural delta since 2026-04-30 (F23 → F37)

This batch closed 15 task IDs + two refactor commits. Group by goal:

### Cascade & dispatch hardening
- **F23** (34644c0) — `_lake_build_batch`: one `lake build m1 m2 m3 ...` instead of N sequential single-target calls. Backward succeeded avg dropped 517s → 151s (-71%) on Haiku wilson.
- **F24** (efd0236) — Cascade race fix. Symmetric `cascade_one` no-op guards on `'shelved'` (was only `'proved'`); pipeline.run_backward re-checks goal status before linking. Closed an OR-race that left goal stuck at attempts=N/attempting + orphan strategy.
- **F31** (83304d7) — Model-aware default thresholds. `BUILDER/SHELVE` defaults pick by `ASTERISM_AGENT_MODEL` substring: haiku → 5/8 (more rounds for weak iteration); else → 3/7 (Sonnet/Opus rarely succeed at attempts ≥3). Env override still highest priority.

### Context.md / token economy
- **F26** (1ec26ec) — Lazy-load Context.md. Past attempts + Verify failures: digest in Context.md + full content moved to `PAST_ATTEMPTS.md` / `PAST_VERIFIES.md` companion files in attempts dir. Context.md ~10 KB → ~3 KB.
- **F27** (0091561) — Trim claude CLI flags: `--tools "Read Write Edit"` + `--setting-sources ""` + `--disable-slash-commands` + `--exclude-dynamic-system-prompt-sections`. System prompt prefix ~20.7K → ~7.8K tokens (-62%).
- **F29** (af3f575) → partially reverted by **F36** (a7cb787) — F29 banned "detailed proof sketches" in PROPOSAL.md to cut output tokens; F36 dropped that one ban after wilson regression showed Sonnet stopped mentally simulating each sub-goal's proof, leading to lazy 2-sub decompositions where sub_1 = parent's hardest lemma renamed. Other anti-fluff bans preserved (no goal restating, no sub-goal statement code blocks).
- **F30** (1933c83) — `PAST_ATTEMPTS.md` / `PAST_VERIFIES.md` go through `smart_truncate_stderr(force_reorder=True)`.
- **F32** (d1bd0ff) — `strip_lake_noise()` deletes pure-noise lines outright (LEAN_PATH dump, redundant `error: build failed` summaries). Real-data ~62% size reduction on 17-sample dead_attempts.
- **F35** (433d87d) — `lemma_lookup` parser accepts optional `@` prefix in `#check` output. Was mashing 3 lemmas into 1 bullet when implicit-arg lemmas got the `@` prefix from Lean.
- **Reorder** (2c541aa) — `_section_lemma_references` placed adjacent to `_section_manifest_hints` so name+signature read together.

### Same-session retry (F33 — major addition)
- **F33** (46c73c9) + follow-up (945c8d4) — `goals.builder_session_id`. First Builder dispatch mints uuid + `claude --session-id <uuid>`; retries use `--resume <uuid>` with a short prompt that inlines the smart-truncated lake error directly (no separate RETRY_NOTE.md file → no extra Read tool round-trip). Prior turn's reasoning lives in claude session memory; ~47% token reduction across 3-attempt sequences.
- Stale session sentinel: `--resume` against missing on-disk session returns rc=125; pipeline clears DB id and falls back to cold path with fresh uuid.
- Timeout (rc=124) clears session_id (claude may be mid-write corrupted).
- Other failures keep session_id (next attempt sees prior failed turn — useful self-correction context).
- BUILDER threshold reached / proved / shelved → cascade clears session_id.

### OR sequencing → passive (F37, major architectural shift)
- **F37** — `OR_FANOUT` removed entirely (constant + `ASTERISM_OR_FANOUT` env var + `or_fanout` parameter all gone). Each open Goal now has at most one in-flight Builder OR Backward; sequential strategy retry replaces eager fanout.
  - `bfs_refill` cap=1 universally; `running` set simplified `(tid, kind, pid)` → `(tid, kind)`.
  - Added missing `increment_goal_attempts` in `_propagate_shelve` reopen branch — without this, dead-by-cascade strategies wouldn't advance the goal toward SHELVE_THRESHOLD and Backward would loop forever. Also handles cascade-shelve recursion when the increment itself crosses threshold.
  - Defaults raised: SHELVE 7→8 (Sonnet), 8→10 (Haiku) so passive Backward gets ~5 strategy attempts before goal shelves.
  - `agent.py` new `_section_dead_strategies` — each Backward retry sees prior dead strategies' sub-goal slugs + statuses (anti-repetition prompt hint, replaces F25 sibling alias which no longer applies).
- **F25** (Sibling sub-goal dedupe) — RETIRED. Was for OR-parallel waste; passive trigger eliminates parallel siblings entirely. Anti-repetition handled by `_section_dead_strategies` instead.

### Other
- **F28** (531dedd) — Daemon log auto-path `.asterism/logs/<problem>_<model>_<ts>.log` + tee + retention (keep 20 newest).
- **F34** (7db1603) — `TACTIC_TRY_LIST` adds `norm_cast`, `push_cast`, `ring`, `ring_nf`, `field_simp`, `positivity`, `grind`. Each fast-path hit saves an entire Builder pipeline.
- **F15** (a7caf1a) — Root.lean lifecycle init guard. Reject non-sorry, non-wrap Root.lean unless `--force`. Architecture §3.5 documents three-state lifecycle.
- **OR_FANOUT_DEFAULT** 3 → 2 (f1fbbf0) — less wasteful per-goal default. Now superseded by F37 (whole knob removed).

## Ablations / dead ends (don't re-investigate)

- F27 tools removal is NOT the wilson Sonnet regression cause (verified by `ASTERISM_CLAUDE_TOOLS=default` ablation — Sonnet still timed out on Wilson core).
- Wilson core `(↑(p-1)! : ZMod p) = -1` is a single-step lemma Sonnet can only close via `Nat.prime_iff_fac_equiv_neg_one` (Mathlib helper not in Manifest's forbidden_lemmas). When Sonnet recalls this name, wilson finishes in ~15 min; when it doesn't, no amount of decomposition helps because the sub-goal IS the parent's hardest step.
- baseline 6b0cf3b's "fast" wilson WAS this Mathlib helper shortcut. Not really a deeper proof — commit message itself acknowledges the forbidden_lemmas gap.
- **F40 (Two-phase Builder delivery, opt-in `ASTERISM_BUILDER_TWO_PHASE=1`)** — implemented at commit `2b6ff1a`, reverted at `232a3e0`. Hypothesis: weak models (gemini-flash / haiku) miss the patch.lean deliverable when asked to write PROPOSAL.md + patch.lean in the same call, so split into Phase A (PROPOSAL) and Phase B (cold patch). Live test on wilson with Haiku Builder + Sonnet Backward: 18 Builder pipelines / 30 min, 3 succeeded, 15 failed → 11 `lake_build_error` (Phase B wrote a patch but Lean rejected it: hallucinated lemma names, wrong tactics, syntax errors), only 4 `phase_a_no_proposal`. PROPOSAL content was reasonable; patch quality was the bottleneck. F40 doesn't address Lean reasoning quality, so it neither speeds up Haiku nor reaches root proof faster than the 39.5 min single-phase baseline. Gemini path unverified (quota exhausted on first dispatch). Don't reintroduce without a concrete model whose dominant fail mode is documented as deliverable miss (not Lean type error). Prompt files `builder_phase_{a,b}_*.md` and 6 unit tests deleted along with the revert.
- Critical sub-fix kept (commit `a4bbeb5`, NOT reverted): `uuid.uuid4().hex` (32-char no-dash) is rejected by current claude CLI's `--session-id` validator (wants dashed 8-4-4-4-12). Replaced with `str(uuid.uuid4())`. F33 cold-spawn was actually broken in current claude CLI without this fix; only surfaced because F40 testing happened to exercise the cold path on a fresh DB.

## Usability consolidation (2026-05-02)

After F40 ablation the framework had ~10 env vars scattered across 5 files
and ad-hoc operator workflows (manual `rm -rf .attempts/`, hand-written
sqlite one-liners) that re-occurred every session. This batch consolidates:

- **`asterism reset <p>`** (commit `44385dd`) — wipe one Problem's DB
  rows + `proofs/{L_*,_strategy_*}.lean` + Root.lean back to sorry stub.
  Other Problems untouched. `.attempts/` left alone (per-pipeline ephemeral).
- **`asterism status <p> [--json]`** (commit `44385dd`) — goals table,
  live strategies, queue depth, dead_attempts grouped by failure_reason,
  recent pipelines filtered to this problem. JSON output for piping.
- **`Asterism.yaml`** at repo root + `Tooling/config.py` (commit `d7af009`) —
  4-step resolution chain `env > Asterism.yaml > legacy env > built-in`.
  Schema covers `dispatch.{pool,budget_sec,builder_threshold,shelve_threshold}`
  + `{builder,backward}.{provider,model}`. Optional file; legacy env vars
  (`ASTERISM_AGENT_MODEL`, `ASTERISM_GEMINI_MODEL`, `ASTERISM_LLM_MODEL`)
  remain in the chain so existing setups don't need to change. See
  architecture.md §10 for the full schema.
- **F31 substring tier retired** (same commit `d7af009`) — `_model_aware_thresholds`,
  `_WEAK_DEFAULTS`, `_STRONG_DEFAULTS`, and 7 tests gone. Built-in `(3, 8)` for
  Sonnet/Opus baseline. Weak-tier projects now write `dispatch.builder_threshold: 5`
  + `dispatch.shelve_threshold: 10` in `Asterism.yaml` explicitly. Substring matching
  was brittle (vendor naming drift, future model classes silent-mismatch — proven
  brittle 2026-05-02 by today's UUID hex fix exposing analogous fragility).
- **`asterism doctor`** (commit `b64f58f`) — pre-flight: claude/gemini/lake
  on PATH + version banner, `Asterism.yaml` parse + section count, every
  initialized Problem's Manifest validity, `.attempts/` zombie warning,
  `.asterism/logs/` size. Uses the same Windows-aware gemini resolver
  the provider does so the npm bash-shim path doesn't false-FAIL.
- **`Asterism/CLAUDE.md`** (commit `655d907`) — operator notes for next
  session: read STATUS.md first, use the new CLI subcommands, recurring
  traps (UUID dashed, gemini quota silent, .attempts/ ephemeral),
  testing recipe, do/don't list. Replaces the implicit knowledge that
  was only in compaction summaries.

Deferred per user instruction: `docs/MODEL_TIERS.md` (per-model
recommended threshold table). User wants to discuss this later;
no auto-detection in code, just a doc reference when ready.

## Recent commits (since previous STATUS at 8905d84)

| Commit | Topic |
|---|---|
| 655d907 | Asterism/CLAUDE.md — operator notes for future sessions |
| b64f58f | asterism doctor — pre-flight diagnostic |
| d7af009 | Asterism.yaml + 4-step resolution chain; retire haiku-substring tier |
| 44385dd | asterism reset / status — replace ad-hoc per-Problem ops |
| e63932c | STATUS: record F40 ablation conclusion + uuid sub-fix |
| 232a3e0 | Revert "[F40] Two-phase Builder delivery (opt-in)" |
| a4bbeb5 | Fix F33 cold-spawn rc=1: --session-id requires dashed UUID |
| 2b6ff1a | [F40] Two-phase Builder delivery (opt-in) — reverted |
| 4710987 | F39 — per-pipeline provider/model selection |
| 382e23c | Provider-neutral failure_detail + dispatcher worker-exception recovery |
| 5a0ed10 | F38 — Gemini CLI provider via Code Assist free tier |
| 49a848a | F37 — OR-parallel → passive sequential strategy retry |
| 945c8d4 | F33 follow-up: inline retry error in prompt (drop RETRY_NOTE.md) |
| 46c73c9 | F33 — same-session Builder retry |
| 2c541aa | Reorder Context.md sections |
| a7cb787 | F36 — restore proof-sketch latitude |
| 433d87d | F35 — lemma_lookup `@`-prefix parser |
| 7db1603 | F34 — expand TACTIC_TRY_LIST |
| d1bd0ff | F32 — strip lake noise |
| 83304d7 | F31 — model-aware thresholds |
| 531dedd | F28 — daemon log auto-path |
| 1933c83 | F30 — companion file smart_truncate |
| af3f575 | F29 — PROPOSAL anti-fluff (partially reverted) |
| 0091561 | F27 — CLI flag trim |
| 1ec26ec | F26 — lazy-load Context.md |
| a7caf1a | F15 — Root.lean lifecycle |

## Next pending

- **#227 F10**: Sonnet + Dedupe v4 live-validation. **Current data shows v4 doesn't fire on either wilson or compactness** (max depth 2-3, no ancestor-back reuse pattern). v4 is verified safe (no false positives after F14) but real-yield blocked by tree shape. Either retire as "validated safe" or wait for a deeper-recursion problem.
- **F37 follow-up regression** (post-commit): wilson Sonnet + Haiku must still prove. Sonnet baseline 15.7 min; Haiku baseline 39.5 min. SHELVE 8/10 should give passive Backward enough room.
- **#250 F38**: Gemini CLI provider — code complete (`Tooling/llm/gemini_cli.py`, 13 unit tests). Pivoted from HTTP API to CLI subprocess after smoke tests showed Code Assist CLI tier (60 RPM / 1000 RPD) is the only practical free quota; public Gemini API free tier (2 RPM / 50 RPD on pro) is unusable. Live smoke pending: cantor (~5 min, smallest problem) once user's pro quota resets and flash quota is fresh. Caveats: gemini CLI rc=0 lies on quota exhaustion (provider compensates by checking attempts_dir output presence + quota-marker phrases). No F33 same-session retry support (gemini --resume uses session index, not UUID — semantically incompatible).

## Test count

374 unit tests + 2 lake-integration tests (skipped if lake missing). All green at HEAD. Recent additions: 10 reset/status, 20 Asterism.yaml + resolution chain, 8 doctor; 7 retired (haiku substring tier).

## Tooling LOC

~9900 lines (Tooling + tests combined; Tooling alone ~5000). Mostly steady; F33 added ~500 net.

## Things to verify post-compact

1. `git log --oneline -16` — top should be 945c8d4 (F33 inline follow-up); F37 is uncommitted in working tree.
2. `git diff --stat` should show changes in: `Tooling/dispatcher.py`, `Tooling/agent.py`, `tests/test_dispatcher.py`, `tests/test_agent.py`, `docs/architecture.md`, `docs/STATUS.md`.
3. Working tree: `Problems/wilson/` Haiku milestone (commit 9c2c2a0) preserved; `.asterism/logs/`, `.asterism/`, `Tooling/.lemma_cache.json`, `*.log` all gitignored.
4. `python -m pytest tests/ -q --deselect tests/test_dedupe.py::test_batch_isdefeq_real_lake --deselect tests/test_lemma_lookup.py::test_lookup_batch_real_lake` should show **314 passed**.
5. `Problems/wilson/playbook.md` non-empty (1 idiom from regression run).

## User preferences (memory pinned)

- Long-term clean over short-term patch
- "建議?" / "看一下" = consult signal, propose first, wait for "ok" / "動手"
- Don't fix prompts when frameworks could fix the root cause; if prompt is right tool, scope to specific model
- After several additive commits, pause for consolidation pass (this STATUS update + section-list refactor + diagnostics table are exactly that)
- Per-problem experience belongs in plain-text Markdown next to the problem, not in DB (F22 playbook design)
- Prompt cuts have second-order reasoning-quality cost — F29 → F36 lesson: don't only weigh tokens
- 砍掉一個可調節旋鈕（OR_FANOUT env / param / constant）整體簡化收益大於彈性損失（F37 hardcode=1 路線）
