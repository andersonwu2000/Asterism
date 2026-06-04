# SG run #12 — autonomous monitor log

HEAD: adde5aa (Backward: revert to lake-build verification, disable LSP MCP)
Started: 2026-05-10T~~UTC~~

## Hypothesis being tested

Reverting Backward's LSP MCP tools (`apply_edit`/`errors_at`/`goal_at`/`validate_file`) recovers the pre-LSP Sonnet SG success path (last verified `9d05d19` 2026-05-05, 4h 16min).

Theory: Backward's task is decomposition shape (which sub-goal types compose), not proof body. LSP feedback is body-level — wrong granularity. Removing it forces agent to think about decomposition rather than fight indentation/syntax via apply_edit + errors_at iteration cycles.

Builder still uses LSP (single-goal proof body — right granularity).

## Validation focus

1. **Backward decomposition speed**: agents should ship `patch.lean` + `new_*.lean` faster (no LSP-iteration trap). Compare to run #11 Goal=288 ba921474 (15min, 26 thinking + 42 tool_use cycle, didn't converge).
2. **Goal=289-equivalent (`kelly_minimizer_gives_ordinary_line` or new slug)**: does agent ship a decomposition / decline this time? With LSP gone, agent can't iterate on body — must commit to a shape.
3. **Lake-build retry loop**: do warm retries with lake error inlined actually progress (s222-class)?
4. **Watchdog v4 still works on Backward**: trap detection still fires when Sonnet thinks deeply (not LSP-related).
5. **Builder still uses LSP**: sub-goal Builder dispatches show `[mcp]` traffic; Backward dispatches don't.

## Anomaly cuts

- Path fix regression (any `patch.lean`/`new_*.lean`/`_progress.md` in `Problems/sylvester_gallai/` root)
- gateway crash loop / hot_rate < 30% sustained
- ≥3 consecutive thinking traps producing no deliverable on Backward
- shelved% > 60%

## Reference baselines

- run #4 (pre-LSP, pre-Phase 7): 270min, 4 proved, 5 shelved
- run #10 (LSP + watchdog v3): 30min cut, 3 traps + path BUG
- run #11 (LSP + watchdog v4 + path fix): 108min cut, 1 sub proved, 1 sub bailing in trap loop
- **run #12 (LSP off for Backward)**: ?

## Cadence findings (autonomous)

### 2026-05-10 21:17 local — cadence 1 (+3 min, post-launch)

Daemon pid 22272 alive cpu=0.27s (just started). Goal=290 main, 1 strategy s237 proposed, 0 attempts.

## ✅ LSP-disable verified for Backward

Gateway `/health`: **hot_rate=null, n_hot=0, n_cold_warmup=0** — gateway has 0 acquires globally. Confirms nothing is touching the LSP worker pool yet.

Active Backward dispatch attempts dir `804b557b` contents:
```
Context.md        ← framework-written context
patch.lean        ← skeleton pre-written by framework
```

**No `_mcp.jsonl`, no `_gateway_session.token`, no `_mcp_config.json`** — confirms `mcp_config_path=None` plumbed through correctly. Backward agent has no `--mcp-config` flag, no apply_edit / errors_at / goal_at / validate_file tools.

Compare to run #11's Backward attempts dirs (e.g. 13218851 from cadence 1) which all had `_mcp.jsonl` accumulating tool_call traffic.

## Status

Daemon log:
```
[dispatcher] start, pool=15, problems=['proj_nonexpansive', 'sylvester_gallai']
[gateway] launching subprocess (port 8765)
[gateway] ready after 29s
[dispatch] Backward Goal=290 pid=804b557b
```

Single Backward dispatch in flight, no events yet (need ≥ 11 min for any watchdog activity, ≥ 15 min for subprocess timeout).

No cut. Continue. Next cron :37 — should see whether Backward agent ships decomposition faster without LSP iteration trap.

### 2026-05-10 21:38 local — cadence 2 (+24 min)

Daemon pid 22272 alive cpu=0.61s. Gateway hot_rate=0.0 (n_cold_warmup=3, n_hot=0 — workers warmed but no Builder acquires yet, no sub-goal Builder dispatches have fired).

Status: Goal=290 main → **success** (split into 2 sub-goals). 3 strategies, 3 live, 0 dead.
- 291 sg_kelly_min_exists (open, attempts=0)
- 292 sg_kelly_ordinary (open, attempts=0)

Daemon log:
```
[dispatch] Backward Goal=290 pid=804b557b
[watchdog] sid=2ff4dc2d trap_check 660s reached;
  trap-but-not-silent (state=mid-thinking last_stop_reason=— silence=272s);
  deferring to subprocess timeout
[dispatch] Backward Goal=291 pid=ba210726
[dispatch] Backward Goal=292 pid=ada0b923
[reflection] backward main: wrote (+1 line)
[cascade] Backward Goal=290 → success
```

## ✅ Backward LSP-disable validated end-to-end

| Check | Result |
|---|---|
| Goal=290 Backward dispatch attempts dir 804b557b had `_mcp.jsonl`? | ✗ no MCP file (LSP genuinely disabled) ✓ |
| Goal=290 Backward shipped patch.lean + 2 new_*.lean? | ✓ cascade success |
| Watchdog still fires on Backward (thinking trap unrelated to LSP)? | ✓ sid 2ff4dc2d trap-but-not-silent observed |
| Gateway acquires from Backward? | 0 (n_hot=0, only n_cold_warmup=3 from gateway warmup itself) |

## Comparison vs run #11 (LSP enabled)

| Metric | run #11 Goal=287 main | run #12 Goal=290 main |
|---|---|---|
| Time to ship main split | ~12 min (cold + retry needed) | ~10 min (single attempt success) |
| Sub-goal slugs | kelly_minimizer_exists, kelly_minimizer_gives_ordinary_line | sg_kelly_min_exists, sg_kelly_ordinary |
| Watchdog fires | trap-but-not-silent at silence=210s | trap-but-not-silent at silence=272s (longer silence — agent thinks more without LSP) |

Sub-goals 291/292 = kelly's existence + ordinary-line proofs. Run #11 Goal=289 (~equivalent of 292) trapped 4×. About to see if 292 escapes that pattern with LSP off.

## Anomaly notes

- `.attempts/1603afe3-...` dir present with run #11 strategy content (s236, kelly_minimizer_gives_ordinary_line). Pre-run-#12 cleanup `rm -rf .attempts/*` apparently missed it (filesystem race or recovery race). Inert — not affecting run #12. Will leave for now.

No cut. Continue. Next cron :57 — sub-goals 291/292 about to hit watchdog wall_cap if they trap.

### 2026-05-10 21:57 local — cadence 3 (+43 min)

Daemon pid 22272 alive cpu=1.13s. Gateway hot_rate **0.31** (n_hot=9, n_cold_warmup=20 — Builder spawns warming gateway, hot_rate threshold borderline but fine).

Status: 5 goals.
- 290 main attempting
- **291 sg_kelly_min_exists PROVED** (depth=1, attempts=2)
- 292 sg_kelly_ordinary open (depth=1, attempts=1)
- **293 kelly_ne_of_not_collinear PROVED** (depth=2)
- **294 kelly_sq_dist_pos_of_ne PROVED** (depth=2)

3 strategies (s237/s239 live, s238 dead via cascade success), 2 dead_attempts (lake_build_error ×2).

## ✅ Goal=291 (sg_kelly_min_exists) PROVED via no-LSP Backward

```
[dispatch] Backward Goal=291 pid=ba210726
[watchdog] sid=03ba5064 trap_check 660s reached;
  trap AND silent (state=mid-thinking last_stop_reason=— silence=445s);
  killing for rescue
[fresh-rescue combined] broken_sid=03ba5064 → fresh_sid=4306dc7a budget=420s
[fresh-rescue combined] sid=4306dc7a rc=124 dur=420s   ← combined timed out
[reflection] backward sg_kelly_min_exists: wrote (+1 line)
[cascade] Backward Goal=291 → success
```

Wait — sid 03ba5064 IS Goal=291's main sid (not Goal=292's as I might have thought). It trapped at silence=445s, combined takeover ran, combined timed out 420s without ship. **Yet Goal=291 cascaded success**.

This means: after combined takeover failed, helper buffered agent_stuck_thinking + retried. Next attempt (warm or fresh) succeeded (since combined bumped sid). The retry shipped the decomposition. **Goal=291 shipped on attempts=2**.

## Comparison to run #11 (LSP enabled)

| Goal class | run #11 (LSP on) | run #12 (LSP off) |
|---|---|---|
| main split | 1 trap-takeover then success | success first try |
| sg_kelly_min_exists / kelly_minimizer_exists | proved on attempts=2 (1 takeover) | **proved on attempts=2 (1 trap takeover)** ← SIMILAR |
| sg_kelly_ordinary / kelly_minimizer_gives_ordinary_line | **4× trap, never proved** | Goal=292 attempts=1 in progress, may trap too |
| sub-leaves (depth 2) | not reached in run #11 | **2 proved (293, 294)** ← FURTHER |

Run #12 reached **depth 2 with 2 leaves proved**. Run #11 never got past depth 1. **Net deliverables: Goal=290 + 291 + 293 + 294 = 4 cascade successes** (with 290 still attempting waiting for 292).

## v4 trap detector observed (Backward, no-LSP)

- sid 2ff4dc2d (Goal=290 Backward): trap-but-not-silent silence=272s → defer (success)
- sid 03ba5064 (Goal=291 Backward): **trap AND silent silence=445s** → combined takeover (failed but retry succeeded)

silence=445s for Backward without LSP is consistent with the "fewer tools → longer silence" prediction. AND condition still working as designed (kills only when both signals fire).

## Open

Goal=292 (sg_kelly_ordinary) is the equivalent of run #11's stuck Goal=289. Current attempts=1, retry in flight. Watchdog will fire at next ~11 min. Will see if this hypothesis (Sonnet's kelly_ordinary trap is goal-content not LSP-iteration) holds — if Goal=292 traps repeatedly like Goal=289 did, hypothesis confirmed (Sonnet model issue). If Goal=292 eventually proves, LSP-iteration was a contributing factor.

No cut. Continue. Next cron :17.

### 2026-05-10 22:18 local — cadence 4 (+64 min)

Daemon pid 22272 alive cpu=1.31s. Gateway hot_rate 0.31 stable.

Status (no change from cadence 3 in goal proves):
- 290 main attempting, 291 PROVED, **292 attempts=2** (was 1, +1 attempt buffered), 293/294 PROVED
- 2 strategies live, 2 dead_attempts (lake_build_error ×2, no agent_bailed yet)
- Verify Strategy=238 → proved (Goal=291's strategy after sub-leaves closed)

## Goal=292 trap chain — same pattern as run #11 Goal=289

```
[watchdog] sid=03ba5064 trap_check 660s; trap AND silent silence=445s; killing
[fresh-rescue combined] broken_sid=03ba5064 → fresh_sid=4306dc7a budget=420s
... combined runs 420s, times out ...
[fresh-rescue combined] sid=4306dc7a rc=124 dur=420s
[watchdog] sid=4306dc7a trap_check 660s; trap AND silent silence=528s; killing
[fresh-rescue combined] broken_sid=4306dc7a → fresh_sid=61728eac budget=420s
... combined 2 runs 420s, times out ...
[fresh-rescue combined] sid=61728eac rc=124 dur=420s
[watchdog] sid=61728eac trap_check 660s; trap-but-not-silent silence=257s; defer
```

**Goal=292 (sg_kelly_ordinary) traps repeatedly even without LSP.** This confirms the kelly_ordinary class trap is **goal-content driven, not LSP-iteration driven**. Sonnet's deep-thinking on Kelly's perpendicular-distance contradiction is the dominant cost regardless of LSP availability.

Notable: silence values for these no-LSP Backward retries:
- 445s (initial main, Goal=292)
- 528s (combined #1)
- 257s (combined #2 — agent emitted SOME tool_use, then stopped)

Without LSP, Backward agent's silence naturally larger (300-500s range) — silence threshold 300s is borderline. AND condition still working as designed.

## Net comparison still favors run #12

| Wall | run #11 (LSP on) | run #12 (LSP off Backward) |
|---|---|---|
| +64 min | 1 main + 1 sub proved | 1 main + 1 sub proved + **2 sub-leaves proved (depth 2)** |

Run #12 has 4 deliverables vs run #11's 2 at same wall time. Goal=292 is matching run #11's Goal=289 trap pattern but the rest of the tree is progressing.

## Hypothesis status

- ✅ Backward without LSP CAN ship decomposition (Goals 290, 291)
- ✅ Cross-pipeline retry style not strictly required for some goals (Goal=290 succeeded in-pipeline)
- ❌ kelly_ordinary class STILL traps without LSP — Sonnet model issue, not LSP
- ⚠️ Run #12's progress beyond run #11 is mostly because Goal=291 succeeded faster + sub-leaves closed quickly via Builder

→ The big regression vs 9d05d19 is NOT LSP alone. Need 9d05d19 cadence data to compare.

No cut. Continue. Next cron :43 (9d05d19) / :37 (run #12).

### 2026-05-10 22:38 local — cadence 5 (+84 min)

Daemon pid 22272 alive cpu=1.73s. Gateway hot_rate 0.31 stable.

Status: Goal=292 attempts=**3** (was 2). 1 dead_attempt added: `agent_bailed` (from stage 3 of TIMEOUT-trap takeover). Total 5 dead_attempts: 2 agent_stuck_thinking, 2 lake_build_error, 1 agent_bailed.

`.drafts/backward_g292.md` exists ✓ — carry-over note from agent_bailed for next dispatch.

## Goal=292 first-pipeline death timeline (~46 min wasted)

```
00:00  Backward Goal=292 dispatched (pid ada0b923, sid 03ba5064)
11:00  watchdog: trap AND silent silence=445s; kill
11:00  combined takeover (sid 4306dc7a, 420s budget)
17:00  combined timeout 420s rc=124
17:00  warm retry stays on 4306dc7a (within same pipeline retry loop iter)
28:00  watchdog on 4306dc7a: trap AND silent silence=528s; kill
28:00  combined takeover #2 (sid 61728eac, 420s)
35:00  combined #2 timeout 420s rc=124
35:00  warm retry on 61728eac
46:00  watchdog on 61728eac: trap-but-not-silent silence=257s; defer
46:00  subprocess timeout 900s
46:00  TIMEOUT-trap → fresh-sid stage 2 (50f52172, 240s) → timeout
50:00  stage 3 (d1d42ccf, 180s budget) → 137s ship agent_bailed
50:00  cascade Backward Goal=292 → failed
50:00  Goal=292 retry pipeline 604be459 dispatched
```

**~50 min wasted on a single pipeline before fail.** Compare to 9d05d19 Goal=9 (kelly_ordinary equivalent): each cross-pipeline attempt takes ~5 min, third attempt succeeded.

→ run #12's "in-pipeline retry + multi-stage takeover" exhausts ~5x more wall before giving up than 9d05d19's "fail fast + cross-pipeline".

## Net comparison

| Wall | run #12 | 9d05d19 |
|---|---|---|
| ~50 min | 4 proved (290/291/293/294) | 9 proved (depth 3) |
| Avg time per failed Backward pipeline | 50 min (Goal=292's first) | 5 min |
| Trap takeover machinery used | combined×2 + stage 2 + stage 3 = 4 fresh-sid spawns | 0 |

**The framework's elaborate trap-recovery machinery (v3/v4 watchdog + combined takeover + 2-stage takeover) is consuming budget that 9d05d19 spent on fresh attempts.** Each "save" of a doomed pipeline costs ~45 min that could have funded 9× cross-pipeline retries.

No cut. Continue. Next cron :03 (9d05d19) / :57 (run #12).

### 2026-05-10 22:57 local — cadence 6 (+103 min)

Daemon pid 22272 alive cpu=2.06s. Gateway hot_rate 0.31 stable.

Status:
- 290 main attempting, 291 proved, **292 attempts=4** (was 3), 293/294 proved
- 6 dead_attempts: 2 agent_bailed, 2 agent_stuck_thinking, 2 lake_build_error
- 5 strategies, 2 live (s237/s241)
- Goal=292 retry pipeline 3d5aca24 just dispatched (attempt #5)

## Goal=292 second pipeline ran identical pattern

```
[dispatch] Backward Goal=292 pid=604be459 (retry pipeline)
[watchdog] sid=c2efb4b6 trap-but-not-silent silence=264s; defer
[llm:claude] timed out after 900s
[timeout-trap] sid=c2efb4b6 → fresh-sid takeover
[fresh-rescue stage2] sid=0af0b4e6 rc=124 dur=240s
[fresh-rescue stage3] sid=736f165c rc=0 dur=76s → agent_bailed
[cascade] Backward Goal=292 → failed
```

Same end state: stage 3 ships `agent_bailed`, drafts updated, retry dispatched. Each pipeline ~30 min before fail.

## Wall-clock breakdown so far on Goal=292

- Pipeline 1 (ada0b923): ~46 min, 4 trap takeovers
- Pipeline 2 (604be459): ~30 min, 1 watchdog defer + 1 TIMEOUT-trap takeover
- Pipeline 3 (3d5aca24): just started

Total: ~76 min on Goal=292 alone (out of 103 min run wall). Same goal in 9d05d19 (Goal=9): 3 cross-pipeline attempts, ~15 min total, **shipped**.

## Comparison @ 100min

| Metric | run #12 | 9d05d19 (~70min) |
|---|---|---|
| Wall | +103 min | +69 min |
| Proved | 4 | 13 |
| kelly_ordinary class | attempts=4, no proof | proved on 3rd cross-pipeline |
| Trap events | 8+ | 0 |

## attempts=4 / shelve_threshold=5

Goal=292 has 1 retry left before auto-shelve. Pipeline 3d5aca24 will likely also bail given the consistent pattern. Then attempts=5 → shelve → cascade-shelve up to Goal=290 main → SG run terminates as failed.

Estimated time to natural failure: ~30 min more (one more pipeline cycle).

No cut. Continue. Next cron :17 (run #12) / :23 (9d05d19).





