# LSP Integration — 把拆解的決策權還給 agent、解鎖即時協作

狀態：設計討論中。架構與決策點待 user 拍板後進實作 phase。

技術細節（process tree、RAM 數字、tool 詳細參數、JSON-RPC、PoC 數據）見
[`lsp_integration_tech.md`](lsp_integration_tech.md)。本檔只談概念與決策。

---

## 目錄

1. [動機](#1-動機)
2. [為什麼這樣設計](#2-為什麼這樣設計)
3. [整體架構](#3-整體架構)
4. [心智模型](#4-心智模型)
5. [過渡與風險](#5-過渡與風險)
6. [開放決策點](#6-開放決策點)

---

## 1 動機

當前 Asterism 的 and/or-graph 架構（goal tree、Backward 拆解、Verify
chain、dedupe、library promotion）並不是「人怎麼證明數學」的對應、而是
**「`lake build` 只能 per-file 給回饋」的反向工程結果**。

framework 用 `lake build` 拿不到 incremental feedback、所以被迫：
- 把每條引理切成獨立 `L_*.lean`（lake 認得的最小 build unit）
- 用 attempt-by-attempt 模型（一次 spawn = 一次 build = 一次 dead_attempt）
- 用 forensic 紀錄 stderr 給下次 spawn 看（agent 沒法在 session 內收回饋）
- **預先**用 Backward planner 設計 sub-goal 樹、agent 後續只能填空、不能改
  statement

PoC（`spike/`、2026-05-07）證明 LSP 可以提供 sub-second edit feedback、完整
goal 與 error 資訊在 session 內暴露給 agent。

**結論**：and/or-graph 是 build feedback 限制的補丁。LSP 拿掉限制、補丁退場、
**拆解的決策權還給 agent**——但拆解本身不消失、改由 agent 在探索過程中自決
時機與粒度。

---

## 2 為什麼這樣設計

### 2.1 lake build 的限制

- 粒度：per-file
- 時機：build 跑完才有錯誤訊息
- 內容：stderr 文字、agent 看不到 goal state

forces：proof 必須拆成一檔一條 lemma；agent 寫完一次就 exit；agent 看不到
goal、只能從 type signature 推測。

### 2.2 人類數學家怎麼處理大規模證明

樣本：Liquid Tensor Experiment、mathlib perfectoid、有限單群分類、Hadamard
證 Monsky、FLT。共同模式：

1. **Statement-first decomposition**：頂級數學家先寫 sketch、把證明拆成 N 個
   proposition、固定 statement、後填 proof
2. **多人 / 多 session 平行**：不同人挑不同 lemma 各自寫、同步點是 statement
3. **Statement 會修**：寫到一半發現原 statement 不對、回頭改、依賴的 proof
   重 elaborate
4. **拆解是 discovered**：寫到一半發現某段邏輯重複、抽 lemma、新檔誕生；
   遞迴、隨時、自決
5. **Library 自然累積**：今天的 helper 是明天的 tool、emergent
6. **重構是日常**：抽共同 / generalize / 改名 / 簡化、不是事後 cleanup phase

新架構要把這六點當 first-class、不是邊角功能。

### 2.3 LSP 解鎖了什麼

| 解鎖 | 對應人類做法 |
|---|---|
| Statement 可動、依賴自動 re-elab | 2.2.3 |
| 拆解時機自由、遞迴 | 2.2.4 |
| 自頂向下 + 自底向上同時推進 | 2.2.1 + 2.2.4 |
| Library emergent、agent 明示 promote | 2.2.5 |
| 多 agent 即時收斂（共用 LSP ground truth） | 2.2.2 |
| 重構是日常 first-class | 2.2.6 |

### 2.4 FLT 對照與啟示

Imperial College London 的 Fermat's Last Theorem 形式化（1500+ commits、
多人協作、Kevin Buzzard 領導）是大型 Lean 形式化的成熟參考。其架構驗證了我們
新模型的多個假設、也指出一個關鍵缺漏。

| FLT | Asterism 對應 |
|---|---|
| Blueprint LaTeX + annotations | Manifest 薄 + Lean 檔頭 metadata 無 |
| `\lean{name}` link | Lean import 隱含 |
| `\leanok` 狀態 | sorry count = 0 |
| Dependency graph | **待新增**（決策點 11） |
| GitHub issues | work queue items |
| claim / disclaim | file-level lock |
| **Buzzard 寫 blueprint** | **缺漏 — Architect role** |
| 多人 prove | Prover role |

#### 五個關鍵啟示

1. **Architect 是獨立 role、不是 Prover 的 mode**
   FLT 的 Buzzard 寫整個 blueprint（拆解、設計 statement、依賴關係）、
   不證任何東西。這跟 Prover 是完全不同的工作流——大腦模式（planning vs
   executing）、輸出（架構 vs proof body）、成功標準（架構穩定 vs sorry 收）
   全不同。
2. **Blueprint 是 first-class artifact**
   依賴聲明 + status 標記 + math text 顯式化、能自動生成依賴圖。
   隱含在 Lean 代碼裡推不出 math intent。
3. **Dependency graph 是 progress 視覺化的核心**
   problem 有 50 個 helper 時、file tree 看不出結構。
4. **Top-down 拆解在 scale 上是必要的**
   FLT 14 chapters / 9 miniprojects / 數百 lemmas、沒 Architect 預先拆好、
   無法管 1500 commits。深題（Monsky / SG）必走 Architect、小題可跳過。
5. **手動 coordination 即使有 bots 也是必要的**
   FLT dashboard 是 maintainer 手推、不是 FIFO 自動。dispatcher 不只是
   work queue puller、要做 priority / role assignment / give_up 重排等仲裁。

---

## 3 整體架構

### 3.1 主迴圈轉變

舊：
```
while True:
    work_item = pick_next(db_state)              # goal × strategy × pipeline_kind
    spawn_claude_session(work_item, role_prompt) # builder / backward / reflection
    record_outcome(session_id, exit_reason)      # cascade 規則跑、更新 goal lifecycle
```

新：
```
while True:
    work_item = pick_next(work_queue)            # problem × role × target × hints
    session = spawn_claude_session(work_item, role_prompt)
    consume_session_events(session)              # 邊跑邊收事件
    record_outcome(session.id, session.events, session.final_state)
    update_work_queue(events)                    # 事件衍生新 work items
```

差異：
1. **work item 形狀**：「goal × strategy」→「problem × role × target」
2. **事件流**：session 進行中收 events（sorry 變、signature 改、helper 創建）、
   不只看 exit
3. **事件驅動 work queue**：cascade 不是固定規則、是事件衍生新 items

主迴圈結構保留、責任擴張到「session 進行中持續跟 LSP server 同步」。

### 3.2 Role 集合（disciplined）

舊 pipeline kind：Builder / Backward / Reflection。

新 role 嚴格收斂、只承認**有實質 prompt 差異 + 工作流結構不同**的才算 role。
Reflection 不是獨立 role、是每個 role session 結束時的 step。

兩個核心 role + 一個可選 role。FLT 對照（§2.4）佐證 Architect / Prover 必須
分開——Buzzard 寫 blueprint vs contributors 填證明、是兩種完全不同的工作。

#### 3.2.1 核心 role：Architect

對應 FLT 的 Buzzard 角色。**寫結構、不證**。

- **輸入**：work item with `target = problem`、context_hint =「new problem」/
  「architecture needs revision」
- **目標**：產生 / 更新 file tree 結構 + 各 declaration 的 statement +
  依賴關係
- **典型動作**：讀 Manifest、create_file 多個 stub helper、Main.lean 用
  sorry 串起來、改現有 helper 簽名
- **不做**：proof body（除了 trivial 一行）、tactic 細節
- **退出條件**：架構 stable + 各 helper signature 通過 elaborate（即 sorry
  都還在但 type check 過）/ 預算耗

對小題（PN 級）可跳過 Architect、Prover 自帶輕度 sketch。對中大題
（cantor / SG / Monsky）必走 Architect。

#### 3.2.2 核心 role：Prover

填 sorry。涵蓋大部分執行工作。

- **輸入**：work item with `target_file` + `context_hint`
- **目標**：減少 target（或衍生檔）的 sorry / error
- **典型動作**：看 goal、寫 tactic、看 error、修；inline `have`；抽出新
  helper（中尺度自拆）；改 helper signature；inline 一個 helper 回 main；
  generalize / 改名 / 簡化
- **退出條件**：target sorry → 0 / partial 但 budget 耗 / agent give-up

Prover 跟 Architect 的界線：**signature change 的範圍**。Prover 改的
signature 通常局部（自己抽出的 helper）。如果發現需要動 Architect 預先設計的
statement、應該標記、給 framework 決定要不要回 Architect 重整。

#### 3.2.3 可選 role：Reviewer（決策點 6）

當 problem 多 session 沒進展、可能需要外部視角。

- **權限**：read-only、不給 edit tool
- **輸出**：critique 進 LESSONS、可能標 hint 給後續 role

是否設此 role 是決策點。可視為 Prover read-only mode、不另設。

#### 3.2.4 不是 role 的東西

- **Reflection**：每 role session 結束時的責任、不是獨立 role
- **Library-Promoter**：framework 函式 + Prover 明示 promote 混合
- **Verifier**：framework 跑 lake build 終驗、不需要 agent
- **Sketcher**：併入 Architect 或 Prover 的 sub-mode

### 3.3 Work queue 模型

work item：
```
WorkItem {
  problem_id: str
  role: 'architect' | 'prover' | 'reviewer'
  target: 'problem' | file_path | 'new_helper'
  context_hint: str
  budget: { wall_clock_s, token_max }
  predecessor_session_id?: str
}
```

舊 cascade 是 leaf→strategy→root 的單向上推、新 work queue 是**事件驅動的多
方向**。觸發新 work item 的事件：

| 事件 | 衍生 work item |
|---|---|
| 新 problem 加入（大題） | `(p, architect, problem)` 初始拆解 |
| 新 problem 加入（小題、決策點 12） | `(p, prover, Main.lean)` 直接 |
| Architect 結束、產生 N 個 stub helper | 每個 stub 一個 prover work item |
| Prover 結束、檔內仍有 sorry | 每個未收 sorry 一個 prover work item |
| Prover 創新 helper file with sorry | 對應 prover work item |
| Prover 改某 helper signature | 給每個受影響檔出 prover work item |
| Prover 改 Architect 設計的 statement | 標記、可能觸發 architect 重整 work item |
| Prover 同 sorry 連 N 次失敗 | reviewer work item（如啟用） |
| Prover give_up | sorry 進入「困難」標記、影響後續 priority |
| 跨題 lemma 重複出現 | framework 自動跑 library promote、不出 work item |
| 階段 milestone（root proved） | refactor_pass work item 整理檔結構 |

Work queue 排序不是 FIFO。需要考慮 problem priority、Architect 級事件 vs
細節 prove 事件、agent give_up 過的 work item 是否重排、predecessor session
接力時是否同 agent 接。具體演算法是決策點 5。

### 3.4 多 agent 同 problem 協作

#### 並行性

**同 problem 多 agent 同時跑、各自 edit 不同檔**。共用一台 `lake serve`、
各自一個 worker。同檔多 agent 編輯禁止（file-level lock）。

平行 granularity：active edit 檔數、不是 leaf 數。比舊 graph 更靈活——舊
graph 平行只發生在不同 leaf；新可發生在 main + helpers 同時推進。

#### 同步機制：Statement-as-contract

agent A 在 Main 寫 `have hX : <sig> := by sorry`、agent B 拿這條 sorry 去
helpers/hX.lean 試證、agent C 在 Main 假設 hX 繼續往下寫。

A 改 hX signature → framework broadcast 給 B C 的 worker → 立刻 re-elaborate
→ 看到 type error → B C 知道契約改了、決定 adapt 或 push back。

#### 衝突處理

- **同檔多 agent**：file-level lock 阻止
- **A 改 signature、B 已在用舊版本寫 proof**：B 的 worker 收 broadcast、
  re-elab 失敗、agent 看到 error 自決
- **A B 都試圖 promote 同名 helper**：framework 偵測、序列化處理

機制細節（broadcast 範圍、import 鏈掃描）見 tech doc §4。

### 3.5 取代 / 保留 / 打掉

#### 保留
- 主迴圈結構（while + pick + spawn + record）
- session = 預算單元
- claude_cli spawn / postmortem / quota_exhausted
- Manifest / BRIEF / LESSONS
- lake build 終驗

#### 取代（語意對應、實作重做）
- pipeline kind → role（數變少、但每個能做更多）
- goal_tree → file tree + sorry burndown
- attempts↔dead_attempts 1:1 → events stream
- cascade 規則 → event-driven work queue
- TREE.md → file tree + dependency graph + sorry burndown
- L_*.lean / _strategy_*.lean 命名 → agent 自定（helpers/ + Main.lean）

#### 打掉
- Backward planner（auto-decomposition 邏輯）
- dedupe / promote_to_alias 機械邏輯（agent 明示）
- strategy verification chain（沒 strategy 了）
- goal × strategy 二元 work item（變成 problem × role × target）

---

## 4 心智模型

### 4.1 File tree as state

problem 的 ground truth 是它的 .lean 檔案樹。framework state（DB）只是這棵樹
+ session 歷史 + work queue 的索引。

```
Problems/<p>/
├── library/              # 跨題穩定 lemma（被 promote 上來的）
├── helpers/              # 本題 helper（agent 隨時新增 / 改 / 刪）
└── Main.lean             # 主定理、import helpers/* + library/*
```

狀態變化（檔新增、sorry 減少、signature 改）就是 events。

### 4.2 Statement-as-contract

每個 declaration（theorem / lemma / def）的 signature 是契約。

- **proof body 改變**：local change、不影響其他檔
- **signature 改變**：契約變更、需 broadcast 給所有 user
- **新增 declaration with sorry**：契約定義、邀請其他 agent 來填

這是多 agent 協作的同步點、跟 git-merge 的 by-line 同步完全不同——
**LSP 在型別層級給保證、不是文字層級**。

### 4.3 Sorry burndown 取代 cascade

舊：goal lifecycle = pending / attempting / proved / failed / moot、cascade
規則決定何時轉哪個態。

新：每檔的 sorry count + 整 problem 的 sorry total 是進度量化。

- session 結束、檔 sorry 從 N 變 M、ΔN-M 是該 session 貢獻
- 跨 session 累積、繪成 burndown 線
- root proved = Main 0 sorry AND lake build 通過

不需要狀態機、只需要事件流 + 計數。

session outcome 5 種（取代舊 success/fail）：

| Outcome | 含義 |
|---|---|
| `root_proved` | 整題 done |
| `partial_progress` | sorry 數降了、未收完 |
| `no_progress` | sorry 數沒變 |
| `regression` | sorry 數變多（forensic 必標記） |
| `give_up` | agent 自評不適合、拒繼續 |

預算：session = wall-clock cap OR token cap OR sorry-budget。agent give_up
是有效結束、不算失敗。

---

## 5 過渡與風險

### 5.1 規模

不是 Phase 8、是 v3 級重寫。受影響面：

- `Tooling/pipeline/{builder,backward,_retry,_reflection}.py` — 重寫
- `Tooling/dispatcher.py` — work queue 模型重寫
- `Tooling/dedupe.py` `Tooling/library.py` `Tooling/verify.py` — 角色重評估
- `Tooling/db.py` — schema 大改
- `Tooling/agent.py` — tool surface 多 LSP 路徑
- `tests/*` — 大批重寫
- `docs/*` — 多份現有 design doc 過時

### 5.2 過渡策略

**並存方向**：保留 and/or-graph、加 LSP-driven 為平行 pipeline kind、
Manifest 標 `entry_mode: graph | lsp`。

順序：
1. PN / inner_zero 級小題用 lsp mode 跑通
2. cantor 級中題並跑驗證 scale
3. graph mode 確認劣勢後分階段砍

舊 graph data 在 lsp mode 不產生新資料、保留 read 能力供歷史 snapshot 與
cross-problem reuse。

### 5.3 主要風險

- **大檔 LSP 延遲**：Monsky-scale 1000+ LOC 是否仍 sub-second didChange？
  PoC 沒測。Phase 1 要驗 cantor / SG 級。
- **LLM 行為**：給了 InfoView 不見得用得好。empirical question、要真跑才知道。
- **Statement broadcast 成本**：改一個熱 helper、N 個 worker 要 re-elab、
  總共可能數分鐘、agent 卡。需要 dependency analysis 限制範圍。
- **多 agent 同題收斂失敗**：互改互廢、可能比單 agent 還慢。需要 coordinator
  仲裁機制。
- **forensic 資料爆量**：session 事件流 + sorry burndown 加起來不小、
  需要壓縮策略。
- **role 收斂太狠**：把所有東西塞進 Prover / Architect、prompt 可能太雜。
  Phase 1 跑出來再判斷要不要分裂 role。

---

## 6 開放決策點

依序討論、跟 Phase 7 模式一一鎖定。

| # | 決策點 | 選項 |
|---|---|---|
| 1 | Worker pool 上限與 eviction | 同時活躍 worker 上限 / LRU TTL 長度 / RAM 動態調 |
| 2 | Pre-warm 策略 | daemon startup 全預啟 / 只 next pipeline / lazy |
| 3 | Statement broadcast 範圍 | 全 import 鏈 / 1 hop / 標記不立刻 re-elab |
| 4 | 多 agent 同 problem 並行 | 預設開 / 預設關 / 按 problem size 自動 / 上限數 |
| 5 | Work queue 演算法 | FIFO / 進度排序 / agent 自選 / give_up 後處理 |
| 6 | Reviewer role 是否設立 | 設、做為 Prover read-only mode、不設 |
| 7 | Forensic 顆粒度 | edit trace 全錄 / interesting-moment / 只 session 邊界 / 混合 |
| 8 | Tool surface 形式 | MCP server / Bash subcommand / prompt raw RPC |
| 9 | Library promotion | agent 明示 / framework 自動偵測 / 兩者並存 |
| 10 | 過渡時程 | LSP path 何時取代 graph path、新 problem 默認哪個 mode |
| 11 | Blueprint / dependency 表達形式 | 從 Lean import 自動推 / Manifest+ 顯式段落 / 獨立 BLUEPRINT.md / 借鑒 leanblueprint LaTeX |
| 12 | Architect 觸發條件 | 每新題必跑 / 大於 N LOC 才跑 / agent 自評需要時申請 |
