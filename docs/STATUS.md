# Asterism v2 — Current Status

Updated 2026-05-01 (post-Haiku-wilson). Compaction-safe handoff note.

## Proved problems (4 + 1 weak-model variant)

| Problem | Commit | Prover | Wall-clock | Axioms |
|---------|--------|--------|-----------|--------|
| wilson | 9c2c2a0 | **Haiku** | 39.5 min | propext, Classical.choice, Quot.sound |
| wilson (Sonnet, replaced) | 6b0cf3b | Sonnet | ~15 min | propext, Classical.choice, Quot.sound |
| compactness | 46c8941 | Sonnet | ~60 min | propext, Classical.choice, Quot.sound |
| cantor | 6bd6c15 | Sonnet | ~5 min | [] (constructive) |
| gen_generates | 4c6f423 | Sonnet | ~30 min | propext, Quot.sound |

**Headline**: 9c2c2a0 is Asterism's first end-to-end proof by a weak model (claude-haiku-4-5). 5x more pipelines + 2.6x more wall-clock than Sonnet, but identical axioms — framework-side intelligence (F16-F24) compensates for model API gaps.

## Provider stack (commit ca6aec9, F22-extended)

`Tooling/llm/`：Provider registry by env. ClaudeCliProvider (default) + OpenAIProvider (vLLM / Ollama / LM Studio).

- `ASTERISM_LLM_PROVIDER=claude` (default) → Claude CLI subprocess
- `ASTERISM_LLM_PROVIDER=openai` + `ASTERISM_LLM_BASE_URL` + `ASTERISM_LLM_MODEL` → HTTP single-shot
- Single-shot has companion prompt files `prompts/*_singleshot.md`
- **F22 added `Provider.complete_text(prompt, timeout_sec) → str | None`** for short auxiliary calls (idiom extract / playbook curate). Both providers implement; failures return None.

## Architectural delta since 2026-04-30 (F16 → F24 + refactors)

Eight framework changes plus two consolidation passes. All in main.

### Cascade rules — symmetric goal-shelve handling (F12 + F16)
`_propagate_shelve(conn, goal_id)` in dispatcher.py cascades a shelve event in BOTH directions:
- **Upward (F12)**: kill 'proposed' strategies that depend on the shelved goal as a sub-goal; reopen their parent goals if no live strategy remains.
- **Inward (F16)**: kill 'proposed' strategies whose `goal_id` IS the shelved goal (own strategies — they're now moot).

### Cascade race fix (F24)
`cascade_one` no-op guards extended to `'shelved'` for Goal target_kind (matching the existing `'proved'` guard). For Strategy target_kind: parent goal shelved → mark strategy dead. Plus pipeline.run_backward re-checks goal status before linking sub-goals; aborts cleanly with `failure_reason='goal_no_longer_open'` if shelved/proved during the in-flight pipeline. Defense-in-depth: pipeline-side prevents orphan creation, cascade-side handles late races.

### Diagnostic hints (F9 + F13 + F17 → consolidated table)
`Tooling/diagnostics.py` `_HINT_PATTERNS: list[_HintPattern]` table replaces six per-pattern if-blocks. All `re.IGNORECASE` after F17. Adding a new pattern is one entry.

### Lemma signature lookup (F20)
`Tooling/lemma_lookup.py` runs `lake env lean` against `import Mathlib` + `#check @<name>` queries to fetch real signatures. Persistent JSON cache `.lemma_cache.json` keyed on toolchain hash. compile_context emits `## Lemma references (resolved from Mathlib)` section. Names not found produce no bullet (no fabricated info).

### Per-problem playbook (F22)
`Tooling/playbook.py`. After each Verify=proved, dispatcher fires `maybe_record_idiom`:
1. Short LLM call extracts a `- **<pattern>**: <idiom>` bullet.
2. Append if under CAP=10; else second LLM call decides REPLACE n / KEEP. Self-curation.
3. compile_context injects playbook between strategic_notes and past failures.

Boundary: Manifest = author intent; playbook = agent experience. Non-overlapping roles.

### Configurable thresholds (F18)
- `BUILDER_THRESHOLD_DEFAULT = 5` (was hardcoded `2` = 3 Builder tries)
- `SHELVE_THRESHOLD_DEFAULT = 8` (was 7)
- `OR_FANOUT_DEFAULT = 2` (was 3)
- All env-overridable via `ASTERISM_*`.

### Pipeline auto-inject (F17 layer C)
`pipeline._ensure_import_mathlib`: prepends `import Mathlib` when a Backward-generated lemma file has no `^import\s` line.

### Batch lake build (F23)
`pipeline.run_backward`'s sequential `for t in placed: _lake_build(...)` loop replaced with single `_lake_build_batch(workspace, placed)` invocation. Lake parallelizes independent sub-goal builds, serializes the strategy assembly. **Effect**: Backward succeeded avg dropped from ~517s → ~151s (-71%) across the Haiku wilson run.

### Refactors (no behavior change)
| Commit | Change |
|---|---|
| 4d8caba | `compile_context` → section-list pattern |
| ad33753 | `parse_lake_stderr` → `_HintPattern` table |

## Wilson Haiku probe series

| Round | Setup | Outcome | Lessons |
|---|---|---|---|
| Probe 1 | pre-F12 | Stuck attempts=4 (zombie strategies) | F12 + F13 + F14 |
| Probe 2 | post-F12, OR=2 | 19/42 proved, depth 4 | F16 + F17 + F18 |
| Probe 3 | post-F18 | 17 goals, depth 4 narrower | F20 + F22 designed |
| Probe 4 | post-F22 | Race bug surfaced (goal stuck attempts=8/attempting) | F23 + F24 |
| **Probe 5** | post-F24 | **PROVED, 39 pipelines, 39.5 min** | playbook entries captured |

Failure-mode evolution: probes 1-3 dominated by zombie strategies + tree blow-up; probe 4 surfaced OR-race; probe 5's only remaining stuck point (goal 101 = `(-1 : ZMod p).val = p - 1` variant) recovered via Backward recursion. Stack contributions all necessary, none alone sufficient.

## Recent commits (since previous STATUS at 8905d84)

| Commit | Topic |
|---|---|
| 9c2c2a0 | **Wilson proved by Haiku — first weak-model end-to-end** |
| 34644c0 | F23 — batch lake build |
| efd0236 | F24 — cascade race fix |
| 8905d84 | (this STATUS's predecessor — F16-F22 architectural delta) |

## Next pending

- **#227 F10**: Sonnet + maxfinsat_complete to live-validate Dedupe v4 true positives. Independent of F15.
- **#232 F15** (re-scoped): promote-to-Root proven to already work (existing `prune.reconcile_proved_goals` rewrites Root.lean to wrap form on root_proved, observed in Haiku run). F15 narrows to: init-side guard for non-sorry Root.lean + README §Root.lean lifecycle. Implementation lighter than originally scoped.

Future deferred:
- Playbook seed command (one-shot extract idioms from already-proved problems).
- F21 — TACTIC_TRY_LIST expansion; reconsider after more probe data.
- F19 — richer Context.md prior-attempts summary; F20+F22 may have already addressed the gap.
- docs/architecture.md v2.6 — SoT now ~13 commits behind; separate doc pass.
- Cross-problem playbook validation: run Haiku on cantor / compactness with their playbook seeded from the Sonnet proofs.

## Test count

231 unit tests + 2 lake-integration tests (skipped if lake missing). All green at HEAD.

## Tooling LOC

~3900 lines Python (mostly steady since 2026-04-30 mid; F23/F24 added ~50 lines net).

## Things to verify post-compact

1. `git log --oneline -10` — top should be 9c2c2a0 (Haiku wilson proof) or further work.
2. Working tree clean. `Problems/maxfinsat_complete/` is intentionally untracked. `wilson_haiku*.log` + `Tooling/.lemma_cache.json` + `asterism.db.*` are now gitignored.
3. `python -m pytest tests/ -q --deselect tests/test_dedupe.py::test_batch_isdefeq_real_lake --deselect tests/test_lemma_lookup.py::test_lookup_batch_real_lake` should show **231 passed**.
4. `Problems/wilson/playbook.md` should contain 2 entries (the two Haiku idioms).

## User preferences (memory pinned)

- Long-term clean over short-term patch
- "建議?" / "看一下" = consult signal, propose first, wait for "ok" / "動手"
- Don't fix prompts when frameworks could fix the root cause; if prompt is right tool, scope to specific model
- After several additive commits, periodically pause for consolidation pass
- Per-problem experience belongs in plain-text Markdown next to the problem, not in DB (F22 playbook design)
