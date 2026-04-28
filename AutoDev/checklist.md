# Orchestrator Checklist

工作目錄：{workspace}
文件目錄：{workspace}/AutoWorkspace

**每個步驟執行前，先唸出指令再行動**

> **Hybrid mode 預設**：R1 Implement + R3 Fix 由 orchestrator 本體（Opus 4.7）直接執行，**不 spawn Sonnet subprocess**。R2 Review 永遠 spawn 獨立 Auditor subprocess。詳見 `orchestrator.md ## Hybrid mode`。
>
> 下方 R1 / R3 「呼叫 Executor」+ `claude -p ... --session-id` block 為**模板殘留**——hybrid mode 下 orchestrator 直接做、不執行 spawn 指令。`state.md ## Sessions` Executor 欄位寫「（由 orchestrator 直接做）」。
>
> 例外：user 明確指示「這個 cycle spawn sonnet」才走 subprocess 流程。orchestrator 不自行判斷「量大改 spawn」。

---

## Round 0：Cycle 起點

**唸出：「cycle C{N} 開始」**

1. 檢查 `task.md ## Note`（存在則優先）
2. 更新 `state.md ## Step`

#### 備忘錄

- 每個 cycle 開始時建立新 session，不跨 cycle 延續
- 首次呼叫 agent 時用 `--session-id` 搭配隨機 UUID
- 若 `task.md ## 模型` 有指定模型，首次呼叫 agent 時加 `--model {model}`
- 從 JSON output 的 `session_id` 欄位取得 ID 並寫入 `state.md ## Sessions`

Session 恢復（auto-compact 後或 user 手動恢復）：
1. 閱讀 `state.md ## Resume hint`
2. 閱讀 `task.md ## Note`
3. 閱讀 `state.md`
4. 從 `state.md ## Step` 對應步驟繼續，用 `--resume` 延續 agent session

Agent 異常：
1. 在 `state.md ## Summary` 記錄
2. 以 `--resume` 重試
3. 若 `--resume` 失敗，重新呼叫 agent 並更新 `state.md ## Sessions`：
    ```bash
    claude -p "
    當前 Step：C{N} R{M} {role}
    工作目錄：{workspace}
    任務指示：{framework}/roles/{role}.md
    {對應階段的 message}
    " --output-format json --dangerously-skip-permissions --allowedTools "{tool list}" --session-id "${UUID}"
    ```

---

## Round 1：Implement

**唸出：「R1 Implement — 進行開發」**

若 `task.md ## Note` 有更新，應提醒 agent

1. 首次呼叫 Executor 並更新 `state.md ## Sessions`
    ```bash
    claude -p "
    當前 Step：C{N} R1 executor
    工作目錄：'{workspace}'
    任務指示：'{framework}/roles/executor.md'
    " --output-format json --dangerously-skip-permissions --allowedTools "Read,Grep,Glob,Edit,Write,Bash" --session-id "${UUID}"
    ```
2. 等待 Executor 完成 → 更新 `state.md ## Step`
3. 若 `devlog.md ## 指令` 為「暫停」 → 暫停，說明理由並等待使用者審批

---

## Round 2：Review

**唸出：「R2 Review — 呼叫 Auditor 進行驗收」**

若 `task.md ## Note` 有更新，應提醒 agent

1. 首次呼叫 Auditor 並更新 `state.md ## Sessions`
    ```bash
    claude -p "
    當前 Step：C{N} R2 auditor
    工作目錄：'{workspace}'
    任務指示：'{framework}/roles/auditor.md'
    " --output-format json --dangerously-skip-permissions --allowedTools "Read,Grep,Glob,Edit,Write,Bash" --session-id "${UUID}"
    ```
2. 等待 Auditor 完成 → 更新 `state.md ## Step`
3. 若 `audit.md ## 指令` 為「暫停」 → 暫停，說明理由並等待使用者審批

---

## Round 3：Fix

**唸出：「R3 Fix — 呼叫 Executor 進行修復」**

若 `task.md ## Note` 有更新，應提醒 agent

1. 若 `audit.md ## 指令` 為「跳過」：
    1. 初始化 `audit.md ## 指令` 為「無」
    2. **跳過 Executor，直接進入 `## Round 4`**
2. 呼叫 Executor
    ```bash
    claude -p "
    當前 Step：C{N} R3 executor
    1. 審視 'audit.md' 意見是否合理
    2. 修復 R2 Review 發現的問題
    3. 'git commit' 並覆寫 'devlog.md ## Commit'
    " --resume "{executor_session_id}" --output-format json --dangerously-skip-permissions
    ```
3. 等待 Executor 完成 → 更新 `state.md ## Step`
4. 若 `devlog.md ## 指令` 為「暫停」 → 暫停，說明理由並等待使用者審批

---

## Round 4：Cycle 終點

**唸出：「Cycle 結束 — 更新摘要，檢查終止條件」**

1. 更新 `state.md ## Summary`、`state.md ## Phase progress`
2. 簡要介紹本 Cycle 做了什麼
3. 檢查終止條件，滿足任一即停：
    - 達 `task.md ## 終止條件` 定義的終止條件
    - `task.md ## Note` 要求停止

若終止條件滿足 → 將所有 cycle log 移動/覆蓋到 `log/archive/`

若終止條件不滿足 → **唸出：「未達終止條件，回到 Cycle 起點」**，勿擅自終止 Cycle

回到 Cycle 起點
