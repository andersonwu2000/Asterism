# SG run #17 — Opus Backward + Sonnet Builder + spawn-sandbox + dedupe

HEAD: `93850fb` (full stack: spawn-sandbox + dedupe provability-via-apply + three-layer transport-fail fix) + Asterism.yaml uncommitted (`backward.model = claude-opus-4-7`)
Started: 2026-05-10 22:48 local
Daemon pid: **72904**
Background task: `bu6io7la7` (nohup wrapper, completed; daemon standalone)
Log file: `D:/Asterism/.asterism/logs/multi_claude-sonnet-4-6+claude-opus-4-7_20260510-224858.log`
Cron: `20d3407a` :17/:37/:57

## Hypothesis

After run #15 + #16 + dedupe forensic, this is the first SG run with full stack:
- `42bb9af` + `8b5ec29` spawn-sandbox Phase 1+2 (goal_lean rollback on daemon crash)
- `93850fb` dedupe provability-via-apply (catches hypothesis-extension duplicates like 323/329/331)
- `475c318` + `10833bf` + `d2dd861` three-layer transport-fail fix

Test:
1. dedupe catches hypothesis-extension cases in real cascade
2. spawn-sandbox protects against daemon crash
3. transport layer remains stable
4. Opus Backward continues breaking kelly-class hard branch

## Architecture

| Aspect | Value |
|---|---|
| Backward model | claude-opus-4-7 |
| Builder model | claude-sonnet-4-6 |
| Cap | MAX_THINKING_TOKENS = 1K/min |
| Watchdog v4 | trap_check 660s + silence 300s (AND condition) |
| Verify retry | retry-with-backoff + transient/logic split |
| Gateway event loop | WindowsSelectorEventLoopPolicy |
| Worker exception classifier | gateway_unreachable identification |
| Spawn sandbox | Phase 1+2 (real-path snapshot guard) |
| Dedupe | provability-via-apply (alias-semantics-consistent) |
| Wall budget | 16200s = 4h30 |

## Cadence findings

### 2026-05-10 ~23:17 local — cadence 1 (+~20 min)

Daemon pid 72904 alive. Gateway hot_rate **0.69** (11 hot / 4 cold_warmup / 0 evicted / 1 noswap, sessions_active=1).

Status:
- 2 goals: [356] main attempting / [357] kelly_contrapositive (depth 1) open
- 2 strategies (s306, s307)
- Recent: Backward Goal=356 → success (Opus ship)
- Backward Goal=357 in flight (claude-opus-4-7, pid eb138c44)

**Decomposition shape** — narrow:
| Run | Main → sub-goals |
|---|---|
| #14 (Opus first cascade) | 2 subs |
| #15 (Opus first cascade) | 1 sub (`all_collinear_of_no_ordinary`) |
| **#17 (Opus first cascade)** | **1 sub (`kelly_contrapositive`)** |

Different framing this time (contrapositive route).

**spawn-sandbox working**:
- `.attempts/eb138c44.../sandbox/` present (Phase 2 active for in-flight spawn)
- Will be cleaned up automatically on spawn exit

**dedupe state**:
- No `_dedupe_check_*.lean` temp leak in `.attempts/` (finally-unlink works)
- No `[dedupe]` log entries yet (only main+sub-goal present, no dedupe opportunity)
- Will see action when cascade goes deeper with multiple sibling sub-goals

**Transport health — clean**:
- 0 worker exception / WinError / gateway_unreachable
- 0 watchdog event
- gateway ready in 30s (normal)

**Workspace**: clean.

**Cut analysis**: all OK.

No cut. Continue. Next cron :37.

### 2026-05-10 ~23:37 local — cadence 2 (+~40 min)

Daemon pid 72904 alive. Gateway hot_rate **0.53** (26 hot / 18 cold_warmup / 0 evicted / 5 noswap, sessions_active=2).

**🎯 Cascade through depth 5 — 5 consecutive Backward successes**

Status:
- 7 goals (+5 from cadence 1)
- 0 proved (cascade still going down, no Builder leaf complete yet)
- 6 strategies live, 0 shelved, 0 dead_attempts
- Max depth: 5

**Tree**:
```
356 main
└─ 357 kelly_contrapositive (depth 1, attempting)
   └─ 358 kelly_distinct_collinear (depth 2, attempting)
      └─ 359 kelly_no_non_collinear_triple (depth 3, attempting)
         ├─ 360 min_perp_triple_exists (depth 4, open) ← Kelly min existence
         └─ 361 min_perp_triple_no_descent (depth 4, attempting)
            └─ 362 descent_witness (depth 5, open) ← Kelly descent core
```

**Recent pipelines**: 5/5 success (356→357→358→359→361 all Backward chain).

**Active sandboxes** (2 in-flight spawns):
- `.attempts/1d8adc6b.../sandbox/` (Builder Goal=360 Sonnet)
- `.attempts/747c3e4d.../sandbox/` (Backward Goal=362 Opus)

Phase 2 sandbox active for both spawns — goal_lean snapshot recorded, will rollback or commit on exit.

**Clean state**:
- 0 `_dedupe_check_*.lean` temp leak ✓
- 0 stale sandbox dirs (only in-flight ones present) ✓
- 0 `[dedupe] aliased` log entries (no dedup opportunity yet — each cascade level has 1-2 fresh sub-goals)

**Transport health**:
- 0 worker exception / WinError / gateway_unreachable
- 0 watchdog event
- 0 framework anomaly throughout 40 min

**Comparison**:
| Metric | run #15 +40min | **run #17 +40min** |
|---|---|---|
| Goals | ~9 | **7** |
| Proved | 3 | 0 |
| Max depth | 3 | **5** |
| Trap | 0 | 0 |
| Framework anomaly | none | none |

Run #17 going deeper faster but no proved yet (narrow tree means longer wait for Builder leaves to close). All clean.

No cut. Continue. Next cron :57.

### 2026-05-10 ~23:57 local — cadence 3 (+~60 min)

Daemon pid 72904 alive. Gateway briefly overloaded (curl 30s timeout; eventually responded). Sessions_active high (~5 in-flight spawns).

**🔥 d2dd861 修補首次 production trigger validated**

Log evidence:
```
[gateway] release 3ad4b526 failed: timed out
[cascade] worker exception on Builder Goal=368: [WinError 10054] ...; gateway_unreachable (no attempts++)
[cooldown] Builder Goal=368 cooled 30s after gateway_unreachable
[cascade] worker exception on Builder Goal=369: [WinError 10054] ...; gateway_unreachable (no attempts++)
[cooldown] Builder Goal=369 cooled 30s after gateway_unreachable
[cascade] worker exception on Builder Goal=369: <urlopen error [WinError 10061] ...>; gateway_unreachable (no attempts++)
[cooldown] Builder Goal=369 cooled 30s after gateway_unreachable
[cascade] worker exception on Builder Goal=368: <urlopen error [WinError 10061] ...>; gateway_unreachable (no attempts++)
[cooldown] Builder Goal=368 cooled 30s after gateway_unreachable
```

Worker exception classifier correctly identifies WinError 10054 (connection reset by peer) and 10061 (refused) as `gateway_unreachable`. Attempts NOT incremented. 30s cooldown applied per d2dd861 design.

Without d2dd861, each of these would have charged 1 attempt against the goal — Goal=368 and 369 would have each hit `attempts=4` after these 4 transport failures, well on their way to shelve. With the fix, attempts stay 0.

Status:
- **15 goals** (+8 from cadence 2)
- **1 proved**: Goal=360 min_perp_triple_exists (Builder Sonnet, Kelly minimum existence)
- **Max depth: 7** (6× case_*_*_* + kelly_pigeonhole)
- 9 strategies (Goal=370 has 2 strategies = OR-parallel)
- 0 shelved, 0 dead_attempts visible

**Tree** (Kelly proof structure unfolding):
```
... 363 pure_descent (depth 6)
├── 364 case_a_c_b (depth 7, open, attempts=1 from timeout)
├── 365 case_a_c_r
├── 366 case_b_c_a
├── 367 case_b_c_r
├── 368 case_c_r_a   ← gateway_unreachable, cooldown active
├── 369 case_c_r_b   ← gateway_unreachable, cooldown active
└── 370 kelly_pigeonhole (depth 7, open, attempts=1, OR-parallel s313+s314)
```

The 6 `case_*_*_*` = Kelly's same-side argument's 6-way pigeonhole case analysis (which 2 of 3 collinear points sit on which side of perp foot).

**dedupe**:
- 0 `_dedupe_check_*.lean` temp leak ✓
- 0 `[dedupe] aliased` events in log — the 6 case statements have distinct witness binders, so dedup not catching them (likely legitimate case distinctions, not redundant variants)
- Active sandbox dirs (5, matching in-flight spawns): each is a Phase 2 snapshot guard

**Watchdog**: 2 spawn-timeout events (Goal=370 + 364) — Opus thinking hit spawn budget; charged 1 attempt each (proper timeout, not transport).

**Cut analysis**: all green. d2dd861 + sandbox + dedupe all working as designed.

No cut. Continue. Next cron :17.

## CUT REASON — 2026-05-11 ~07:40 local (+~52 min effective + cadence 4 detected anomaly)

**Cut 動作**: CronDelete `20d3407a` ✓、`taskkill /PID 72904 /F` ✓、kill orphan python/lake/lean ✓、`rm .asterism/daemon.pid` ✓

**Cut 動機**: TWO framework BUGs surfaced together:

**BUG 1: `475c318` SelectorEventLoop fix didn't actually take effect**
Gateway log shows fresh IOCP traceback at `05/11/26 07:36:26`:
```
OSError: [WinError 64] 指定的網路名稱無法使用。
  at windows_events.py:798 in _poll
  at windows_events.py:550 in finish_accept
```
This is Python's IocpProactor — meaning uvicorn is STILL using Proactor event loop despite my `_install_windows_event_loop_policy()`. uvicorn's default `loop="auto"` selects Proactor on Windows and IGNORES `asyncio.set_event_loop_policy()`. My fix was ineffective.

**BUG 2: No circuit breaker for permanent gateway death**
After gateway accept loop crashed at 07:36, every Backward dispatch instantly hit `WinError 10061` (connection refused). d2dd861's cooldown is per-(target,kind) 30s. Dispatcher kept re-dispatching → each created a new strategy row → 48 strategies on 15 goals in 20 min. d2dd861's `(no attempts++)` correctly prevents goal shelve, BUT the strategy creation isn't gated.

**Run #17 final snapshot**:
- 15 goals, 1 proved (Goal=360 min_perp_triple_exists), depth 7
- **48 strategies / 0 dead** — runaway creation on Goal=370 + Goal=364
- 0 shelved (d2dd861 prevented attempts++ correctly)
- Cascade reached Kelly six-case + pigeonhole layer before gateway died

**Both BUGs need fixing**:
1. uvicorn must use SelectorEventLoop properly (pass `loop="asyncio"` + global policy + verify via test)
2. Daemon needs a circuit breaker: if N consecutive `gateway_unreachable` fire across the whole daemon, halt dispatching + log fatal + exit (operator must restart)



