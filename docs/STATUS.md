# Asterism v2 — Current Status

Updated 2026-04-30. Compaction-safe handoff note.

## Proved problems (4)

| Problem | Commit | Wall-clock | Axioms |
|---------|--------|-----------|--------|
| wilson | 6b0cf3b | ~15 min | propext, Classical.choice, Quot.sound |
| compactness | 46c8941 | ~60 min | propext, Classical.choice, Quot.sound |
| cantor | 6bd6c15 | ~5 min | [] (constructive) |
| gen_generates | 4c6f423 | ~30 min | propext, Quot.sound |

All on Sonnet via Claude CLI provider. SoT for design: `docs/architecture.md` v2.5.

## Provider stack (commit ca6aec9)

`Tooling/llm/`：Provider registry by env. ClaudeCliProvider (default) + OpenAIProvider (vLLM / Ollama / LM Studio).

- `ASTERISM_LLM_PROVIDER=claude` (default) → Claude CLI subprocess
- `ASTERISM_LLM_PROVIDER=openai` + `ASTERISM_LLM_BASE_URL` + `ASTERISM_LLM_MODEL` → HTTP single-shot
- Single-shot has companion prompt files `prompts/*_singleshot.md` that the provider transparently picks.

## Local model probe (Qwen3-30B-Instruct via Ollama)

Tried as cantor experiment. Result: not viable as Asterism main LLM. Plumbing OK; model writes Lean syntax-correct but lemma-wrong patches; doesn't follow Backward multi-file output protocol; cantor shelved at attempts=7.

## Haiku probe

Wilson with claude-haiku-4-5 (commit run after F11). Result: not viable solo. 4 sub-goals shelved (Mathlib stale knowledge — uses old `Mathlib.Data.Nat.Prime` paths). 3 sub-goals proved. Root stuck attempting at attempts=4 (zombie strategies, F12 just fixed).

## Recent fixes (uncommitted-impact list, all in main)

| Commit | Fix |
|--------|-----|
| 7f27840 | F14 dedupe rc-based correctness, F12 zombie strategy propagate, F13 smart stderr truncate |
| 333d112 | prompt rules wording sync (backward / backward_singleshot) |
| 7768b20 | F11 daemon idle-exit + F9 structured lake-stderr hints |
| 5482f28 | F8 provider-side markdown-fence strip + .txt artifacts |
| ca6aec9 | F7 step 2 OpenAI provider |
| b7c1053 | F7 step 1 LLM provider registry abstraction |

## Next pending

- **#227 F10**: Live-validate Dedupe v4 on a real run (Sonnet + maxfinsat_complete is the proposed candidate). User said this happens after compact. F14 just fixed the false-positive bug; live run is needed to observe true positives.
- **#227 only** is left in pending (besides this F10).

## Test count

149 unit tests + 1 lake-integration test (skipped if lake missing). All green at HEAD.

## Tooling LOC

~2300 lines Python (was 1490 at v2.5 doc). Growth mostly in `dedupe.py`, `diagnostics.py`, `llm/` provider abstraction, prune helpers, F12 propagation.

## Things to verify post-compact

1. `git log --oneline -10` to confirm history
2. Working tree clean (only `Problems/maxfinsat_complete/` untracked is fine)
3. `python -m pytest tests/ -q --deselect tests/test_dedupe.py::test_batch_isdefeq_real_lake` should show 149 passed

## User preferences (memory pinned)

- Long-term clean over short-term patch
- "建議?" / "看一下" = consult signal, propose first, wait for "ok" / "動手"
- Don't fix prompts when frameworks could fix the root cause; if prompt is right tool, scope to specific model
