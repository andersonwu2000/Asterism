# Builder LSP swap

把 Builder pipeline 從「寫一次檔退出、framework lake build」改為「session 內
LSP 連續編輯、退出後 framework 仍 lake build 驗證」。

最小改動。Architect / Strategist / multi-agent 等更大架構議題不在本檔範圍。

狀態：設計已收斂、待實作。

技術細節（LSP wait 邏輯坑、MCP 協議、tool 詳細參數）見本檔末段「附錄」。

---

## 1 動機

當前 Builder pipeline 的反饋環是 spawn-level：agent 寫完 .lean 退出、
framework `lake build` 結果（success / stderr）餵下次 spawn。
**每次反饋都需要新 spawn、agent 不能在 session 內 see-and-fix**。

LSP（透過 MCP server 暴露 `apply_edit` / `goal_at` / `errors_at`）讓 agent
在同 session 內看 goal 變化、看 type error、改 tactic、再看——跟人在 VS Code
寫 Lean 的工作流一致。

實證（spike 2026-05-07）：sonnet 在這個 surface 下對 cantor 級題目會做漸進式
edit、並用 `goal_at` 探索狀態（而非單純 nuke-and-rewrite）。

---

## 2 範圍

### 動

- Builder pipeline spawn 時起 MCP server（LSP-backed）
- Builder prompt 教用 `apply_edit` / `goal_at` / `errors_at`
- Builder 退出條件「寫完一次」→「LSP 回 0 errors AND 0 sorry」
- claude_cli `--mcp-config` 接 LSP MCP server

### 不動

- Backward planner、cascade rules、dedupe、library promotion
- pool=12 並行
- Forensic schema（dead_attempts 1:1 不變）
- Manifest / BRIEF / LESSONS / Reflection
- claude_cli wrapper 整體結構
- Read / Write / Edit / Grep / Bash 內建 tool（保留、agent 自決何時用）
- lake build 角色（仍是 ground-truth 驗證、cascade 規則的依據）
- retry 機制（in-pipeline `--resume` 不變）

---

## 3 決策（已拍板）

### 3.1 MCP server lifecycle = pipeline

跟隨 Phase 7 確立的 pipeline = session 單位。pipeline 起 → MCP 起（LSP 冷
~25s）→ pipeline 內 retry 用同一 warm MCP → pipeline 退 → MCP 關。

優點：cross-pipeline state 不存在、隔離乾淨、跟既有 budget / lifecycle 模型
一致。25s 冷啟對 5-15 min pipeline budget 是 ~5%、可接受。

### 3.2 in-pipeline retry 保留

LSP feedback in-session ≠ 零錯失。spike 證明 LSP 對長 proof 可能假陽性
（fileProgress empty 時 publishDiagnostics 還沒送來）。雖然本次工程加了
`wait_for_diagnostics_settled` 修這個坑、但 retry 仍是 last line of defense
——lake build stderr 抓到的 LSP 漏的、靠 retry 修。

retry 在同 pipeline 內 → 用同一個 warm MCP、不再付冷啟、相容。

### 3.3 lake build 仍跑、仍是 ground truth

LSP 在 session 內提供快速反饋、lake build 在 session 退出後是權威驗證。兩者
角色明確不重疊：feedback vs verification。不省 lake build 這刀。

### 3.4 全切（不並存）+ 明確 rollback 點

- 不做 `builder_mode: legacy | lsp` 並存。維護兩條 code path 成本高、收益低。
- cut 前 user 指定一組既證 problem 走 LSP path 重證、確認都過、再切。
- cut commit 寫明 rollback 指令（`git revert <hash>`）、tag `pre-lsp-cutover`。
- 切後監控、任何既證 problem 失去可重證能力 → 立刻 revert。

### 3.5 Tool surface

agent 同時擁有：
- 內建：Read / Write / Edit / Grep / Bash（含 Loogle 子命令）
- MCP：`mcp__lsp__apply_edit` / `mcp__lsp__goal_at` / `mcp__lsp__errors_at`

不刻意限制 agent 用哪個（不像 spike 的 `--tools ""` 強制路徑）。prompt 引導
推薦工作流但不禁止內建。

理由：spike v9 顯示純 LSP 路線下 sonnet 會幻覺 lemma 名（沒 Loogle 驗）。
保留內建工具讓 agent 有 fallback。

---

## 4 工作項

```
Tooling/lsp_mcp_server.py          new
  - 直接搬 spike/agent_pn/mcp_server.py 框架
  - 加 wait_for_diagnostics_settled（取代壞的 wait_for_file_done + sleep(0.5)）
  - lifecycle 接 Asterism 結構（PROBLEM_DIR / attempts_dir 等）

Tooling/llm/claude_cli.py          modify
  - Builder kind spawn 時加：
      --mcp-config <path>
      --allowed-tools 加上 mcp__lsp__apply_edit mcp__lsp__goal_at mcp__lsp__errors_at
  - 其他 kind（Backward / Reflection / etc）不變

Tooling/pipeline/builder.py        modify
  - spawn 前 fork MCP server 子程序、寫 mcp_config.json
  - pass config path 給 claude_cli
  - pipeline 退時 reap MCP 子程序
  - retry 路徑：keep MCP 活著、claude --resume 復用

Tooling/prompts/builder.md         modify
  - 加段：「也可以用 LSP tools 做 incremental editing」
  - 不強制、提供作為 alternative workflow
  - 說明何時 LSP 比 Edit 好（看 goal、看當前 errors）

tests/                             new + modify
  - test 基本 spawn-with-MCP 跑得起來
  - test retry 路徑復用 MCP
  - test lake build 仍跑、結果仍對（regression test）
```

預估工程量：1 週、含寫 + 測 + 跑 user 指定的既證 problem 重證驗證。

---

## 5 驗證 + 切換流程

```
1. Phase 1 工程完成（Tooling/* 改動 + 新 mcp_server）
2. user 指定一組既證 problem
3. 用 LSP path 跑該組、確認都仍能證
4. 任何一題不過 → 回頭修、不切
5. 全過 → 
   git tag pre-lsp-cutover
   git commit -m "Switch Builder to LSP" 
                "(revert with: git revert HEAD)"
   merge / 部署
6. 監控 1-2 週、任何 proved problem 失去 reproved 能力 → revert
```

---

## 6 風險

- **LSP 冷啟成本累積**：所有 Builder pipeline 都付 25s 冷啟。pool=12 並行下、12 個 LSP server 同時開、瞬時 RAM ~12 × 4 GB = 48 GB peak。要驗 workstation 撐得住、否則 lifecycle 改 per-problem MCP（決策點 3.1 的方案 c）。
- **LSP 假陽性逃過 lake build**：rare 但可能。retry + lake build 是雙保險、應該夠。
- **特殊 problem class 行為差**：手上 5 個 proved 偏 mathlib-heavy 中等規模、不一定 cover 所有失敗模式。切後監控期間如果某類 problem 規律性失敗、可能要 patch 而非全 revert。
- **Tool surface 矛盾**：agent 同時看到 Edit 跟 apply_edit、可能行為混亂。prompt 引導要清楚「proof body 用 apply_edit、其他改動用 Edit」。

---

## 7 後續（不在本 phase）

- **Strategist pipeline**：對應 v3-archive 的 Strategist、解 Asterism 18-strategies 重試問題。設計另開檔。
- **Multi-agent same problem**：spike 觀察沒看到明顯收益、暫不做。
- **MCP server 跨 pipeline 共享**：如果 25s 冷啟成本不可接受、可升級到 daemon 級 lifecycle。看 Phase 1 數據再決定。

---

# 附錄

## A LSP wait 邏輯坑（spike 教訓）

`$/lean/fileProgress` 走 `processing → []` 信號 **不等於** elaborate 真做完。
Lean 對 100+ LOC 的 proof 可能 fileProgress empty 後 25 秒才送出
`publishDiagnostics`。spike v8 因為在 fileProgress empty + 0.5s grace 就讀
diagnostics、結果讀到 stale 空值、agent 自評成功實際 build 不過。

修法：`wait_for_diagnostics_settled`：每 0.5s poll diagnostics、count + 訊息
fingerprint 連續 3 秒不變才返回。max_wait=90s safety。

實作就 ~30 行 Python、放 `Tooling/lsp_mcp_server.py` 內。

## B 進程模型

```
Builder pipeline session：

claude (1 process)
└── claude 透過 stdio 跟 MCP server 講話
    │
    └── lsp_mcp_server.py (Python subprocess)
        ├── 持有 LspClient（spawn lake serve subprocess）
        │   └── lake serve
        │       └── lean --server
        │           └── lean --worker [target.lean]   (~3 GB)
        └── 三個 tool handler
```

pipeline 退 → claude 退 → MCP server 收 SIGTERM → atexit 觸發 LSP shutdown。

## C MCP 工具回傳格式

`apply_edit` 回傳 JSON：
```
{
  "file": "...",
  "edit": "replaced lines X-Y; file is now N lines",
  "goal_at_edit_start": "<rendered markdown of goal at line X col 2>",
  "diagnostics": [{"line", "col", "severity", "message"}, ...],
  "diagnostic_count": int
}
```

`goal_at` / `errors_at` 同 spike 已驗、直接搬。

## D 決策速查

| # | 決策 | 拍板 |
|---|---|---|
| 3.1 | MCP server lifecycle | 跟 pipeline |
| 3.2 | in-pipeline retry | 保留 |
| 3.3 | lake build | 保留為 ground truth |
| 3.4 | migration | 全切 + tagged rollback point |
| 3.5 | tool surface | 內建 + MCP 共存、agent 自決 |
