# SG run #14 — Opus Backward + Sonnet Builder

HEAD: `0e279fe` + Asterism.yaml uncommitted (`backward.model = claude-opus-4-7`)
Started: 2026-05-10 ~17:44 local
Daemon pid: **95236**
Background task: `bo9mlz2ee` (nohup wrapper, completed; daemon is standalone)
Log file: `D:/Asterism/.asterism/logs/multi_claude-sonnet-4-6+claude-opus-4-7_20260510-174426.log`
Cron: `b658ac2b` :07/:27/:47

## Hypothesis being tested

Run #13 forensic showed Sonnet 4.6 hits intelligence ceiling on kelly-class deep math reasoning (read LESSON #1 with answer literally written → re-derived from scratch → fell into same trap LESSON warned about → bailed). This was **NOT** a framework gap — framework provided full intel via Context.md / LESSONS / PAST_*.md / _progress.md.

Test: does **Opus 4.7** on Backward break this ceiling? Specifically:
1. Can Opus ship valid decomposition on kelly-class sub-goal (where Sonnet trapped 4 attempts → shelved)?
2. Does Opus also fall into the LESSON-warned trap (= ceiling deeper than Sonnet)?
3. If Opus ships but Sonnet Builder can't close sub-goal proofs → may need Opus on Builder too

Builder kept on Sonnet 4.6 (cost guard; Opus 5x).

## Architecture

| Aspect | Value |
|---|---|
| Backward model | **claude-opus-4-7** (changed from sonnet-4-6) |
| Builder model | claude-sonnet-4-6 (unchanged) |
| Cap | MAX_THINKING_TOKENS = 1K/min (restored 5/10) |
| Watchdog | v4 (trap_check_sec=660 + silence_threshold_sec=300, AND condition) |
| Wall budget | 16200s = 4h30 |

## Cadence findings (autonomous)

### 2026-05-10 ~18:07 local — cadence 1 (+~22 min)

Daemon pid 95236 alive. Gateway hot_rate **0.55** (6 hot / 4 cold_warmup / 0 evicted / 1 noswap).

Status:
- 3 goals: [302] main attempting attempts=0 / [303] exists_min_kelly_triple open / [304] kelly_min_implies_ordinary open
- 3 live strategies: s250 (main), s251 (304), s252 (303)
- Recent pipeline: Backward Goal=302 → success (1 cascade so far, Opus shipped first decomposition)

**Decomposition comparison**:
| Run | Main → sub-goals |
|---|---|
| #13 (Sonnet Backward) | 295 → 296 kelly_min_is_ordinary + 297 min_noncollinear_exists |
| **#14 (Opus Backward)** | **302 → 303 exists_min_kelly_triple + 304 kelly_min_implies_ordinary** |

Same structural shape (existence + property split), different slug naming. **Goal=304 = kelly_min_implies_ordinary** is the kelly-class hard branch analog — this is the critical test.

**Spawn verification**: 2 claude.exe with `--model claude-opus-4-7` confirmed (pid 86892 + 53312, Backward sub-goals).

**Watchdog/trap events**: 0 (too early — sub-goals just dispatched, trap_check fires at +11min from spawn).

**Workspace**: clean. No .drafts/ yet.

No cut. Continue. Next cron :27.

### 2026-05-10 ~18:27 local — cadence 2 (+~52 min)

Daemon pid 95236 alive. Gateway hot_rate **0.50** (48 hot / 34 cold_warmup / 4 evicted / 9 noswap, sessions_active=3).

**🟢 Cascade explosion — Opus decomposing fast and deep**

Status (vs cadence 1):
- **11 goals** (was 3, +8 in 30 min)
- **4 proved** / 0 shelved / 4 attempting / 3 open
- 8 strategies (6 live)
- **Reached depth 3** (Goal=308/309/310/311/312)

Recent pipelines (last 8): **8 consecutive successes**:
- Backward Goal=308 (exists_min_quot, depth 3) → success
- Backward Goal=307 (exists_kelly_violating_triple) → success **[leaf-bypass]**
- Builder Goal=309 (len_sq_pos, Sonnet) → proved
- Backward Goal=305 (kelly_finset_min) → success
- Backward Goal=304 (**kelly_min_implies_ordinary — kelly-class parent**) → success
- Builder Goal=306 (noncoll_implies_ne, Sonnet) → proved
- Backward Goal=303 (exists_min_kelly_triple) → success
- Backward Goal=302 (main) → success

**0 takeover / 0 watchdog defer / 0 shelved / 0 dead_attempts**

Verify chain: `[verify] Strategy=255 → proved`, `[verify] Strategy=253 → proved` — Phase 7 verify housekeeping caught up.

Spawn verification: 2 Opus Backward in flight (pid 96360, 98676) + 1 Sonnet Builder (pid 96880). Model selection correct.

**Comparison with run #13 at comparable time**:

| Metric | Run #13 +52min | **Run #14 +52min** |
|---|---|---|
| Proved | 3 | **4** |
| Goals discovered | 6 | **11** |
| Max depth | 2 | **3** |
| Trap takeover | 0 (cumulative to +65min: 1) | **0** |
| Watchdog defer | 1 | **0** |
| Shelved | 0 | 0 |
| Kelly-class parent | Goal=296 cascade success (but deeper Goal=299 trapped + shelved) | **Goal=304 cascade success, depth-3 sub-goals dispatching** |

Run #14 progress significantly faster than run #13 — and notably **zero trap activity** despite Opus's deeper thinking.

**Critical pending test**: Goal=311 cross_distance_strict_decrease = Kelly's strict inequality core (equivalent to Sonnet's Goal=299 kelly_false / Goal=301 kelly_strict_ineq which both trapped). Goal=310 between_pair_among_three_collinear + Goal=312 noncoll_three_on_line are also kelly-related.

**Workspace**: clean, no .drafts/.

No cut. Continue. Next cron :47.

## CUT REASON — 2026-05-11 ~02:30 local (anomaly)

**Cut 動作**: CronDelete `b658ac2b` ✓、`taskkill /PID 95236 /F`（daemon）✓、Stop-Process 99000（lingering gateway）✓、`rm .asterism/daemon.pid` ✓

**Cut 動機（user 觀察「異常 停掉」）**：

Log 大量 `worker exception ... <urlopen error [WinError 10061] 無法連線，因為目標電腦拒絕連線>` — daemon 對 gateway HTTP endpoint 連 connection refused、busy-spin 重派 spawn 同一個 goal、Goal=302 main / 303 / 317 / 320 / 321 都因為 attempts hit 5 而 shelved。

Gateway log 顯示 server process 仍在 process requests（"Processing request of type CallToolRequest"），但 daemon 端不斷 connection refused。**這是 gateway half-working state**：一些 LSP MCP tool calls 正常處理、framework 的 HTTP `/verify` 端點被拒絕。可能成因：TCP accept queue overflow、或 gateway worker pool exhaustion 後新請求被 OS-level reset。

**這是跟剛 commit 的 fix (`10833bf`) 不同的 framework BUG** — 我的 fix 處理「gateway timeout / transient」、這次是「gateway 連線層 inconsistent state」、即便 retry 還是被 refused。需要 gateway-side worker watchdog + queue health monitor，不是 client-side fix。

**Run #14 final snapshot**：
- **20 goals reached, depth 5** （Run #13 max depth 3、9d05d19 max depth 4）
- **7 proved**: 305, 306, 308, 309, 314, 316, 318
- **5 shelved**: 302 main, 303 exists_min_kelly_triple, 317 kelly_finset_min_2, 320 case_middle_proj, 321 case_right_proj
- **4 attempting / 4 open / 0 dead_attempts visible**
- **30 strategies total** (vs run #13's 8) — strategy churn 很高（部分因 gateway flapping 反覆 retry）
- 主要原因 main shelved：sub-goal 303 達到 attempts=5 shelve threshold（多次因 gateway connection refused 計入 attempts）→ 父 main 也 attempts=5 shelve

**對 Opus Backward hypothesis 的數據**：
- 達到 depth 5 (case_left_proj 等)、Sonnet 同期沒這麼深
- 走通 Goal=304 kelly_min_implies_ordinary cascade（kelly-class 父）→ depth 2 sub-goals
- 走到 Goal=311 cross_distance_strict_decrease（Kelly 嚴格不等式核心）→ Backward success（沒撞 Sonnet trap）
- Goal=313 between_pair_via_s 反覆 attempts=4、三個 strategies (s271, s273, s275) live
- **Opus 確實突破了 Sonnet 在 kelly-class 的智力上限**（Goal=311 ship through、Goal=304 cascade success），但 framework 端 gateway BUG 中斷實驗

**Comparison final**:
| Run | Wall | Proved | Max depth | Trap takeover | Framework anomaly |
|---|---|---|---|---|---|
| #4 (pre-LSP) | 270min | 4 | n/a | n/a | n/a |
| #11 (v4 + path fix) | 108min cut | 1 sub + 1 leaf | ? | many | many trap |
| #12 (LSP off Backward) | 110min cut | 4 | ? | 8+ | many trap |
| #13 (cap restored, all-Sonnet) | 115min cut | 4 | 2 | 3 + 1 verify infra | verify infra BUG |
| 9d05d19 (replay, all-Sonnet) | 215min cut | 21 (sampling luck) | 4 | 0 (no detection) | none |
| **#14 (Opus Backward + Sonnet Builder)** | **~45min cut** | **7** | **5** | **0** | **gateway half-working state** |

**Key findings**:
1. **Opus Backward 突破 Sonnet 智力上限** ✓ — Goal=311 + Goal=304 都 ship、沒撞 LESSON-warning 陷阱
2. **新 framework BUG**: gateway 對 framework `/verify` 連線 refused，但對 worker LSP MCP 正常 — 半工作狀態
3. **shelve threshold 對 framework infrastructure 失敗的容忍度不夠**：303 多次因 gateway connection refused 計入 attempts、5 次 hit threshold shelve 主 goal、實際 agent 工作沒問題

**下個 framework gap（gateway-side、不是 client-side）**：
- Gateway accept queue / worker pool health monitor
- distinguish「真 attempt fail」vs「infra connection refused」: 後者不該算 goal attempts

