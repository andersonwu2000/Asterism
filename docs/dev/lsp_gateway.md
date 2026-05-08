# LSP Gateway

把每個 spawn 各起一份 lake serve、改成所有 spawn 共用少數常駐 worker。
並行度跟 RAM 預算解耦。

狀態：Phase 1 完成（commit 54e6df9）。Phase 2 設計修正後待實作。

---

## 1 動機

LSP swap 落地後（commits `82772af..f738873`）每個 Builder/Backward spawn 在
spawn 開始時起一個 `lake serve` process、Mathlib 在每個 worker 的 in-memory
elaborated 結構獨立、4 並行就吃 12-20 GB RAM。想拉到 pool=8+ 直接撞 RAM 牆。

從 Lean 側分享 Mathlib 的 elaborated state 不可行（kernel session 設計上就是
isolated、要動就得 fork Lean）。從框架側可走：
- (A) 降 pool ── 不能解 user's goal（要的是更多並行）
- (B) 共用 server ── Phase 1 走過、發現省的不夠
- (C) 共用 worker ── Phase 2 走的路、本檔重點

---

## 2 兩層 RAM 帳（Phase 1 落地後才釐清）

每個 LSP backend 樹 RAM 拆兩層：

| 層 | 角色 | RAM | 共享性 |
|---|---|---|---|
| **Server**：lake serve + lean --server (Watchdog) | LSP 控制平面、routing、生命週期 | ~1.6 GB（固定） | 多 spawn 可共用一份 |
| **Worker**：lean --worker（per didOpen URI） | 該檔的 Mathlib elaborated state、tactic context、term tree | ~3 GB（per worker） | 不可共享（每 worker 獨立） |

- Phase 1 共用 server、N 個 spawn 共用 1 個 server ── 省 (N-1) × 1.6 GB
- 每 spawn 仍然要自己的 worker、共 N × 3 GB ── **這是真實瓶頸**

→ Phase 1 把 RAM 從 4.9 N 降到 1.6 + 3.3 N、有省但仍線性、pool=8 仍吃 28 GB。

---

## 3 spike 關鍵發現：worker 內容 swap 比 fresh worker 快 7-9 倍

`_spike/spike_content_swap.py`（2026-05-08）：

```
[1] 首次 didOpen warmup（fresh worker、Mathlib import 重建）  : 27.2s
[2] didChange → proof A（同 worker、整檔換內容）              : 4.0s
[3] didChange → proof B                                      : 3.0s
[4] didChange → proof C（不同 namespace usage）               : 3.5s
[5] didChange → warmup（重置回 idle 內容）                    : 3.0s
```

**worker 不死、只用 didChange 整檔替換 → 3-4s**（下限是 wait_settled
stable_for=3s、真實 elaborate <1s）。

原因：worker 已活、Mathlib namespace 已在 memory、`import Mathlib` 不重跑、
只重 elaborate body。Lean 4 elaboration 對「imports 不變、body 全換」的
didChange 走快路徑。

→ **Phase 2 用這個機制、不殺 worker、用 didChange 換內容服務不同 pipeline**。

---

## 4 Phase 2 架構

### 模型

```
1 個 server（lake serve + Watchdog）        ── 固定 1.6 GB
├──→ Worker 0（slot URI _gateway_slot_0.lean、預載 Mathlib）
├──→ Worker 1（slot URI _gateway_slot_1.lean）
├──→ ...
└──→ Worker W-1（slot URI _gateway_slot_{W-1}.lean）
                                            ── 各 ~3 GB、共 W × 3 GB
N 個 pipeline 並行（pool 多大開多大）
        ↓
        agent tool call 才打 gateway
        ↓
gateway 看：這 pipeline 的內容當前在哪個 slot？
        ├ [hot]  命中 → 直接做 tool 操作（~ms-1s）
        └ [miss] 沒命中 → 找最 idle 的 slot、didChange 換內容（~3-4s）→ 再做
```

### 排隊單位 = tool call（不是 pipeline）

Pipeline 不持有 slot。Slot 由「最近用內容」沾黏。Pipeline 進長 thinking 不
打 tool 時、它的 slot 內容會被別的 pipeline 替換掉、它下次 tool call 進來
時再 didChange 換回（付一次 ~3-4s miss）。

→ N 可以遠大於 W。pool 想多大開多大。

### Server / Worker / Slot 對應

- **Server 數**：1（多 server 沒收益、每個多 1.6 GB Watchdog overhead）
- **Worker 數 = Slot 數 = W**：唯一 RAM 控制旋鈕
- 1 個 Watchdog 帶 W 個 worker、無 server 層瓶頸（Watchdog 是 multiplexer、
  routing 是 µs 級、各 worker 獨立 process 真並行）

### 排隊只在 worker 層

| 層 | 會排隊？ | 原因 |
|---|---|---|
| Client → Watchdog stdin | 不會 | `_send_lock` 序列化但 1 µs 級寫入 |
| Watchdog 內部 routing | 不會 | 純 dispatch、無 elaborate |
| Worker elaborate | **會** | 同 slot 任意時刻只能 1 個 tool 做 elaborate |
| 不同 worker 之間 | 不會 | 各自獨立 process、CPU 多核並行 |

→ 並發 ≤ W 個 tool call 真並行；第 W+1 個瞬間到、gateway 排到下個 free slot。

---

## 5 RAM 估算

固定：1 server (~1.6 GB) + W workers (~3 GB) + N claudes (~0.33 GB)

```
RAM ≈ 1.6 + 3.0 W + 0.33 N
```

| 配置 | RAM | 並行 pipeline |
|---|---|---|
| Phase 1 N=8（現在） | 28 GB | 8 |
| Phase 2 W=4、N=16 | 19 GB | 16 |
| Phase 2 W=4、N=24 | 22 GB | 24 |
| Phase 2 W=6、N=16 | 25 GB | 16 |
| Phase 2 W=8、N=24 | 33 GB | 24 |

**32 GB 機器：W=4-6 + pool=16-24 真實可行**。

W 是 RAM 旋鈕、N 是並行旋鈕、解耦。

---

## 6 cache miss penalty 估算

對 N=16、W=4：

- 第一次 tool call 一律 miss（~3-4s）
- 同 pipeline 連續 tool call、若沒被擠走 = hit（~1s）
- agent 進長 thinking、slot 內容被替換、回來時 miss（~3-4s）

agent 行為觀察（過往 session log）：
- read/grep 階段：tool 連串、間隔 < 5s ── 期望多半 hit（slot 黏住）
- thinking 階段：tool 間隔 30+ s ── 期望被擠走、下次回來 miss
- validate_file 階段：tool 集中、期望 hit

每 spawn 期望 miss 次數：~5-10 次 × 3-4s = **+15-40s wall**。對 5-15 min
spawn 是雜訊。

---

## 7 Tool call 流程細節

每 pipeline 在 gateway state 持有：
- `pipeline_id`、`target_path`、`file_content`（mirror、含 agent 累積編輯）
- `current_slot`：當前內容所在的 slot id（None = 沒命中）

每 slot 持有：
- `slot_id`、`slot_uri`（固定 `_gateway_slot_<i>.lean`）
- `lock`（互斥）
- `loaded_pipeline_id`：當前裝載的內容屬於誰
- `last_used_ts`：LRU 用

Tool call from pipeline X：

```
acquire any slot lock（preferring slot already loaded with X）
if slot.loaded_pipeline_id != X:
    didChange slot to X.file_content
    wait_for_diagnostics_settled  ← miss penalty 在這
    slot.loaded_pipeline_id = X
do tool op（apply_edit / goal_at / errors_at / validate_file）
update X.file_content if edited
slot.last_used_ts = now
release lock
```

Slot 選擇順序：
1. 已 loaded with X 的（hot）
2. free slot（unlocked + loaded_pipeline_id 是 idle 已久者）
3. LRU 中的 unlocked slot

---

## 8 Phase 階段（修正後）

### Phase 1（已完成、commit `54e6df9`）

K=1 server、移植 4 tools 到 HTTP MCP gateway。已驗 PN e2e（47.3 min wall、
real lake-pass）。RAM 從 12-20 GB 降到 14-15 GB（pool=4 時）。

### Phase 2（待做）── 持久 worker 池 + 內容 swap

替換 Phase 1 的「per-pipeline didOpen / didClose」為「W 個常駐 worker、
按需 didChange swap 內容」。

新增：
- `Tooling/lsp_gateway.py` 改寫 SessionMetadata + Slot pool 機制
- daemon startup 預起 W 個 worker（並行付 cold start）
- Tool call dispatch 加 slot 選擇 + lock + LRU eviction

修改：
- `_register_session` 不再 didOpen target file、只 stash file_content mirror
- `_release_session` 不再 didClose、只清 mirror

驗收：
- PN e2e 跑通、real lake-pass、axiom probe 過
- N=16, W=4 RAM ≤ 25 GB
- spawn wall 比 Phase 1 增 < 30%

工程量：~800-1000 LOC、~2 天。

### Phase 3 ── Lifecycle + Supervision

- worker 健康檢查（定期 ping noop call）
- worker 死掉自動補回
- 定期重啟 worker 防 LSP memory leak（lean 長跑可能漏）
- Daemon Job Object / process group、parent 死 children 自動回收
- Graceful shutdown

### Phase 4 ── 廢棄 + 文件同步

- 移除 `lsp_mcp_server.py:main()` stdio entrypoint
- `_write_mcp_config` 移除 `PYTHONPATH=workspace` 殘留
- `architecture.md` / `data-flow.md` / STATUS.md 同步

---

## 9 不變式

實作期間必守：

- **Slot lock 必嚴**：同 slot 任意時刻只 1 tool op 進行。違反 → 內容亂、
  worker state 損壞。
- **file_content mirror 是 single source of truth**：slot 內容是 mirror 的
  cache、agent 看到的編輯結果以 mirror 為準。slot 被別人換走、mirror 不丟。
- **didChange 整檔替換、不用 incremental**：incremental 對「全換」沒收益、
  且我們的 file_content mirror 模型本來就是整檔狀態、用 full content 最簡單。
- **worker 死 → 對應 slot 標 invalid**：下次借用必先重新 didOpen warmup。
  防 zombie slot 服務 stale state。

---

## 10 風險與緩解

| 風險 | 緩解 |
|---|---|
| Watchdog 多 worker scaling 限制 | 量過 1 server + 多 worker spike 沒問題；Phase 3 加監控 |
| Worker memory leak 久跑漏 | Phase 3 定期 recycle |
| didChange 對「imports 不變」假設失效（agent 改 imports） | 我們的 ensure_imports 流程其實已經框定 imports；極端 case 走 fresh worker fallback |
| Slot lock 死鎖 | 全部 lock acquire 走 timeout、超時 fail-fast |
| Pipeline 結束沒釋放 | gateway 偵測 session inactivity、自動清；下次 borrow 自然會 evict |

---

## 11 Rollback

`git revert <Phase-2-commit-range>` + 重啟 daemon 回 Phase 1。Phase 1 的
HTTP MCP + per-spawn register/release 行為保留、Phase 2 是「pool 機制重構」、
不改 wire protocol。
