# LSP Integration — 技術細節

`lsp_integration.md` 的伴隨檔。實作 phase 才會用到的 process tree、RAM 數字、
tool 詳細參數、JSON-RPC 介面、PoC 數據都在這。決策時不需要看本檔。

---

## 目錄

1. [LSP server 拓撲](#1-lsp-server-拓撲)
2. [Lifecycle 與 pre-warm 細節](#2-lifecycle-與-pre-warm-細節)
3. [Tool surface 詳細](#3-tool-surface-詳細)
4. [Signature change broadcast 機制](#4-signature-change-broadcast-機制)
5. [Forensic 細節](#5-forensic-細節)
6. [PoC 結果](#6-poc-結果)
7. [Process tree](#7-process-tree)
8. [JSON-RPC 介面要點](#8-json-rpc-介面要點)
9. [Spike 代碼引用](#9-spike-代碼引用)

---

## 1 LSP server 拓撲

```
daemon
└── server pool
    ├── lake serve [proj_nonexpansive]   (~1 GB)
    │   ├── worker [Main.lean]            (~3 GB)  ← agent A 在 edit
    │   ├── worker [helpers/X.lean]       (~3 GB)  ← agent B 在 edit
    │   └── worker [helpers/Y.lean]       (~3 GB)  ← idle、TTL 倒數
    ├── lake serve [cantor]               (~1 GB)
    │   └── worker [Main.lean]            (~3 GB)
    └── lake serve [SG]                   (~1 GB)
        └── (無 worker、SG 無 active edit)
```

關鍵：
- **一台 server 帶多 worker**、N = 該題 active edit 檔數、不是總檔數
- 沒人 edit 的檔、就算 problem 有 50 個 helper、也只有 disk 上的 .olean、
  不耗 RAM
- pipeline 結束不殺 server、只 didClose 自己編輯的檔、idle worker TTL 自動
  回收
- 不同 problem 各自一台 server、互不影響

### 1.1 RAM 預算估算

| 場景 | server count | 活躍 worker | RAM |
|---|---|---|---|
| 單題單 agent | 1 | 1 | ~5 GB |
| 單題 3 agent 平行 | 1 | 3 | ~10 GB |
| 3 題各 1 agent | 3 | 3 | ~12 GB |
| 6 題各 2 agent | 6 | 12 | ~42 GB |

workstation 可、laptop 注意。worker LRU eviction 是 first-class 機制。

---

## 2 Lifecycle 與 pre-warm 細節

| 階段 | 動作 | 時間 |
|---|---|---|
| daemon startup | 對所有 active problem spawn `lake serve` + didOpen dummy 檔 | ~145s 冷 / ~25-30s 暖 |
| work item 拿到 | framework didOpen target | ~22s warm worker 起 |
| session 結束 | didClose target、worker idle、TTL 倒數 | — |
| TTL 過期 | worker exit、釋 ~3 GB | — |
| daemon 退 | 所有 server graceful shutdown | — |

cold mathlib import 一輩子付一次（OS file cache 暖了之後 5× speedup）。
pre-warm 是把這次冷啟動押在 daemon startup、之後 pipeline 全暖。

---

## 3 Tool surface 詳細

設計原則：**每個 action 自帶後果**。`apply_edit` return 自動帶 edit 後 cursor
位置 goal + 受影響 diagnostics、agent 不用主動 query。其他 tools 是 ad-hoc
探索、用在「想看別處」。

| Tool | 作用 | 主要參數 | 回傳內容 |
|---|---|---|---|
| `apply_edit` | 寫檔 + re-elab | `file, range, new_text` | 改後 cursor 位置 goal + 受影響 diagnostics |
| `goal_at` | 看別處 goal | `file, line, col` | 該位置 hypothesis + goal text |
| `errors_at` | 看 diagnostics | `file, line?` | error / warning 列表、含完整 Lean 訊息 |
| `try_tactic` | 試 tactic、不寫檔 | `file, line, tac` | 試後 goal、可 rollback |
| `list_files` | 看 problem file tree | (none) | tree + 每檔 sorry count |
| `create_file` | 新增檔（extract helper） | `path, content` | 初始 elaborate 結果 |
| `delete_file` | 刪檔（inline 回 main） | `path` | 受影響依賴 |

### 3.1 實作形式（決策點 8）

候選：
- **MCP server**：LSP 操作是長 lifecycle、stateful、MCP 對這設計乾淨。傾向。
- **Bash subcommand**：`asterism lsp goal-at <file>:<line>:<col>`、簡單、
  shell-friendly、但需自己管 LSP 連線狀態
- **Anthropic native tool**：客製化最緊、但跟 Anthropic API 綁定、跨模型不便

---

## 4 Signature change broadcast 機制

framework 偵測：

1. agent 改了 helpers/X.lean、比對 declaration list（before / after）
2. 區分：proof body 變 vs signature 變
3. 若 signature 變、找所有 import X 的檔（掃 import graph）
4. 對每個受影響的 active worker：直接 didChange 觸發 re-elab、agent 立刻看 break
5. 對 idle worker：等下次 didOpen 才 elab、暫不通知
6. 記錄 signature 變更歷史到 forensic（before / after / 影響範圍）

範圍與通知策略是決策點 3。三個方向：
- **全 import 鏈**：所有 transitive import 都廣播。最完整、可能成本爆。
- **1 hop**：只直接 import 廣播。便宜、可能漏 indirect break。
- **標記不立刻 re-elab**：標 dirty、等該檔被 didOpen 才 elab。最便宜、
  agent 體驗最差（事後才發現破）。

---

## 5 Forensic 細節

### 5.1 Session events schema

每 session 紀錄：
- 開始時 problem state（檔列表、各檔 sorry count）
- 事件 timeline（重要事件、不全錄）
- 結束時 state + LESSONS（agent 自寫）
- session outcome

### 5.2 Event types

| Event | 必記 / 壓縮 | 內容 |
|---|---|---|
| `apply_edit` | 壓縮 | 改動 hash + cursor 軌跡、不全錄文字 |
| `signature_change` | 必記 | declaration name、before / after sig、影響範圍 |
| `helper_create` | 必記 | path、初始 statement |
| `helper_delete` | 必記 | path、刪前 sorry count |
| `sorry_count_change` | 必記 | file、before / after count、delta |
| `error_appear` | 必記 | file、line、message |
| `error_disappear` | 必記 | file、line、原 message |

### 5.3 存儲量控制

edit trace 全錄會撐爆 SQLite。用「**interesting moments**」濾——sorry 變、
error 出現 / 消失、signature 改、helper create 才存快照。其他 edit 只記
metadata。顆粒度是決策點 7。

---

## 6 PoC 結果

完整數據見 `spike/README.md` + `spike/results.json` + `spike/pn_results.json`。

### 6.1 冷啟動

- spawn `lake serve` → `initialize` 回應：2.0s
- + didOpen mathlib import 檔 → elaborate 完成（OS cache 冷）：146s
- 同樣動作 OS cache 暖：~25-30s（5× speedup）

### 6.2 Latency（warm worker）

- `$/lean/plainGoal` p50 1.3 ms / p99 2.4 ms（單 import Mathlib + sorry
  fixture、N=50）
- PN monolith plainGoal 4-15 ms（包 8 theorems 的 130 LOC 真實檔）
- didChange → publishDiagnostics 真實 server work <100 ms（spike 量到 0.30s
  是 sleep floor）

### 6.3 RAM（單 server、單 worker、PN monolith）

- `lake serve` parent: 11 MB
- `lean --server`: 1.15 GB
- `lean --worker`: 3.26 GB
- 總: 4.68 GB

### 6.4 並發（兩 server 同時 elaborate）

- 兩個 monolith 並行 elaborate：27.1s
- 各 4.6 GB、合計 9.2 GB
- 線性疊加、無 lock contention

### 6.5 Edit feedback（PN monolith）

| Edit | didChange → diag | Diagnostic 內容 |
|---|---|---|
| body → `sorry` | 0.30s* | warning "declaration uses `sorry`" |
| body → `intro ... ; exact rfl` | 0.30s* | error "Type mismatch ..." 含完整 Lean 訊息 |
| body → restore | 0.30s* | 0 diagnostics |

\* 0.30s 是 spike 代碼裡的 sleep floor、實際 server work <100ms。

---

## 7 Process tree

```
lake serve (pid P, ~11 MB)         # routing parent
└── lean --server (~1.15 GB)       # LSP brain
    ├── lean --worker FILE_A (~3 GB)   # 每個 active edit 檔一隻
    ├── lean --worker FILE_B (~3 GB)
    └── ...
```

- workers 共讀同份 mathlib olean（OS-level mmap 共享 page cache、in-memory
  elaboration result 不共享）
- 每個 worker 獨立 process、kill 掉只影響該檔、parent server 不死
- 同一台 server 可帶 N worker、N = 該題 active edit 檔數

---

## 8 JSON-RPC 介面要點

LSP 標準 + Lean 擴充：

- `initialize` / `initialized` / `shutdown` / `exit` — 標準生命週期
- `textDocument/didOpen` / `didChange` / `didClose` — 檔案狀態
- `textDocument/publishDiagnostics`（server → client）— error / warning / info
- `$/lean/fileProgress`（server → client）— 處理中 vs 完成
- `$/lean/plainGoal`（client → server）— 該位置 goal state

framing：`Content-Length: <N>\r\n\r\n<json-utf8>` 連續傳。

### 8.1 Windows 注意

不要用 `2>&1` redirect server stderr——PowerShell 5.1 會 wrap 成
NativeCommandError、把 `$?` 設成 `$false`、即使 exit code 0。

stdout 預設 cp950 encoder 不接 Unicode 數學符號（`⊢` `‖` `⟪` `ℝ` 等）。
Python 端 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` 解決。

---

## 9 Spike 代碼引用

- `spike/lsp_client.py` — minimal JSON-RPC client、~250 LOC、stdlib + psutil
- `spike/measure.py` — Q1-Q5 quantitative measurement
- `spike/pn_test.py` — PN end-to-end Phase A/B test
- `spike/pn_root_monolith.lean` — PN 全 inline 單檔（130 LOC、無 inter-file imports）

design doc 走完決策點、進實作 phase 後可以 `git rm -r spike/`、PoC 數據引用
轉到本檔內、`spike/results.json` + `spike/pn_results.json` 留 git 歷史
當 snapshot。
