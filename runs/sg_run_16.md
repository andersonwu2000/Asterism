# SG run #16 — Opus Backward + Sonnet Builder + spawn_sandbox

HEAD: `8b5ec29` (spawn-sandbox Phase 1+2 deployed) + Asterism.yaml uncommitted (`backward.model = claude-opus-4-7`)
Started: 2026-05-10 22:28 local
Daemon pid: **100312**
Background task: `bzm08lss1` (nohup wrapper, completed; daemon standalone)
Log file: `D:/Asterism/.asterism/logs/multi_claude-sonnet-4-6+claude-opus-4-7_20260510-222753.log`
Cron: `0ef524e0` :11/:31/:51

## Hypothesis

After SG run #15 manual cut at +170min revealed s300 BUG (operator-killed daemon left goal_lean broken with theorem name corruption), three commits landed:
- `42bb9af` spawn-sandbox Phase 1: SpawnWorkspace + sweep + tests
- `8b5ec29` spawn-sandbox Phase 2: backward.py + builder.py migration

Test:
1. spawn-sandbox prevents goal_lean state leak even on daemon crash (sweep restores from manifest snapshot at next daemon startup)
2. Three transport-fail fixes (475c318 + 10833bf + d2dd861) continue working
3. Opus Backward continues to break kelly-class hard branch

## Architecture

| Aspect | Value |
|---|---|
| Backward model | claude-opus-4-7 |
| Builder model | claude-sonnet-4-6 |
| Cap | MAX_THINKING_TOKENS = 1K/min |
| Watchdog | v4 (trap_check 660s + silence 300s, AND condition) |
| Verify | retry-with-backoff + transient/logic split |
| Gateway event loop | WindowsSelectorEventLoopPolicy |
| Worker exception classifier | gateway_unreachable identification |
| **Spawn sandbox** | **Phase 2 (backward.py + builder.py wrap goal_lean snapshot/restore)** |
| Wall budget | 16200s = 4h30 |

## Cadence findings

### 2026-05-10 ~22:39 local — cadence 1 (+~11 min)

Daemon pid 100312 alive. Gateway hot_rate **0.80** (8 hot / 1 cold_warmup / 0 evicted / 1 noswap, sessions_active=1).

**🟢 spawn_sandbox observed working in production**

`.attempts/454ab3c4.../sandbox/_manifest.json` shows:
- owner_pid 100312 (matches daemon)
- committed=false (in-flight)
- real_paths includes `Root.lean` with sha_before recorded

Sandbox snapshotted goal_lean (Root.lean, depth-0 main) on Backward enter. If daemon crashed mid-spawn, next startup sweep would restore.

Status:
- 1 goal: [354] main open attempts=0
- 1 strategy: s304 (Backward Opus Goal=354 in flight)
- Backward already produced `patch.lean` + `new_kelly_contradiction.lean` in attempts_dir (partial decomposition)

**Gateway startup**: `[gateway] ready after 58s` — slower than typical ~30s. Possibly SelectorEventLoop slower than ProactorEventLoop on cold worker init, but acceptable. Watch if subsequent restarts repro.

**No `[sandbox-sweep] startup` message** — correct, fresh start with no orphan sandboxes to recover.

**No transport anomaly** — 0 worker exceptions / WinErrors / gateway_unreachable.

**Workspace**: clean (BRIEF / Defs / LESSONS / Manifest / Root / TREE).

**Cut analysis**: all green.
- ❌ No daemon suicide (alive)
- ❌ No parent_stub_not_decomposable (Phase 2 working)
- ❌ No sandbox/ leak (only in-flight spawn has one)
- ❌ Gateway hot_rate 0.80 healthy
- ❌ shelved% = 0
- → No cut, continue

No cut. Continue. Next cron :31.

## CUT REASON — 2026-05-10 ~22:42 local (+~14 min)

**Cut 動作**: CronDelete `0ef524e0` ✓、`taskkill /PID 100312 /F` ✓、kill orphan python/lake/lean/claude ✓、`rm .asterism/daemon.pid` ✓

**Cut 動機**: 主動 cut 去做 dedupe 升級（hypothesis-extension equivalence）。Run #15 暴露 323/324/329/331 重複問題未解、會影響後續 cascade 效率。run #16 才剛起 Backward main、損失 ~14 min wall。修補後重啟為 run #17。

**Run #16 final snapshot**:
- 1 goal (354 main, attempts=0, no cascade yet)
- 1 strategy (s304 Backward in flight when cut)
- spawn-sandbox observed working: `.attempts/454ab3c4.../sandbox/_manifest.json` correctly snapshotted Root.lean + recorded SHA + owner_pid + committed=false
- 0 transport anomaly (gateway hot_rate 0.80, no WinError)
- Confirmed Phase 1+2 sandbox active in production — sandbox dir created on enter, sweep would fire on next startup if daemon crashed

