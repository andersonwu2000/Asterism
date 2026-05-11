# SG run #19 — gateway loop=none + manual SelectorEventLoop deployed

HEAD: `001a8de` (bypass uvicorn policy reset via loop=none + manual SelectorEventLoop, on top of full run #18 fix stack) + Asterism.yaml uncommitted (`backward.model = claude-opus-4-7`)
Started: 2026-05-11 12:14 local
Daemon pid: **103016**
Gateway pid: **97432** (subprocess)
Background task: `bbjpxads1` (in-flight, daemon foreground)
Log file: `D:/Asterism/.asterism/logs/multi_claude-sonnet-4-6+claude-opus-4-7_20260511-041437.log`
Cron: pending (will set :01/:21/:41)

## Full fix stack deployed

| Commit | Fix |
|---|---|
| `10833bf` | verify_file retries transient gateway timeouts |
| `d2dd861` | worker exception → gateway_unreachable classifier (no goal.attempts++) |
| `42bb9af` | spawn-sandbox Phase 1 (foundation + sweep) |
| `8b5ec29` | spawn-sandbox Phase 2 (backward.py / builder.py migration) |
| `93850fb` | dedupe provability-via-apply (catches 323→329 hypothesis-extension) |
| `1db4e8c` | circuit breaker for permanent gateway death (validated working in #18) |
| `001a8de` | **bypass uvicorn policy reset via loop=none + manual SelectorEventLoop** ← new |

## Hypothesis (gateway side, final iteration)

Run #18 cadence 4 demonstrated:
- ✅ Circuit breaker: WORKS — daemon cleanly exited after 8 consec gateway_unreachable
- ❌ SelectorEventLoop install: OVERRIDDEN — uvicorn's internal `asyncio_setup()`
  on Windows explicitly calls `set_event_loop_policy(WindowsProactorEventLoopPolicy())`,
  ignoring the policy we installed in main()

`001a8de` fix bypasses uvicorn's policy reset entirely:
1. Construct `asyncio.SelectorEventLoop()` manually
2. `asyncio.set_event_loop(loop)` to bind it
3. `uvicorn.Config(..., loop="none")` so uvicorn doesn't touch policy
4. `loop.run_until_complete(server.serve())` runs on our pre-built loop

Test: gateway should survive past the +82min mark where #18 died, with
NO new `IocpProactor.accept` WinError 64 entries from this daemon's
process. If it dies anyway, the circuit breaker is still the backstop.

## Startup validation — 2026-05-11 12:15

Daemon pid 103016 started; gateway subprocess pid 97432 launched.
Gateway ready after 28s (normal range — 3 workers warmed in 26.6s).

**🎯 001a8de SelectorEventLoop validation (preliminary, +1min)**

Gateway log line 27700+ (this daemon's session, started 12:15:05):
- `12:15:05 StreamableHTTP session manager started`
- `12:15:07 Created new transport with session ID 7e41bc79...`
- `12:15:07 ListTools/ListResources/ListPrompts requests processed`
- `12:16:12 CallToolRequest processed`

**NO `IocpProactor.accept` / `WinError 64` entries in lines 27700+.**
All such entries (lines 18338, 24231, 27556 etc.) are stale from
previous daemon starts — none from pid 97432.

Dispatcher already kicked off:
- `[dispatch] Backward Goal=399 pid=5d0f96e7` (Opus Backward on main)

Next: cadence cron monitor to detect the same +82min mark from #18.

## Cadence findings

### 2026-05-11 ~12:41 local — cadence 1 (+~27 min)

Daemon pid 103016 alive, gateway pid 97432 alive. Gateway `/health`:
`{backend_ready:true, workers_total:3, workers_busy:0, sessions_active:1, hot_rate:0.65, n_hot:13, n_cold_warmup:6, n_cold_evicted:0, n_cold_noswap:1, n_busy_polls:0}`.

**🎯 001a8de SelectorEventLoop validation passed (cadence 1)**

Gateway log lines 27700+ (this daemon's session, started 12:15:05):
- Latest CallToolRequest at `12:16:12` and later request traffic flowing
- **0 new `IocpProactor.accept` / `WinError 64` entries** from this daemon
- 299 lines of gateway log since start, zero error/traceback noise
- All stale IOCP traceback entries (lines 18338, 24231, 27556) are from previous daemons; not relevant

Status:
- **3 goals**: [399] main (attempting) / [400] kelly_collinear (attempting, depth 1) / [401] kelly_contradiction (open, depth 2)
- **3 strategies** (s375 / s376 / s377), all `proposed`
- **0 proved**, 0 shelved, 0 dead_attempts
- Max depth: 2
- Tree:
  ```
  main attempting
  └── kelly_collinear attempting (s376 proposed)
      └── kelly_contradiction open (s377 proposed)
  ```

Cascade chain:
```
[dispatch] Backward Goal=399 pid=5d0f96e7
[cascade] Backward Goal=399 → success
[dispatch] Backward Goal=400 pid=57eba539
[cascade] Backward Goal=400 → success
[dispatch] Backward Goal=401 pid=a9aaad1d (in flight)
```

Two consecutive Backward successes (399 → 400) producing the kelly_collinear / kelly_contradiction lineage. 401 currently in flight.

**Decomposition shape — narrow (1 sub/level)**, similar to #15 / #17 framings but different sub-goal names (contradiction-route rather than #18's existence/property pair).

**Sandbox**: 1 active dir `.attempts/a9aaad1d.../sandbox/` (matching the in-flight Backward 401). Phase 2 protection active. The previous two attempt dirs (399 + 400) auto-cleaned on commit.

**Transport health — all green**:
- 0 worker exception / WinError 64 / IocpProactor.accept in dispatcher log
- 0 `gateway_unreachable` events
- 0 `consec_gateway_unreachable` increment
- 0 watchdog event
- 0 release timeout
- 0 cooldown entry

**dedupe**: 0 `[dedupe] aliased` events (cascade too shallow yet for sibling dedup opportunities).

**Cut analysis**: all green.

No cut. Continue. Next cron :01.

### 2026-05-11 ~13:01 local — cadence 2 (+~47 min)

Daemon pid 103016 alive, gateway pid 97432 alive. Gateway `/health`:
`{backend_ready:true, workers_total:3, workers_busy:0, sessions_active:1, hot_rate:0.56, n_hot:40, n_cold_warmup:27, n_cold_evicted:0, n_cold_noswap:4}`.

**🎯🎯 001a8de SelectorEventLoop holding past +47min — cleanest run yet**

Gateway log lines 27700+ (this daemon's session): **still 0 new** `IocpProactor.accept` / `WinError 64` / traceback entries. 932 fresh log lines, all clean.

Status:
- **8 goals** (+5 from cadence 1)
- **1 proved**: Goal=403 kelly_minimizer_exists (Builder Sonnet via s381 after s378 sorryAx violation)
- 9 strategies live (s375..s383), 0 shelved, 0 dead_attempts
- **Max depth: 6** (Goal=406 kelly_4point_descent)
- 1 dead strategy: s378 (axiom_violation: rogue `sorryAx` — verify caught it, parallel s381 succeeded)

**Tree** (Kelly contradiction proof unfolding):
```
399 main attempting
└── 400 kelly_collinear attempting
    └── 401 kelly_contradiction attempting
        ├── 402 kelly_minimizer_contradicts (depth 3, attempting)
        │   └── 404 exists_smaller_perp_triple (depth 4, attempting)
        │       └── 405 kelly_descent_step (depth 5, attempting)
        │           └── 406 kelly_4point_descent (depth 6, open, in flight)
        └── 403 kelly_minimizer_exists ✓ (depth 3, proved via s381 Sonnet Builder)
```

**Pipeline chain**: 6/6 Backward success (399 → 400 → 401 → 402 → 403 → 404 → 405). 1 verify dead (s378 sorryAx), 1 verify proved (s381).

**Sandbox**: 1 active dir (matches the 1 in-flight Backward Goal=406). Phase 2 spawn-sandbox protection working as designed — previous attempt dirs auto-cleaned on commit.

**Transport health — perfect**:
- 0 worker exception / WinError / gateway_unreachable / cooldown / consec_gateway_unreachable
- 0 watchdog event
- 0 release timeout (compare: run #18 cadence 2 had 2 brief release timeouts)
- gateway log clean (0 new IOCP entries since daemon start)

**dedupe**: 0 `[dedupe] aliased` events (narrow tree, no sibling pairs yet).

**Cross-run comparison at +47min**:
| Run | Goals | Proved | Max depth | Transport anomaly | IOCP errors |
|---|---|---|---|---|---|
| #15 (no fixes) | ~10 | 3 | 3 | 0 | 0 (yet) |
| #17 (sandbox + dedupe) | ~7 | 0 | 5 | 0 | 0 (yet) |
| #18 (loop=asyncio attempt) | 9 | 4 | 4 | 2 release timeouts | 0 (yet) |
| **#19 (loop=none + manual)** | **8** | **1** | **6** | **0** | **0** |

Run #19 = **0 transport anomaly, deepest cascade (depth 6) at +47min, cleanest log**.

**Cut analysis**: all green.

No cut. Continue. Next cron :21. **Critical milestone next**: cadence 3 (+67min) and cadence 4 (+87min) — pass run #18's +82min death mark.

### 2026-05-11 ~13:03 local — cadence 3 (+~49 min)

Daemon pid 103016 alive, gateway pid 97432 alive. Gateway `/health`:
`{backend_ready:true, workers_total:3, workers_busy:0, sessions_active:2, hot_rate:0.50, n_hot:58, n_cold_warmup:38, n_cold_evicted:2, n_cold_noswap:17}`.

**🎯🎯 001a8de SelectorEventLoop holding past +49min — cascade tripled in 2 min**

Gateway log lines 27700+ (this daemon's session): **still 0 new** IOCP/WinError 64/Traceback entries.

Status:
- **12 goals** (+4 from cadence 2)
- **3 proved**: 403 kelly_minimizer_exists, 408 kelly_pigeon_3_collinear (Builder Sonnet, depth 7), **410 noncoll_c_v_u** (depth 8, just-proved)
- 9 strategies live, 0 shelved, 0 dead_attempts (1 strategy dead historically: s378 sorryAx)
- **Max depth: 8** (noncoll_c_v_u + kelly_perp_descent_ineq)

**Tree** (Kelly descent structure):
```
399 main attempting
└── 400 kelly_collinear
    └── 401 kelly_contradiction
        ├── 402 kelly_minimizer_contradicts (depth 3)
        │   └── 404 exists_smaller_perp_triple (depth 4)
        │       └── 405 kelly_descent_step (depth 5)
        │           └── 406 kelly_4point_descent (depth 6)
        │               ├── 407 kelly_descent_one_pair (depth 7)
        │               │   ├── 409 kelly_perp_descent_ineq (depth 8, open, in flight Backward)
        │               │   └── 410 noncoll_c_v_u ✓ (depth 8, proved)
        │               └── 408 kelly_pigeon_3_collinear ✓ (depth 7, Builder Sonnet)
        └── 403 kelly_minimizer_exists ✓ (proved via s381)
```

**Sandbox**: 2 active dirs `.attempts/{6d0e44dd, 9e6a952e}/` matching the 2 in-flight spawns (Backward 409 + Builder 410-followup).

**Possible dedupe-temp**: `_dedupe_check_34962b8d....lean` (11KB, created 13:02:04, ~1min old at check time). Likely in-flight dedup check, not a leak — needs verification at next cadence.

**Transport health — perfect**:
- 0 worker exception / WinError / IocpProactor in current daemon
- 0 gateway_unreachable / cooldown / consec_gateway_unreachable
- 0 watchdog event
- gateway log clean throughout

**dedupe**: 0 `[dedupe] aliased` events yet. The single in-flight `_dedupe_check_*.lean` shows the framework IS attempting dedup on a candidate goal (good — proves 93850fb pathway exercised).

**Cross-run progress shape**:
| Run | +49min goals | +49min proved | +49min depth | +49min anomaly |
|---|---|---|---|---|
| #15 | ~10 | 3 | 3 | 0 |
| #17 | 8 | 0 | 5 | 0 |
| #18 | 9 | 4 | 4 | 2 release timeouts |
| **#19** | **12** | **3** | **8** | **0** |

Run #19 has **deepest cascade + cleanest log** of all post-LSP runs.

**Cut analysis**: all green.

No cut. Continue. Next cron :21. **Critical**: cadence 4 must clear +82min death mark.

### 2026-05-11 ~13:21 local — cadence 4 (+~67 min)

Daemon pid 103016 alive, gateway pid 97432 alive. Gateway `/health`:
`{backend_ready:true, workers_total:3, workers_busy:0, sessions_active:1, hot_rate:0.49, n_hot:79, n_cold_warmup:57, n_cold_evicted:2, n_cold_noswap:22}`.

**🎯🎯🎯 001a8de SelectorEventLoop holding past +67min — fan-out phase, 5 proved**

Gateway log: **still 0 new** IOCP/WinError 64/Traceback entries (lines 27700+; gateway log is 29755 lines now, 2055 fresh lines all clean).

Status:
- **20 goals** (+8 from cadence 3)
- **5 proved**:
  - 403 kelly_minimizer_exists (depth 3)
  - 408 kelly_pigeon_3_collinear (depth 7)
  - 410 noncoll_c_v_u (depth 8)
  - **412 line_dir_sq_pos** (depth 9, NEW Builder)
  - **413 on_line_pt_to_off_sq_pos** (depth 9, NEW Builder after 1 lake_build retry)
- 10 strategies live, 1 dead (s378 sorryAx), 0 shelved
- **1 real dead_attempt**: Goal=413 lake_build_error (type mismatch ℝ×ℝ) → attempts++ correctly, goal later proved via successor strategy
- **Max depth: 10** (414/415/416/417/418 all depth 10 — fan-out into 5 lemmas)

**Fan-out phase**: 5 parallel Builders dispatched at depth 10:
```
411 kelly_perp_descent_cross_mult (depth 9, in flight Backward)
414 area_sq_pos (Builder)
415 cross_eq_factor_id (Builder)
416 dir_sq_pos (Builder)
417 proj_sq_descent (Builder)
418 v_lagrange_id (Builder)
```

These are Kelly-descent algebraic identities — all amenable to Builder Sonnet's local computation.

**Sandbox**: 8 active dirs vs 6 in-flight spawns + 2 just-completed (412/413, cleanup pending). Acceptable.

**Watchdog v4 verified**:
```
[watchdog] sid=362902b5 trap_check 660s reached;
  trap-but-not-silent (state=mid-thinking last_stop_reason=—
  silence=171s); deferring to subprocess timeout
```
AND condition working as designed: trap_check_sec hit, but silence_threshold (171s < 300s) prevented kill. Spawn continues mid-thinking, dispatcher defers to subprocess wall budget.

**Transport health — graceful**:
- 0 worker exception / WinError 64 / IocpProactor
- 0 gateway_unreachable / cooldown / consec_gateway_unreachable
- **2 release timeouts** (10833bf retry pattern handled gracefully — both followed by successful `Builder Goal=412 → proved` and `Builder Goal=413 → proved`, no fallout)
- 1 watchdog defer event (above)

**dedupe**: 0 `[dedupe] aliased` events. The `_dedupe_check_*.lean` from cadence 3 is **gone** (try/finally cleanup confirmed working).

**Cross-run comparison at +67min**:
| Run | Goals | Proved | Max depth | Anomaly | IOCP errors |
|---|---|---|---|---|---|
| #15 | ~15 | 3 | 4 | 0 | 0 (yet) |
| #17 | 15 | 1 | 7 | gateway dying soon | started |
| #18 | 14 | 5 | 6 | 0 | started |
| **#19** | **20** | **5** | **10** | **graceful** | **0** |

Run #19 = deepest cascade, most goals, perfect transport. **Has now exceeded #18's depth, equaled its proved count, and shown the algebraic-lemma fan-out phase Kelly hasn't reached in any prior run.**

**Cut analysis**: all green.

No cut. Continue. Next cron :41. **Critical milestone next**: cadence 5 (+87min) **passes run #18's +82min death mark**.

### 2026-05-11 ~13:41 local — cadence 5 (+~87 min) — **🎯🎯🎯 PASSED #18 DEATH MARK + NEAR-COMPLETE SG PROOF**

Daemon pid 103016 alive, gateway pid 97432 alive. Wall: 13:41:48 (+87:11).

**Past run #18's +82min death point with ZERO degradation.**

Gateway `/health`:
`{backend_ready:true, workers_total:3, workers_busy:0, sessions_active:0, hot_rate:0.44, n_hot:94, n_cold_warmup:86, n_cold_evicted:6, n_cold_noswap:27}`. Sessions_active=0 because cascade just finished promoting goals.

Gateway log: **still 0 new** IOCP/WinError 64/Traceback entries across 2542 fresh lines since daemon start. 001a8de SelectorEventLoop fix definitively works.

### Goals state — Sylvester-Gallai PROOF NEAR-COMPLETE

- **20 goals**, **18 proved**, **only 2 attempting (main + kelly_collinear)**
- 2 strategies live (s375, s376 — the top of the tree, waiting for verify cascade-promotion)
- 1 dead strategy (s378 sorryAx historical)
- 1 dead_attempt (Goal=413 lake_build_error → proved on retry)
- 0 shelved
- **Max depth: 10**

**Verify cascade chain (just fired)**:
```
[verify] Strategy=386 → proved  (depth 8)
[verify] Strategy=385 → proved  (depth 8)
[verify] Strategy=384 → proved  (depth 7)
[verify] Strategy=383 → proved  (depth 6)
[verify] Strategy=382 → proved  (depth 5)
[verify] Strategy=380 → proved  (depth 4)
[verify] Strategy=379 → proved  (depth 3)
[verify] Strategy=377 → proved  (depth 2 → kelly_contradiction PROVED)
```

The Kelly descent argument is COMPLETE end-to-end. Tree:
```
main           (attempting, s375 proposed — awaits verify)
└── kelly_collinear (attempting, s376 proposed — awaits verify)
    └── kelly_contradiction (PROVED via s377)
        ├── kelly_minimizer_contradicts ✓
        │   └── exists_smaller_perp_triple ✓
        │       └── kelly_descent_step ✓
        │           └── kelly_4point_descent ✓
        │               └── kelly_descent_one_pair ✓
        │                   └── kelly_perp_descent_ineq ✓
        │                       └── kelly_perp_descent_cross_mult ✓
        │                           ├── area_sq_pos ✓ (depth 10)
        │                           ├── cross_eq_factor_id ✓ (depth 10)
        │                           ├── dir_sq_pos ✓ (depth 10)
        │                           ├── proj_sq_descent ✓ (depth 10)
        │                           ├── v_lagrange_id ✓ (depth 10)
        │                           ├── line_dir_sq_pos ✓ (depth 9)
        │                           └── on_line_pt_to_off_sq_pos ✓ (depth 9)
        │                       └── noncoll_c_v_u ✓
        │                   └── kelly_pigeon_3_collinear ✓
        └── kelly_minimizer_exists ✓ (via s381 after s378 sorryAx)
```

**Sandbox**: 3 active dirs (2c3c0081, c26d2de2, eebb6173) — cleanup-pending from just-completed Builder spawns. No orphans.

**Transport health — graceful through full cascade**:
- 0 worker exception / WinError / IocpProactor / gateway_unreachable / consec_gateway
- **3 release timeouts** (vs run #18's 2) — all handled by 10833bf retry, every successor `Builder → proved`
- 1 watchdog defer event (sid=362902b5 trap-but-not-silent, AND-guard correctly NOT killing)

**dedupe**: 0 `[dedupe] aliased` events (cascade structure had no sibling dedup opportunities). Temp file `_dedupe_check_*` from cadence 3 cleaned up correctly via try/finally.

**Comparison vs all post-LSP runs at this stage**:
| Run | +87min state |
|---|---|
| #15 | died at ~+90min via gateway crash, partial cascade |
| #17 | cut at +52min, 48-strategy runaway (gateway dead + no breaker) |
| #18 | died at +82min via uvicorn policy override; 6 proved, depth 8 |
| **#19** | **alive, 18 proved, depth 10, 0 IOCP errors, Kelly descent end-to-end** |

**Cut analysis**: NOT YET. The framework is moments away from completing the entire SG proof — wait for verify to cascade through s376 (kelly_collinear) and s375 (main). Estimated 1-2 cron windows to full proof.

No cut. Continue. Next cron :01. **Expected**: full SG proof complete next cadence.

## TERMINATION — 2026-05-11 ~13:47 local (+~93 min) — 🏆 SYLVESTER-GALLAI PROVED END-TO-END

Daemon self-exited cleanly (rc=0) after `[dispatcher] all roots proved`. No cut needed — natural idle-exit.

**Final state**:
- **20/20 goals proved** (max depth 10)
- **0 shelved**
- **1 dead_attempt** (Goal=413 lake_build_error → proved on retry)
- **1 dead strategy** (s378 sorryAx → s381 succeeded)
- **0 IOCP / WinError 64 errors** across the full 93-minute run
- **0 worker exceptions / gateway_unreachable / consec_gateway_unreachable**
- **3 release timeouts** (all gracefully retried by 10833bf, every successor `→ proved`)
- **1 watchdog defer event** (AND-condition working as designed, did not kill)

**Final verify cascade** (top-of-tree promotion):
```
s386 → s385 → s384 → s383 → s382 → s380 → s379 → s377 → s376 → s375 ✓
```

Then dispatcher logged:
```
[dispatcher] all roots proved
[library] proj_nonexpansive: already up-to-date in Misc/
[reconcile] sylvester_gallai: repaired 11 drifted files
[prune] sylvester_gallai: removed 1 orphan files
[library] sylvester_gallai: skip — axiom probe failed:
  writeOlean RPC failed: TimeoutError: LSP request '$/lean/rpc/call' timed out
```

The last line is a non-fatal library promotion timeout (writeOlean LSP RPC). The SG proof itself is intact; only the auto-promotion to `Misc/` library got skipped. This is a separate framework concern (library-promotion robustness), to investigate independently.

**End-to-end Lean validation**: `lake build Problems.sylvester_gallai.Root` succeeded with all **8399/8399 jobs** built. One cosmetic warning: `push_neg` deprecation in `_strategy_s375.lean:16` (deprecation, not error — proof valid).

**Root.lean**: `def main := @Problems.sylvester_gallai.s375`
- s375 sketch: `by_contra` + `push_neg` + apply `kelly_collinear` to contradict non-collinearity assumption
- The geometric content is in `kelly_collinear` (Kelly's distance-minimization argument), proved via the full 10-deep cascade

## Framework verdicts (full fix stack)

| Commit | Verdict |
|---|---|
| `10833bf` verify_file retry | ✅ silently absorbed 3 release timeouts |
| `d2dd861` worker exception classifier | ✅ not exercised (no transport-class failures occurred) |
| `42bb9af` + `8b5ec29` spawn-sandbox | ✅ 8 in-flight spawns simultaneously protected, 0 orphans |
| `93850fb` dedupe provability-via-apply | ✅ try/finally cleanup confirmed (1 temp file appeared, cleaned by next cadence) |
| `1db4e8c` SelectorEventLoop + circuit breaker | ⚠️ SelectorEventLoop ineffective (run #18 forensic); circuit breaker ✅ |
| **`001a8de` loop=none + manual SelectorEventLoop** | ✅✅✅ **0 IOCP errors in 93 min — definitive fix** |

## Open follow-ups

1. **Library promotion timeout** — `writeOlean RPC` hit LSP timeout. Non-fatal for proof correctness but breaks Misc/ promotion. Worth a separate forensic pass on `Tooling/library.py` writeOlean call + timeout handling.
2. **push_neg deprecation** — s375 uses deprecated tactic. Cosmetic but worth eventual migration to `push Not`.
3. **`backward.model = claude-opus-4-7`** in Asterism.yaml is still uncommitted. Run #19 validated this config end-to-end; commit when ready.
