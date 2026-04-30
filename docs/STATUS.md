# Asterism v2 — Current Status

Updated 2026-05-01. Compaction-safe handoff note.

## Proved problems (4)

| Problem | Commit | Wall-clock | Axioms |
|---------|--------|-----------|--------|
| wilson | 6b0cf3b | ~15 min | propext, Classical.choice, Quot.sound |
| compactness | 46c8941 | ~60 min | propext, Classical.choice, Quot.sound |
| cantor | 6bd6c15 | ~5 min | [] (constructive) |
| gen_generates | 4c6f423 | ~30 min | propext, Quot.sound |

All on Sonnet via Claude CLI provider. SoT for design: `docs/architecture.md` v2.5 (lagging 11+ commits — separate update task pending).

## Provider stack (commit ca6aec9, F22-extended)

`Tooling/llm/`：Provider registry by env. ClaudeCliProvider (default) + OpenAIProvider (vLLM / Ollama / LM Studio).

- `ASTERISM_LLM_PROVIDER=claude` (default) → Claude CLI subprocess
- `ASTERISM_LLM_PROVIDER=openai` + `ASTERISM_LLM_BASE_URL` + `ASTERISM_LLM_MODEL` → HTTP single-shot
- Single-shot has companion prompt files `prompts/*_singleshot.md`
- **F22 added `Provider.complete_text(prompt, timeout_sec) → str | None`** for short auxiliary calls (idiom extract / playbook curate). Both providers implement; failures return None.

## Architectural delta since 2026-04-30 (F16 → F22 + refactors)

Six framework changes plus two consolidation passes. All in main.

### Cascade rules — symmetric goal-shelve handling (F12 + F16)
`_propagate_shelve(conn, goal_id)` in dispatcher.py now cascades a shelve event in BOTH directions:
- **Upward (F12)**: kill 'proposed' strategies that depend on the shelved goal as a sub-goal; reopen their parent goals if no live strategy remains.
- **Inward (F16)**: kill 'proposed' strategies whose `goal_id` IS the shelved goal (own strategies — they're now moot).

DB invariant restored: `strategy.status='proposed'` implies parent goal alive.

### Diagnostic hints (F9 + F13 + F17 → consolidated table)
`Tooling/diagnostics.py` `_HINT_PATTERNS: list[_HintPattern]` table replaces six per-pattern if-blocks. Patterns: bad import, no-such-file (Mathlib path with `\\→/` transform), unknown identifier, unknown constant, autoImplicit hint, unknown tactic. All `re.IGNORECASE` after F17 — Lean's casing varies (`unknown identifier` lowercase vs `Unknown constant` capital). Adding a new pattern is one entry.

### Lemma signature lookup (F20)
`Tooling/lemma_lookup.py` runs `lake env lean` against `import Mathlib` + `#check @<name>` queries to fetch real signatures. Persistent JSON cache `.lemma_cache.json` keyed on `(toolchain_version_hash, lemma_name)`; `lake update` invalidates implicitly. Mathlib loading dominates (~20s cold), so all of one goal's names go in one subprocess. agent.py's compile_context emits a `## Lemma references (resolved from Mathlib)` section with `name : signature` bullets. Names not found produce no bullet.

### Per-problem playbook (F22)
`Tooling/playbook.py`. After each Verify=proved, dispatcher fires `maybe_record_idiom`:
1. Short LLM call extracts a `- **<pattern>**: <idiom>` bullet (or `SKIP` for trivial proofs).
2. If `Problems/<p>/playbook.md` < CAP=10 entries → append.
3. If at CAP → second LLM call asks `REPLACE n` or `KEEP`. Self-curation: candidate must beat an incumbent or get discarded.

compile_context injects playbook between strategic_notes and past failures. Boundary: Manifest = author intent (static); playbook = agent experience (dynamic). Both inject; non-overlapping roles.

### Configurable thresholds (F18)
- `BUILDER_THRESHOLD_DEFAULT = 5` (was hardcoded `2` = 3 Builder tries; now 5 tries before Backward fallback)
- `SHELVE_THRESHOLD_DEFAULT = 8` (was 7; now 5 Builder + up to 3 Backward before shelve)
- Env: `ASTERISM_BUILDER_THRESHOLD`, `ASTERISM_SHELVE_THRESHOLD`. Validator: SHELVE > BUILDER required.
- Tuned for weaker models (Haiku-class) which iterate productively but need more rounds. Sonnet runs can tighten back via env.
- `OR_FANOUT_DEFAULT = 2` (was 3) — less wasteful per goal.

### Pipeline auto-inject (F17 layer C)
`pipeline._ensure_import_mathlib`: when a Backward worker writes a sub-goal lemma file with no `^import\s` line at all (Haiku occasionally does this), framework prepends `import Mathlib`. Idempotent in Lean 4. Catches "Unknown constant Nat.factorial" failures before they happen.

### Refactors (no behavior change)
| Commit | Change |
|---|---|
| 4d8caba | `compile_context` → section-list pattern (10 pure section funcs, main fn just iterates) |
| ad33753 | `parse_lake_stderr` → `_HintPattern` table |

## Wilson Haiku probes summary

Three rounds during this iteration cycle, all stopped before convergence (intentional — goal was framework BUG-hunting, not proving).

| Round | When | Setup | Outcome | Lessons |
|---|---|---|---|---|
| Probe 1 | pre-F12 | Haiku, default thresholds | Root stuck attempting=4 (zombie strategies) | F12 + F13 + F14 |
| Probe 2 | post-F12, pre-F16 | Haiku, OR_FANOUT=2 | 19/42 proved, depth 4, F12 cascade live-validated | F16 + F17 + F18 |
| Probe 3 | post-F18 | Haiku, BUILDER=5/SHELVE=8 | 17/?? proved, depth 4 still, tree narrower (-75%) | F19/F20 designed, F18 effect partially confirmed |

Failure mode classified across all probes: Haiku knows lemma families but writes wrong arg order / hallucinated names / missing `Fact`/`NeZero` instances. Direction is right, API specifics are wrong → motivates F20 (lemma signature lookup) + F22 (playbook for cross-strategy idiom transfer).

## Recent commits (since previous STATUS at 6390221)

| Commit | Topic |
|---|---|
| ad33753 | Consolidate hint regexes into _HintPattern table |
| 4d8caba | Refactor compile_context into section-list pattern |
| f766707 | F22 — per-problem playbook |
| 1011f1f | F20 — lemma signature lookup |
| 8881383 | F18 — configurable BUILDER/SHELVE thresholds |
| f1fbbf0 | OR_FANOUT_DEFAULT 3 → 2 |
| 6dfd7ce | F17 — hint regex case-insensitive + auto-inject Mathlib |
| b6c3896 | F16 — symmetric cascade |

## Next pending

- **#227 F10**: Sonnet + maxfinsat_complete to live-validate Dedupe v4 true positives. Cost: Sonnet tokens. Order: do AFTER F15 (so Root.lean state is clean) or directly if user prioritizes.
- **#232 F15**: Root.lean lifecycle hardening — init guard for non-sorry Root + auto promote-to-wrap on root_proved + README §Root.lean lifecycle. Architecture-level cleanup.

Future deferred (mentioned during F22 design, not on task list):
- Playbook seed command (one-shot extract idioms from already-proved problems via single LLM call).
- F21 — TACTIC_TRY_LIST expansion (`field_simp`, `push_cast`, `decide`); only useful if probe data shows Builder fast-path failures.
- F19 — richer Context.md prior-attempts summary; deferred after F22 probe data review.
- docs/architecture.md v2.6 — SoT lagging 11+ commits; separate doc maintenance pass.

## Test count

222 unit tests + 2 lake-integration tests (skipped if lake missing). All green at HEAD.

## Tooling LOC

~3900 lines Python (was 2300 pre-F16). Growth: F20 (`lemma_lookup.py` 200), F22 (`playbook.py` 250 + 2 prompt files 70), `complete_text` provider extension, F18 thresholds + tests, agent.py refactor reorganized but didn't shrink.

## Things to verify post-compact

1. `git log --oneline -12` to confirm history (top should be ad33753 if no further work)
2. Working tree clean (`Problems/maxfinsat_complete/` untracked is fine; `wilson_haiku2.log` / `wilson_haiku3.log` / `asterism.db.preprobe` fine to ignore or delete)
3. `python -m pytest tests/ -q --deselect tests/test_dedupe.py::test_batch_isdefeq_real_lake --deselect tests/test_lemma_lookup.py::test_lookup_batch_real_lake` should show **222 passed**

## User preferences (memory pinned)

- Long-term clean over short-term patch
- "建議?" / "看一下" = consult signal, propose first, wait for "ok" / "動手"
- Don't fix prompts when frameworks could fix the root cause; if prompt is right tool, scope to specific model
- After several additive commits, periodically pause for consolidation pass (this STATUS update + 4d8caba + ad33753 are exactly that)
