# Orchestrator

任務目標：**運作開發循環直到 task.md 終止條件達成**

Cycle 開發流程：
1. R1 Implement: Executor
2. R2 Review: Auditor
3. R3 Fix: (Executor)

`{framework}` = 框架目錄，`{workspace}` = 工作目錄

---

## Hybrid mode（預設執行模式）

**R1 Implement 與 R3 Fix 由 orchestrator 本體（Opus 4.7）直接執行**——讀 phase doc / audit.md、改 source code、跑 pytest、git commit、寫 devlog。**不 spawn Sonnet subprocess**。

**R2 Review 永遠 spawn 獨立 Auditor subprocess**（fresh session、Opus 4.7）——獨立 review 是 hybrid mode 的核心保留項；orchestrator 自我 review 有 confirmation bias、不可省。

### Hybrid mode 緣由

C11–C18 觀察：silent-failure pattern 在 Sonnet R1 連續 6 cycle regression（即便 prompt 加 ⚠️ 警告 Sonnet 仍漏）。Opus 直接做 R1 品質高（實測 hybrid C17 R3 + C18 R1+R3 + C19 R3 連續穩）；R2 Auditor 即便 hybrid mode 也仍抓到 1 處 silent-failure（C18 R1 BACKWARD_MOCK fallback），證明獨立 review 不可省。

### spawn Sonnet 的例外條件

僅在以下情況可 spawn Sonnet subprocess、否則 orchestrator 直接做：
- **user 明確指示 spawn**（例：「這個 cycle 你 spawn 一個 sonnet」）
- **無例外**：spike batch / 大型 cycle / mechanical work 等都**不**自動 spawn——這些情境的判斷成本由 orchestrator 承擔、不轉嫁

orchestrator 不可自行決定「這個 cycle 量太大、spawn Sonnet 比較快」；違反 hybrid mode 約束。如 cycle 過大 orchestrator 可拆分多 cycle（task.md cycle plan 動態調整規則）、不轉用 subprocess。

### checklist 對齊

`checklist.md` R1 / R3 段落寫成「呼叫 Executor」是模板殘留；hybrid mode 下 R1 / R3 解讀為「orchestrator 內聯完成」、`state.md ## Sessions` Executor 欄位寫「（由 orchestrator 直接做）」。R2 段落保留 spawn 流程不變。

---

## 啟動流程

### 1. 建立工作目錄

- 確認 `{workspace}` 和 `AutoWorkspace/task.md` 存在
- 建立 `AutoWorkspace/log/`

### 2. 審計 `task.md`

對照 `{framework}/task.template.md` 檢查 `AutoWorkspace/task.md`：
1. 驗證 `task.md` 內容無失真
2. 若 `task.md ## Runtime 行為指令` 為空，推斷並補足：
    - 有 test script → `{test_command} --verbose 2>&1 | tail -50`
    - 有 HTTP server → `curl -s localhost:{port}/health`
    - 有 CLI entry → 用 sample input 執行並擷取輸出
    - 有 log 檔案 → `tail -20 {log_path}`
    - 完全無法推斷 → 跳過
3. 若 `task.md ## 模型` 有指定，記錄各角色的模型，供 checklist 呼叫時使用

有問題 → 向使用者提出修正建議。

### 3. 生成 `AutoWorkspace/audit.md`

```markdown
# Cycle 目標：
## R2 驗收：
### Code Review
## 指令：無
```

### 4. 生成 `AutoWorkspace/devlog.md`

```markdown
## Commit：
## 指令：無
```

### 5. 生成 `AutoWorkspace/state.md`

```markdown
## Resume hint
你是 Asterism Orchestrator。auto-compact 後讀本檔 + task.md → 從 ## Step 對應 round 繼續執行 checklist.md。

## Step
C{N} R{M} <role>

## Sessions
Auditor：{session_id}
Executor：{session_id}

## Phase progress
P{n}.{milestone}：{進度描述}

## Blockers
{無、或卡住的項目 + 原因 + 等待 user 介入}

## Summary
```

### 6. 進入 Cycle

1. 根據環境選擇生成隨機 `{UUID}` 的指令：
    - Linux/Mac: `{UUID}=$(cat /proc/sys/kernel/random/uuid)`
    - Windows(PowerShell): `{UUID}=$(powershell -Command "[System.Guid]::NewGuid().ToString()")`
    - Python: `{UUID}=$(python -c "import uuid; print(uuid.uuid4())")`
2. 閱讀 `{framework}/checklist.md`
    - 從 `C1` 開始計數
    - 從 `Cycle 起點` 開始執行
