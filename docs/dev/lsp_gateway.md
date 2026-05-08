# LSP Gateway

把每個 spawn 各起一份 lake serve、改成所有 spawn 共用少數常駐 backend。
並行度跟 RAM 預算解耦。

狀態：spike 通過、Phase 1 待實作。

---

## 1 動機

LSP swap 落地後（commits `82772af..f738873`）每個 Builder/Backward spawn 在
spawn 開始時起一個 `lake serve` process（child of claude）、Mathlib 在每個
worker 的 in-memory elaborated 結構獨立、4 並行就吃 12-20 GB RAM。想拉到
pool=8+ 直接撞 RAM 牆。

從 Lean 側分享 Mathlib 的 elaborated state 不可行（kernel session 設計上就是
isolated、要動就得 fork Lean）。從框架側只能：
- (A) 降 pool — 不能解 user's goal（pool=4 → pool=8）
- (B) 共用 backend — 本檔走的路

---

## 2 範圍

### 動

- 新檔 `Tooling/lsp_gateway.py`：long-living asyncio HTTP server、daemon
  startup 起 K 個 lake serve backend、所有 spawn 經 HTTP MCP 連同一個
- `pipeline/__init__.py:_write_mcp_config`：MCP config 從 stdio command 改
  HTTP URL `{"type":"http","url":"..."}`
- 4 個 LSP tool（`apply_edit`/`goal_at`/`errors_at`/`validate_file`）從
  `lsp_mcp_server.py` 移植到 gateway、保持簽名不變（agent 看不到差異）
- daemon 啟動加 backend pre-warm 步驟、ready 才開放 dispatch

### 不動

- agent 看到的 tool 簽名 + 行為（apply_edit/goal_at/errors_at/validate_file）
- pipeline 流程（spawn / parse / cascade）
- file-level lock（Asterism 已有：one pipeline per goal at a time）
- prompt（agent 不知道 backend 是共用的）

### 廢棄（Phase 4）

- `lsp_mcp_server.py` 的 stdio main()（claude 自 spawn 模式）
- `_write_mcp_config` 裡 `PYTHONPATH=workspace` 的 env propagation

---

## 3 架構決定（2026-05-08 spike 完成 + user 確認）

| 議題 | 選擇 | 替代 |
|---|---|---|
| Backend 起動時機 | **Daemon startup pre-warm** | lazy on first request、standalone process |
| Phase 1 範圍 | **K=1 backend、移植 4 tools** | K=2 一次到位、純設計 doc |
| File state 隔離 | **Sticky per-pipeline_id** | round-robin、global K=1 |
| Transport | **streamable-http**（FastMCP） | sse（deprecated）、stdio |

理由：
- pre-warm：daemon 啟動付一次 ~30-145s cold start、所有後續 spawn 不再付
- K=1 first：先驗 HTTP transport + lifecycle、不引入 routing 複雜度
- sticky：file state 一致性簡單、跨 backend broadcast 不必要
- streamable-http：MCP spec 2025-03-26 標準 transport、FastMCP 原生支援

---

## 4 Spike 結果（2026-05-08）

`_spike/spike_mcp_server.py` + `_spike/mcp_config.json` 驗：

- FastMCP `streamable-http` transport 在 port 8000、`/mcp` endpoint
- claude CLI 接 URL config（`{"type":"http","url":"..."}`）work
- 3 並發 client 命中同一 pid（51848）、call counter 累加 2→4 正確、無 race
- MCP session ID 由 protocol 自管（`Mcp-Session-Id` header）
- claude CLI 端 timeout / retry 在 HTTP transport 下沒看到異常

技術 unknown 全消、剩純工程實作。

---

## 5 Phase 分階段（每階段獨立 commit）

### Phase 1 — Gateway 原型（K=1）

新增：
- `Tooling/lsp_gateway.py`（~600 LOC）：
  - `LspBackend`：包一個 `lake serve` process + LspClient（重用 `lsp_mcp_server.py:LspClient`）
  - `Gateway`：FastMCP server、暴露 4 個 tool、每個 tool 內部呼叫單一 backend
  - `register_session(pipeline_id, target_path, problem, workspace)` — REST 端點、spawn-time 註冊 session metadata
  - `main()`：CLI entrypoint、起 backend 等 ready、起 HTTP server

修改：
- `Tooling/dispatcher.py`：daemon startup 加 gateway launch + readiness wait（~50 LOC）
- `Tooling/pipeline/__init__.py:_write_mcp_config`：stdio → HTTP URL（~30 LOC）
- `Tooling/agent.py`：spawn 前先 POST `/register`（~20 LOC）

驗收：
- PN run 在新 gateway 下跑通、root proved + lake build 過 + axiom probe pass
- RAM 量測：pool=4 + gateway K=1 ≈ 5-7 GB（vs 現在 12-20 GB）
- spawn cold start 不再付 LSP init（gateway 已 warm）

不動：tools 行為 / prompt / cascade / dedupe / library promote。

### Phase 2 — Backend Pool（K>1）

新增：
- `Gateway` 的 backend pool：K 個 LspBackend、`pipeline_id → backend_idx` 映射
- 第一次 tool call 時 sticky-bind：負載最低 backend、記錄 affinity
- spawn 結束時 release（gateway 透過 session lifecycle 偵測、或 framework
  顯式呼叫 `/release/<pipeline_id>`）

驗收：
- pool=8 + K=2 跑通 PN、RAM ≤ 12 GB
- 不同 pipeline 的 file edit 互不污染（同 backend 多檔正常、跨 backend
  本就隔離）

### Phase 3 — Lifecycle + Supervision

新增：
- Backend 健康檢查（每分鐘 ping `lake env lean -e "1+1"` 之類的 noop call）
- 死 backend 自動重啟（gateway 內部 supervisor）
- Periodic refresh：每 N 個 spawn 或每 X hour 重啟 backend（防 LSP memory leak）
- Graceful shutdown：daemon stop 時 gateway 先 drain in-flight、再殺 backend

驗收：
- kill -9 一個 backend、gateway 重起、in-flight spawn 看到 retry-able error、
  Phase 7 retry helper 接手
- 4 hr 連跑無 RAM 累積（vs 現在 LSP memory leak 問題）

### Phase 4 — 整合 + 廢棄

清理：
- 移除 `lsp_mcp_server.py:main()` stdio entrypoint（保留 LspClient 給 gateway 用）
- 移除 `_write_mcp_config` 裡 `PYTHONPATH=workspace` env propagation
- 更新 `architecture.md` / `data-flow.md` / STATUS.md
- 整合測試 + e2e 在 PN/cantor/SG 跑一輪

---

## 6 關鍵不變式

實作期間必守：

- **Sticky 必須穩**：同一 pipeline_id 的所有 tool call 一定同 backend。否則
  apply_edit 在 A、goal_at 在 B、看到 stale state、agent 寫錯。
- **File handle release**：spawn 結束（pipeline 收尾、watchdog kill、retry
  helper exhaust）時 backend 上該 spawn 開的所有 file 必須 didClose。否則
  backend 內存累積、最終 OOM。
- **Backend crash → spawn fail-fast**：backend 死、in-flight spawn 拿到 HTTP
  error、claude CLI 退出非 0、retry helper 看到、走正常 retry。**禁止**
  gateway 自己 swallow error。
- **Pre-warm 不擋 daemon shutdown**：daemon stop 信號到、gateway 立即響應、
  即使 backend 還在 cold start。

---

## 7 風險與緩解

| 風險 | 緩解 |
|---|---|
| FastMCP HTTP transport 在大流量 / 長 session 下不穩 | spike 已驗 3 並發 ok；Phase 1 PN run 是真實壓測（spawn 時長 5-15min、tool call 數十次） |
| Backend memory leak 累積 | Phase 3 periodic refresh（每 N spawn 重啟） |
| Sticky routing 失效（race / state 不一致） | 用 MCP session ID 作 routing key、protocol 層保證 monotonic |
| Daemon supervisor 自己崩 | Phase 3 加 PID file + 重啟邏輯 |
| Gateway 變單點故障 | Phase 3 加 backend supervisor、最壞情況 fallback 到 per-spawn stdio mode（保留 lsp_mcp_server.py 作 escape hatch） |

---

## 8 RAM / 性能預估

| 配置 | RAM | 並行 | Cold start cost |
|---|---|---|---|
| 現在 N=4 / 各起 K=4 | 12-20 GB | 4 | 每 spawn ~30-145s |
| Phase 1 N=4 / K=1 | 3-5 GB | 4 (queue) | 每 daemon startup 一次 |
| Phase 2 N=8 / K=2 | 6-10 GB | 8 | 每 daemon startup 兩次（並行） |
| Phase 2 N=16 / K=4 | 12-20 GB | 16 | 每 daemon startup 四次（並行） |

工具呼叫排隊延遲（worst case 4 並發瞬間擠 K=1 backend）：

- 單 tool call 5-30s（apply_edit/validate_file 較重）
- 4 個瞬間擠：第 4 個等 ~30s
- 對 5-15 min spawn 是雜訊（< 5%）
- 健康 spawn tool call 間隔 30-90s、實際 queue depth 多半 0-1

---

## 9 Rollback

`git revert <gateway-commit-range>` + 重啟 daemon。`lsp_mcp_server.py:main()` 在
Phase 4 之前一直保留、所以 Phase 1-3 期間 rollback 不需要還原 stdio path code。

Phase 4 完成後若要回 stdio mode：`git revert` 比較難（已刪 stdio main + 改 config
寫法）、需要從歷史 commit 找 deleted code 還原。為此 Phase 4 commit 必須清楚標
「point of no easy return」、執行前先驗 Phase 1-3 至少 2 週穩定。

---

## 10 Open decisions（Phase 1 開做前需拍板）

無。架構議題在 §3 表已收斂。Phase 1 開始實作前不需要再 user review。

Phase 2 / 3 各自可能有 sub-decision（如 Phase 2 的 sticky binding key 用
pipeline_id 還是 MCP session ID），到時候再開 sub-doc。
