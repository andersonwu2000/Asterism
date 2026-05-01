# Asterism v2 — Current Status

Updated 2026-05-01 (post-F33 stack). Compaction-safe handoff note.

## Proved problems (4 + 1 weak-model variant)

| Problem | Commit | Prover | Wall-clock | Axioms |
|---------|--------|--------|-----------|--------|
| wilson | 9c2c2a0 | Haiku | 39.5 min | propext, Classical.choice, Quot.sound |
| wilson (Sonnet, replaced) | 6b0cf3b | Sonnet | ~15 min | propext, Classical.choice, Quot.sound |
| compactness | 46c8941 | Sonnet | ~60 min | propext, Classical.choice, Quot.sound |
| cantor | 6bd6c15 | Sonnet | ~5 min | [] (constructive) |
| gen_generates | 4c6f423 | Sonnet | ~30 min | propext, Quot.sound |

**Latest regression check** (post-F35/F36 fixes): wilson re-proved by Sonnet in **15.7 min**, axioms identical to baseline. Sub_1 used the same `Nat.prime_iff_fac_equiv_neg_one` shortcut the original baseline relied on.

## Architectural delta since 2026-04-30 (F23 → F36)

This batch closed 14 task IDs + two refactor commits. Group by goal:

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

### Other
- **F28** (531dedd) — Daemon log auto-path `.asterism/logs/<problem>_<model>_<ts>.log` + tee + retention (keep 20 newest).
- **F34** (7db1603) — `TACTIC_TRY_LIST` adds `norm_cast`, `push_cast`, `ring`, `ring_nf`, `field_simp`, `positivity`, `grind`. Each fast-path hit saves an entire Builder pipeline.
- **F15** (a7caf1a) — Root.lean lifecycle init guard. Reject non-sorry, non-wrap Root.lean unless `--force`. Architecture §3.5 documents three-state lifecycle.
- **OR_FANOUT_DEFAULT** 3 → 2 (f1fbbf0) — less wasteful per-goal default.

## Ablations / dead ends (don't re-investigate)

- F27 tools removal is NOT the wilson Sonnet regression cause (verified by `ASTERISM_CLAUDE_TOOLS=default` ablation — Sonnet still timed out on Wilson core).
- Wilson core `(↑(p-1)! : ZMod p) = -1` is a single-step lemma Sonnet can only close via `Nat.prime_iff_fac_equiv_neg_one` (Mathlib helper not in Manifest's forbidden_lemmas). When Sonnet recalls this name, wilson finishes in ~15 min; when it doesn't, no amount of decomposition helps because the sub-goal IS the parent's hardest step.
- baseline 6b0cf3b's "fast" wilson WAS this Mathlib helper shortcut. Not really a deeper proof — commit message itself acknowledges the forbidden_lemmas gap.

## Recent commits (since previous STATUS at 8905d84)

| Commit | Topic |
|---|---|
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
- **#238 F25**: Sibling sub-goal dedupe. Compactness OR-parallel run showed s148/s150/etc producing byte-identical sub-goals across siblings — F25 would alias them. Empirical lever vs F33 / F36 lever is smaller; design noted but not implemented.
- **F37** (placeholder): OR-parallel → passive trigger. User-proposed pivot from eager OR_FANOUT to lazy expansion. Spec to be detailed post-compact.
- **F38** (placeholder): Gemini provider via free-tier API. New `Tooling/llm/gemini_api.py`. Spec to be detailed post-compact.

## Test count

309 unit tests + 2 lake-integration tests (skipped if lake missing). All green at HEAD.

## Tooling LOC

~9900 lines (Tooling + tests combined; Tooling alone ~5000). Mostly steady; F33 added ~500 net.

## Things to verify post-compact

1. `git log --oneline -16` — top should be 945c8d4 (F33 inline follow-up).
2. Working tree: `Problems/wilson/` should reflect the regression-test re-proof (Root.lean wrap form `:= s249`); maxfinsat_complete is fully removed; `.asterism/logs/`, `.asterism/`, `Tooling/.lemma_cache.json`, `*.log` all gitignored.
3. `python -m pytest tests/ -q --deselect tests/test_dedupe.py::test_batch_isdefeq_real_lake --deselect tests/test_lemma_lookup.py::test_lookup_batch_real_lake` should show **309 passed**.
4. `Problems/wilson/playbook.md` non-empty (1 idiom from regression run).

## User preferences (memory pinned)

- Long-term clean over short-term patch
- "建議?" / "看一下" = consult signal, propose first, wait for "ok" / "動手"
- Don't fix prompts when frameworks could fix the root cause; if prompt is right tool, scope to specific model
- After several additive commits, pause for consolidation pass (this STATUS update + section-list refactor + diagnostics table are exactly that)
- Per-problem experience belongs in plain-text Markdown next to the problem, not in DB (F22 playbook design)
- Prompt cuts have second-order reasoning-quality cost — F29 → F36 lesson: don't only weigh tokens
