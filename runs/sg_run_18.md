# SG run #18 — full transport-fail story deployed

HEAD: `1db4e8c` (SelectorEventLoop真正生效 + circuit breaker on top of spawn-sandbox + dedupe + 三層 transport-fail 修補) + Asterism.yaml uncommitted (`backward.model = claude-opus-4-7`)
Started: 2026-05-11 02:59 local
Daemon pid: **100700**
Background task: `bhfy0ti50` (nohup wrapper, completed; daemon standalone)
Log file: `D:/Asterism/.asterism/logs/multi_claude-sonnet-4-6+claude-opus-4-7_20260511-025909.log`
Cron: `b773c979` :01/:21/:41

## Full fix stack deployed

| Commit | Fix |
|---|---|
| `10833bf` | verify_file retries transient gateway timeouts |
| `d2dd861` | worker exception → gateway_unreachable classifier (no goal.attempts++) |
| `42bb9af` | spawn-sandbox Phase 1 (foundation + sweep) |
| `8b5ec29` | spawn-sandbox Phase 2 (backward.py / builder.py migration) |
| `93850fb` | dedupe provability-via-apply (catches 323→329 hypothesis-extension) |
| `1db4e8c` | SelectorEventLoop actually takes effect + circuit breaker for permanent gateway death |

## Hypothesis (final round)

1. SelectorEventLoop policy truly active — gateway accept loop won't die from IOCP WinError 64
2. Even if transport fails transient, d2dd861 classifies + cooldown, doesn't burn goal attempts
3. Even if gateway permanently dies, circuit breaker exits after 8 consecutive gateway_unreachable
4. spawn-sandbox + dedupe continue working
5. Opus Backward breaks kelly-class deep cascade as before

## Cadence findings

### 2026-05-11 ~03:21 local — cadence 1 (+~22 min)

Daemon pid 100700 alive. Gateway hot_rate **0.72** (23 hot / 6 cold_warmup / 0 evicted / 3 noswap, sessions_active=2).

**🎯 1db4e8c SelectorEventLoop validation passed**

Gateway log latest entry: `[05/11/26 11:08:43] INFO Processing request of type CallToolRequest`. **NO new `WinError 64` / `IocpProactor.accept` errors** in current daemon's gateway. The old WinError 64 entries (02:31:32 from run #15, 07:36:26 from run #17) are all stale, from previous daemon starts.

Critically, the policy install moved to top of main() + `loop="asyncio"` passed to uvicorn.run() — this time the SelectorEventLoop is actually used.

Status:
- 3 goals: [371] main attempting / [372] exists_min_dist_triple / [373] min_dist_implies_ordinary_pair (depth 1)
- 3 strategies, 0 shelved, 0 dead_attempts
- Backward Goal=371 main → success (Opus shipped, 2 sub-goals produced)
- 2 Backward in flight (372 + 373)

**Decomposition shape**: existence + property (same as run #14 first cascade, wider than #15's "single sub").

**Sandbox**: 2 active dirs (one per in-flight spawn). Phase 2 protection active.

**Transport health**:
- 0 worker exception / WinError / gateway_unreachable in dispatcher log
- 0 `consec_gateway_unreachable` increments (gateway healthy)
- Gateway 33s startup (normal range)

**Cut analysis**: all green.

No cut. Continue. Next cron :41.

### 2026-05-11 ~03:41 local — cadence 2 (+~42 min)

Daemon pid 100700 alive. Gateway hot_rate **0.65** (68 hot / 30 cold_warmup / 1 evicted / 5 noswap, sessions_active=1).

**🎯🎯 Run #18 cleanest run yet — 4 proved at +42min, wider decomposition**

Status:
- 9 goals (+6 from cadence 1)
- **4 proved**: 372 exists_min_dist_triple, 375 exists_kelly_min_ratio, 376 kelly_cross_of_ratio (Builder), 378 exists_min_over_nondeg
- 5 strategies live (was 3); 0 shelved, 0 dead_attempts
- Max depth: 4 (Goal=379 kelly_geom_pick)

**Verify housekeeping chain** (3 strategies cascade-promoted):
```
[backward leaf-bypass] strategy=s362 → ready_for_verify
[verify] Strategy=362 → proved
[verify] Strategy=360 → proved
[verify] Strategy=358 → proved
```

**Tree**:
```
371 main attempting
├─ 372 exists_min_dist_triple ✓
└─ 373 min_dist_implies_ordinary_pair (attempting)
   ├─ 374 kelly_strict_decrease (attempting)
   │  └─ 377 kelly_witness (attempting)
   │     ├─ 378 exists_min_over_nondeg ✓
   │     └─ 379 kelly_geom_pick (depth 4, open, in flight)
   └─ 375 exists_kelly_min_ratio ✓
      └─ 376 kelly_cross_of_ratio ✓ (Builder Sonnet)
```

**Comparison vs prior runs at +42min**:
| Run | Goals | Proved | Max depth | Tree shape |
|---|---|---|---|---|
| #15 (no fixes) | 9 | 0 | 3 | narrow (1 sub/level) |
| #17 (sandbox + dedupe) | 7 | 0 | 5 | narrow + 1 BUG manifesting |
| **#18 (full stack)** | **9** | **4** | 4 | **wider (2 subs from main + 373)** |

Run #18 produces proved goals fastest of all post-LSP runs — wider decomposition lets Builder Sonnet close leaves before cascade goes too deep.

**Transport health — 2 brief release timeouts, no fallout**:
```
[gateway] release f8ded50d failed: timed out
[gateway] release 242b1f86 failed: timed out
```
Both handled gracefully by 10833bf retry pattern. NO worker exception, NO `gateway_unreachable` triggered, NO `consec_gateway_unreachable` increments. Gateway stays accept-loop healthy under SelectorEventLoop.

**Sandbox active**: 3 attempt dirs, 1 sandbox dir (2 already completed and self-cleaned).

**Cut analysis**: all green.

No cut. Continue. Next cron :01.

### 2026-05-11 ~04:01 local — cadence 3 (+~62 min)

Daemon pid 100700 alive. Gateway hot_rate **0.60** (85 hot / 43 cold_warmup / 1 evicted / 13 noswap, sessions_active=3).

Status:
- 14 goals (+5 from cadence 2)
- **5 proved**: 372, 375, 376, 378, **381 kelly_s_param** (NEW Builder Sonnet, depth 5)
- 9 strategies live, 0 shelved, 0 dead_attempts
- Max depth: **6** (Goals 382/383/384 — three t-range case sub-goals)

**New cascade extension**:
```
... 379 kelly_geom_pick (depth 4)
└─ 380 kelly_pick_from_param (depth 5)
   ├─ 381 kelly_s_param ✓ (Builder Sonnet)
   └─ (cascade produced 3 case sub-goals at depth 6)
      ├─ 382 kelly_pick_from_param_t_gt   (t > 1 case)
      ├─ 383 kelly_pick_from_param_t_mid  (t ∈ (0,1))
      └─ 384 kelly_pick_from_param_t_neg  (t < 0)
```

The three t_* case sub-goals are parameter-range case analysis on Kelly's construction. Same conclusion shape with different t-range hypothesis — candidate for dedupe inspection, but likely the witness construction differs per case so dedup should reject (and observed: no `[dedupe] aliased` log entry).

**Sandbox active**: 5 attempt dirs / 3 sandbox dirs (in-flight 3 Backwards, completed ones cleaned).

**Transport health — all green**:
- Cumulative 2 release timeouts (cadence 2, no new this cadence)
- 0 worker exception / WinError / gateway_unreachable
- 0 `consec_gateway_unreachable` increment
- 0 watchdog event

**Cross-run comparison at +60min**:
| Run | Goals | Proved | Max depth | Anomaly |
|---|---|---|---|---|
| #15 (no fixes) | ~9 | 3 | 3 | none yet |
| #17 (sandbox + dedupe) | 15 | 1 | 7 | runaway 48 strategies (cut +52min) |
| **#18 (full stack)** | **14** | **5** | **6** | **0** |

Run #18 = **5× proved vs #17, 0 anomaly, 9 strategies (healthy range)**. Full fix stack performing at SG-class workload.

**Cut analysis**: all green.

No cut. Continue. Next cron :21.

### 2026-05-11 ~04:21 local — cadence 4 (+~82 min) — circuit breaker fired, daemon exited

Daemon pid 100700 alive at cadence start; self-exited via circuit breaker during this 20-min window.

**🎯🎯🎯 1db4e8c circuit breaker fired as designed**

Log sequence:
```
[gateway] release a8739ba6 failed: <urlopen error [WinError 10061] ...>
[cascade] worker exception on Builder Goal=398: WinError 10061; gateway_unreachable (no attempts++)
[cooldown] Builder Goal=398 cooled 30s after gateway_unreachable (consec=1)
[cooldown] Builder Goal=396 cooled 30s after gateway_unreachable (consec=2)
[cooldown] Builder Goal=397 cooled 30s after gateway_unreachable (consec=3)
[cooldown] Builder Goal=394 cooled 30s after gateway_unreachable (consec=4)
[cooldown] Backward Goal=389 cooled 30s after gateway_unreachable (consec=5)
[cooldown] Backward Goal=385 cooled 30s after gateway_unreachable (consec=6)
[cooldown] Builder Goal=396 cooled 30s after gateway_unreachable (consec=7)
[cooldown] Builder Goal=397 cooled 30s after gateway_unreachable (consec=8)
[dispatcher] 8 consecutive gateway_unreachable — gateway appears 
permanently dead; exiting. Restart daemon (gateway will be 
re-launched) and inspect .asterism/logs/gateway.log for the 
underlying crash.
```

Compare to run #17: same gateway-crash scenario but daemon DIDN'T self-exit → 48-strategy runaway. Run #18 cleanly cut at 8 consecutive failures, no DB pollution.

## CUT REASON — 2026-05-11 ~04:22 local (+~83 min, daemon auto-exited at +~82min)

**Cut 動作**: CronDelete `b773c979` ✓、`taskkill /PID 100700 /F`（已經 exit 但 process 沒清完）✓、kill orphan python/lake/lean/claude ✓、`rm .asterism/daemon.pid` ✓

**Cut 動機**: Daemon已 auto-exit via circuit breaker (1db4e8c). Operator cleanup + investigate gateway death.

**Run #18 final snapshot (when daemon exited)**:
- **28 goals reached** (up from 14 at cadence 3)
- **6 proved**: 372, 375, 376, 378, 381 kelly_s_param, 388 t_gt_dichotomy
- Max depth 8 (cross_ineq_*, noncoll_*)
- 16 strategies live (healthy range, NOT runaway despite gateway death)
- 0 shelved
- attempts charged correctly (385/387/389/394/395 have attempts=1 from real timeouts; 396/397/398 have attempts=0 because gateway_unreachable correctly classified)

**Root cause of gateway death**:
- Gateway log line ~24305 onwards shows fresh WinError 64 at IocpProactor.accept at 12:02:24 — gateway IS still using ProactorEventLoop despite my 1db4e8c attempt to use SelectorEventLoop
- Investigation: uvicorn's internal `asyncio_setup()` on Windows explicitly calls `asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())`, OVERRIDING my install. `loop="asyncio"` just chooses between asyncio/uvloop families; it does NOT preserve my policy.
- **`1db4e8c` SelectorEventLoop install is being overridden by uvicorn itself.**

**Mixed verdict on 1db4e8c**:
- ✅ Circuit breaker: WORKS PERFECTLY — daemon cleanly exited after 8 consecutive gateway_unreachable. Run #17 runaway prevented.
- ❌ SelectorEventLoop: still ineffective. uvicorn's policy reset overrode my install.

**Next fix**: use `loop="none"` in uvicorn.Config, manage asyncio loop manually with WindowsSelectorEventLoop, so uvicorn's policy reset has nothing to overwrite.



