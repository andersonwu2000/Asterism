# Phase 2 — Decomposition

## 目標

接上 P1 的 Builder skeleton，引入第一個 agent pipeline `Backward`：把一個 Goal 拆成 sub-Goals + 新 Strategy，並讓 cascade 能沿 AND/OR graph 往下鋪展、再往上回收 `proved`。
Phase 結束時，框架對一個無 leaf-Strategy 預先寫好的 Goal，能自動拆解、寫 sub-Goals、各自 Builder 證明、cascade 上去到 root `proved`。
**第一次接 LLM agent**：claude CLI subprocess、`--add-dir` 限範圍、staging-only 寫入、agent 輸出 validator。

## Scope

### In

- **Agent stage runtime（Provider 抽象）**（架 §8.3、impl §6.5）
  - `Provider.invoke(model_tier, prompt, scope_dirs, session_id) → AgentResponse` 介面
  - **P2 只實作 claude provider**；gemini / codex 留 P5 備援
  - `claude --add-dir` 限定 agent 可見路徑為「Problem 目錄 + 該 pipeline 的 staging dir」
  - agent 結束後驗「除 staging 外無檔案被改」（git status 等價，per-provider 統一兜底）
  - session 管理（claude jsonl；介面預留給 gemini / codex 不同 session 機制；pipeline 結束即 GC）
  - prompt 模板系統（`docs/prompts/<stage>.md` 一份 prompt 三家共吃 + context interpolation）
- **Model 解析機制**（架 §8.3 三層覆寫的低兩層）
  - 框架預設 `agent.model_defaults`：P2 啟用兩個 entry——`builder.tactic_llm: haiku`、`backward.agent: sonnet`
  - Problem META.md `models?:` 覆寫：解析機制 P2 上、Strategist override 留 P7
- Backward pipeline 完整 stage 序列（pipelines.md §2）：`failure_replay` → `find_lemmas`（stub）→ `find_subgoals`（stub）→ agent → `dedupe (local)`（簡化版，純 statement_hash 比對）→ validator → `self_verify (multi)` → commit
- Backward agent prompt v1（落 `docs/prompts/backward.md`）：給 Goal、給 dead_attempts 摘要、要求輸出 PROPOSAL（combinator + sub-Goals + leaf claim 清單）
- Validator（`Tooling/validator.py`）：
  - hypothesis carry 走 Lean meta（`tools/validator.lean`，CLI 對齊 impl §4.2）
  - slug collision 查 SQL UNIQUE
  - sub-Goal 數量 ≤ `validator.max_subgoals`（§Config）
- self_verify stage 抽出獨立（P1 內嵌於 tactic_try、P2 拆出來）；single mode（驗單檔，Builder.tactic_llm 用）+ multi mode（lake build staging dir，Backward 用）
- commit 多 row：INSERT 多個 sub-Goals + INSERT strategy + INSERT strategy_subgoals + mv 多檔，全在一個 `begin_batch` TX
- Reactor 升級：從 P1 single-task exit 模式 → 進入 daemon mode：
  - Block 在 event_bus，無新 event 時 30s tick 喚醒跑 structural refill
  - 真實的 atomic pool（cap=`P`，預設 4，threading 或 multiprocessing）
  - **Reactor 對 4 種 event kind 分流**（v3 §6 events 表）——非「6 step 順跑 + 第 7 步 control_signal」結構，而是 event handler dispatch：
    - `pipeline_finished` → 走 6-step cycle（cascade / refill / spawn）；P2 簡化只跑 step 2/3/4/6（step 1 stale 過濾留 P3、step 5 Strategist 觸發留 P7、P3 補空 hook 預鋪結構）
    - `control_signal` → 獨立 handler：
      - `pause`：停派新 pipeline、現有 pipeline 自然結束
      - `resume`：恢復派
      - `shutdown`：SIGTERM all running pipelines → wait 5s → SIGKILL fallback → scheduler exit
      - `set_budget` / scope 細粒度控制留 P7
    - `fatal` → halt（沿用 P1 機制）
    - `task_checkpoint` → P5 才有 handler（P2 收到視為 stale event 丟棄）
- Structural refill 簡化版：BFS goals table、`status='open'` 的 Goal enqueue Backward、全 sub-Goal proved 的 Strategy enqueue Builder、`kind=conjecture/construction` 的 kind-dispatch 留 P4/P5
- **P2 stop-gap：per-(Goal, pipeline_kind) hard-coded retry cap**——P1 用 hard-coded enqueue（人類 add 才 enqueue）隱含防止 exhausted Goal 無限重派；P2 引入 BFS structural refill 後此防線消失，BFS 每 cycle 都會撈到 exhausted Goal 再 enqueue。**P2 補 in-memory 計數**：reactor 維護 `dict[(goal_id, pipeline_kind), failure_count]`，達 `N_block_after_failures=5` 後 BFS 跳過。**正式 `goals.blocked_pipelines` 機制留 P3**——in-memory 版本 scheduler 重啟即重置（接受 P2 期間 restart 後對 stuck Goal 重試一輪，P3 持久化解決）
- Cascade 規則（v3 §6 step 3）：
  - Builder 鏈成功 → strategies.succeeded、父 Goal proved（trust_set 用 #print axioms 構造）
  - Strategy dead → 父 Goal 視 Strategy 數量決定 open / shelved（簡單 fallback：所有 Strategy dead 就 shelved）
  - Cascade upward propagation 鏈（v3 §6 cascade upward 段）：sub-Goal proved → 下個 cycle structural refill 偵測「Strategy 全 sub-Goal proved」→ enqueue Builder for that Strategy
- depth 欄位 + `D_max[theorem]=12` 兜底（structural refill 時 depth ≥ 12 直接 UPDATE shelved）
- Trust set 構造（impl §5.2）：cascade 把 Goal 翻 proved 前對 root theorem 跑 `lake env lean -e '#print axioms <thm>'`、parse axiom names → `trust_set` 列 lean_axiom entries
- Accept rule（impl §5.3）只啟用 `status='proved' / type='classical'`：trust_set 全 entry kind='lean_axiom' AND name ∈ Problem.axioms
- META.md axiom 解析（impl §5.0 minimal）：YAML frontmatter parser、`axioms` 欄位強制
  - **Accept rule 首次啟用**：cascade verdict 構造 trust_set 後比對；`allowed_axioms` 取自 META.md 的 `Problem.axioms`（impl §5.3）。**P1 trust_set 留 NULL、無 accept rule**——P2 首次跑 #print axioms + 檢查 ⊆ Problem.axioms
- Cancellation propagation 簡化版：cascade 觸發 Goal proved → SIGTERM 同 Goal still-running 的 Backward / Builder（**「同 Goal」= `target_id == G.id` 的 pipeline**；P4 才有 twin pipeline 需要走 twin_of 跨 Goal cancel）。白名單寫死「殺所有」，留待 P4 升級成 verdict-aware 正向白名單

### Out

- **`Backward.failure_replay` 接真實 dead_attempts 摘要**——P2 用 stub 回 empty；Builder.failure_replay P2 接真實（K_digest=5）。dead_attempts table 仍 INSERT、Backward 端真實接入留 P3
- `find_lemmas` / `find_subgoals` 接真實 search（P2 stub 回 empty list；agent 純靠語料知識想 lemma）
- Search / Dedupe subsystem（P3）；P2 dedupe 走最簡單的 SQL `WHERE statement_hash = ?` 比對。**`statement_hash` = normalized text 的 SHA256**（whitespace 規格化、無 token-level 處理），**不蓋 α-equivalence**——`fun n => n+0` vs `fun m => m+0` 算 collision miss。Demo theorem 必須選簡單到不會踩 α-equivalence 的 case；α 等價的不同表達式由 P3 dedupe.lean (Lean.Meta.isDefEq) 接手
- Cache（P4）
- IH-trap 偵測（`parent_subgoal_max_similarity` 計算放 P3）
- `blocked_pipelines` 自動寫入（P3）
- Strategist（P3 起逐步加）
- Refuter / Counterexample / Forward / ConstructionSearch / Generalizer
- Multi-Problem
- Library promotion
- Trust set 內 `kind=computational`（P4 conjecture 才有）

## Demo

**P2 起 `asterism run` 預設 daemon 模式**（P1 預設 `--once`）。`--once` 仍可用作 single-shot。後續 phase 一律假設 daemon。

```bash
asterism init --problem sg
# 產 Problems/sg/{
#   META.md           # 三公理（強制宣告）
#   Defs.lean         # 範本：import Mathlib + 留空（user 自加 Sylvester–Gallai 用定義）
#   Root.lean         # 範本：import Problems.sg.Defs + 留空（Library promotion 寫入點，P6 才動）
# }

# 注入一個需要拆解的 root theorem
# demo 用：Nat.add_comm 從零證 by induction，或 sylvester_gallai L0001 之類能 demo 範圍的
asterism goal add \
  --problem sg \
  --slug add_comm_demo \
  --kind theorem \
  --spec "∀ m n : Nat, m + n = n + m"
# --spec 是統一介面（P2 起；P5 加 construction kind 接 .lean 檔路徑）
# 框架自動產 Problems/sg/Goals/<G_id>_add_comm_demo/add_comm_demo.lean
# 內容範本：
#   import Problems.sg.Defs                    -- Defs.lean 自身 import Mathlib，讓所有 Goal 共享 import
#   theorem add_comm_demo : ∀ m n : Nat, m + n = n + m := by sorry
# leaf-strategy 由後續 Backward 產，user 不提供——取代 P1 的 --leaf-strategy flag
# Root.lean 不動（P6 Library promotion 才寫入）

asterism run        # P2 起預設 --daemon
# 預期：
#   Backward(G_root) 跑 → 拆出 G_base, G_step
#   Backward(G_base) 跑 → 寫 leaf strategy（無 sub-Goal）
#   Backward(G_step) 跑 → 寫 leaf strategy
#   Builder(G_base.S) → proved
#   Builder(G_step.S) → proved
#   cascade up → G_root.S succeeded → G_root proved
#   reactor 進 idle tick

asterism goal show G_root
# 預期：status=proved, answer_data={"type":"classical",...}
#       trust_set=[{"name":"propext","kind":"lean_axiom",...}, ...]
#       depth chain 完整
```

## Acceptance criteria

0. **Demo bash 一條龍 pass**——上面 §Demo 整段 bash 從 `init` 到 `goal show` 跑完、最後 status=proved + trust_set 非空。**這是 phase 完成的 single sanity gate**
1. **Agent 範圍隔離**：Backward agent 嘗試在 staging 之外寫檔（pytest fixture 故意做 evil agent prompt）→ runtime 偵測 + 該 stage failed → retry → 上限後 outcome=`exhausted`
2a. **拆解端到端（warm cache）**：CI 重複跑 demo theorem，wall-clock < 5 min（Mathlib 已 build、claude session 重用）
2b. **拆解端到端（cold cache）**：清 lake cache + 清 ~/.claude/* → demo wall-clock < 20 min（含首次 Mathlib build）
3. **Cascade upward**：手動構造 sub-Goal proved 但父 Strategy 還沒 success 的狀態 → 下個 reactor cycle 在 30s tick 內偵測 + enqueue Builder for parent Strategy
4. **Multi-row commit TX**：用 `COMMIT_FAULT=after_step1`（P1 hook，作用於 begin_batch）打斷 Backward commit → recovery scan 把所有相關 sub-Goals + strategy + strategy_subgoals 一致還原到 pre-commit 狀態（沒有半個 INSERT、半個沒）
5. **Validator hypothesis carry**：Backward agent 寫 sub-Goal 缺父 Goal 的某個 hypothesis binder → validator reject + retry from agent stage
6. **Trust set 構造**：proved root 的 `trust_set` 內 entry 名字跟 `lake env lean -e '#print axioms ...'` 輸出一致
7. **Accept rule reject**：人為改 Problem META.md 把 `Classical.choice` 拿掉 → 對需用 choice 的 demo theorem cascade verdict reject、Goal 仍 attempting、寫 dead_attempts、emit pause control_signal（manual unhang 後可繼續）
8. **D_max 兜底**：人為注入一個會無限拆的 Goal → depth 達 12 時 structural refill 階段直接 UPDATE shelved，不再派 Backward
9. **daemon idle**：reactor 沒事做時 CPU 接近 0（block 在 event_bus 不 busy poll）、30s 內回應新 control_signal
10. **Model 解析（框架預設 + META.md 兩層）**：手動在 META.md 寫 `models: { backward.agent: opus }` → Backward 跑時實際呼叫 claude 的 opus model id（驗 subprocess argv）；無宣告 → 用框架預設 sonnet。**Strategist override（第三層）留 P7**——P2 只啟用低兩層
11. **Stop-gap retry cap**：人為注入一個 Backward 必 exhausted 的 Goal → 連 5 次 exhausted 後 BFS 不再 enqueue 該 Goal 的 Backward；scheduler 重啟後 in-memory 計數重置、再次嘗試一輪（P3 持久化版接手後消失）

## 依賴

### 前置 phase

- P1 完成（Lake harness、commit 協議、Builder、Reactor 雛型、CLI）

### 必跑 spike

- **spike-004 claude CLI `--add-dir` 行為**——`claude --add-dir <path1> --add-dir <path2>` 是否真的把 agent fs 視野限制成 union？對外 read 也擋嗎？影響 agent 隔離手段
- **spike-005 Lean.Elab 抽 binder list**——對 P2 用的 demo theorem，`Lean.Elab.Frontend` 抽出來的 binder list 是否符合驗證需求（vs 人類眼裡的 hypothesis）？影響 validator 設計
- **spike-006 lake env lean 並發實壓**——同時跑 4 個 lake build 是否撞 cache lock 或彼此干擾？P1 spike-001 是輕量試，P2 是真實壓力
- **spike-007 claude CLI prompt token 上限**——Backward prompt 含 dead_attempts 摘要 + Goal statement + Defs.lean + Mathlib hints，估算 token 量級。決定 prompt 模板的精簡程度

## 引入元件

### Pipeline

- **Backward**：完整 stage 序列（pipelines.md §2），但 `failure_replay` / `find_lemmas` / `find_subgoals` 三個 pure stage 用 stub
- **Builder 升級**：加 `failure_replay`（接真實 dead_attempts，但 K_digest=5 有限制）+ `find_lemmas`（stub）+ `tactic_llm`（agent，輸出 a/b/c 三選一：tactic proof / needs_decomposition / bad_goal）

### DB table（啟用 P1 預留欄位）

P1 schema 已一次列 v3 §9.1 全欄位、未用欄位 nullable（codex review #12 決策）。**P2 不擴 schema**——只是開始消費以下原本 nullable 留空的欄位：

- `goals`：開始寫入 `depth` / `twin_of`（P4 才真實雙向、P2 留 NULL 即可）/ `derived_from`（P5 才寫、P2 留 NULL）/ `status_changed_at` / `trust_set`
- `strategies`：`parent_subgoal_max_similarity` 仍 NULL，P3 接手（無新欄位寫入；session 是 pipeline-level transient state、掛 `pipelines` table）
- `pipelines`：開始寫入 `session_id`

### Config

新增：

| key | P2 預設 |
|---|---|
| `P` (atomic pool) | 4 |
| `K_digest` | 5 |
| `D_max[theorem]` | 12 |
| `N_retry` | 10（P1 schema 預留、P2 真實啟用——agent stage 失敗 retry 上限） |
| `T_wall` | 30 min（P1 已有，P2 沿用） |
| `agent.providers` | `[claude]`（P5 起加 gemini / codex） |
| `agent.fallback_chain` | `[claude]`（single-entry list，retry 後直接 outcome=exhausted；P5 延伸成多 entry） |
| `agent.model_defaults.builder.tactic_llm` | haiku |
| `agent.model_defaults.backward.agent` | sonnet |
| `claude` CLI 路徑 + base flags | 從 env / config |
| reactor idle tick | 30s |
| `N_block_after_failures` | 5（P2 用 in-memory；P3 改為 `goals.blocked_pipelines` 持久化） |
| `validator.max_subgoals` | 8（經驗值，避免 agent 過度拆解；正式作為 invariant 留 P3+ 視 Hadamard 經驗調） |

### Stage 實作

- `agent` (Backward) — 對齊 pipelines.md §2 step 4，透過 Provider 抽象呼叫
- `agent` (Builder.tactic_llm) — 對齊 pipelines.md §1 step 4，透過 Provider 抽象呼叫
- `validator` — 呼 `tools/validator.lean` + 整合 SQL UNIQUE check

### Provider 介面預留

`Tooling/agent/provider.py` 抽象基類 + `Tooling/agent/providers/claude.py` 唯一實作。fallback chain 機制 P2 single-entry list `[claude]`（retry 後直接 outcome=exhausted、無 fallback 切換）；P5 加 gemini / codex 延伸成多 entry。

### Agent prompt 落地

- `docs/prompts/builder_tactic_llm.md`
- `docs/prompts/backward.md`

兩個 prompt P2 暫時都先用「夠用」的版本，P7 Strategist 升級時可能會回來重寫。

### 新增 Tooling 檔

```
Tooling/
├── lake.py              # P1
├── commit.py            # P1
├── scheduler.py         # P1, P2 升級成 daemon
├── agent/
│   ├── provider.py      # P2 新（Provider 抽象基類 + 兩層 model 解析；Strategist 第三層留 P7）
│   └── providers/
│       └── claude.py    # P2 新（唯一實作；gemini.py / codex.py 留 P5）
├── pipelines/
│   ├── builder.py       # P1, P2 加 agent stage
│   └── backward.py      # P2 新
├── stages/
│   ├── agent.py         # P2 新（呼 Provider + prompt template + scope 兜底驗）
│   ├── self_verify.py   # P2 新（P1 在 tactic_try 內嵌 lake 驗、無獨立 stage）；P2 抽獨立 stage 含 single + multi mode
│   ├── validator.py     # P2 新
│   ├── failure_replay.py # P2 stub
│   └── ...
├── trust.py             # P2 新（#print axioms 解析）
├── meta.py              # P2 新（META.md 解析含 axioms + models?）
└── cli.py               # P1, P2 加 daemon mode
```

## 任務序列

DB 端 P2 不需 schema migration（P1 已建全 schema、§引入元件 §DB table 段已說明），任務序列只列實作動作：

1. **spike-004 / 005 / 006 / 007 跑完**——結果落 `docs/spikes.md`，特別 spike-004 影響 agent 隔離設計
2. **Provider 抽象 + claude 實作**（`Tooling/agent/provider.py` + `Tooling/agent/providers/claude.py`）：
   - 介面對齊 impl §6.5
   - claude provider：`--add-dir` 限制、結束後 git status 兜底、jsonl session GC
   - 兩層 model 解析（框架預設 + Problem META.md；Strategist override 第三層留 P7）
   - fallback chain 機制 P2 single-entry list，P5 延伸成多 entry
3. **`tools/validator.lean`**：對齊 impl §4.2 介面
4. **Validator Python 端**（`Tooling/stages/validator.py`）：呼 validator.lean + SQL UNIQUE + `validator.max_subgoals` check
5. **META.md parser**（`Tooling/meta.py`）：YAML frontmatter、`axioms` 強制、`models?` 選擇性
6. **Trust set 構造**（`Tooling/trust.py`）：`#print axioms` subprocess 包裝、parse、accept rule
7. **Backward pipeline runtime**（`Tooling/pipelines/backward.py`）：完整 stage 序列、commit batch
8. **Builder agent 升級**（`Tooling/pipelines/builder.py`）：tactic_llm agent stage 接上 + Builder.failure_replay 接真實 dead_attempts
9. **Reactor 升級**（`Tooling/scheduler.py`）：
   - Daemon mode：event_bus block + 30s idle tick
   - Atomic pool（threading.ThreadPoolExecutor 或 multiprocessing）
   - **Event kind dispatch**（4 種 event：pipeline_finished / control_signal / fatal / task_checkpoint）：
     - pipeline_finished → 6-step cycle（P2 簡化跑 step 2/3/4/6）
     - control_signal → 獨立 handler（pause/resume/shutdown）
     - fatal → halt（沿用 P1）
     - task_checkpoint → P5 接 handler、P2 視為 stale 丟棄
   - structural refill BFS（簡化：先做 theorem-only dispatch）
   - cascade rules 模組化（為 P4 改成 dispatch 表預鋪路）
10. **Cancellation 簡化版**：cascade 觸發 Goal proved 時 SIGTERM `target_id == G.id` 的 still-running pipeline
11. **In-memory retry cap stop-gap**：reactor 維護 `failure_count: dict[(goal_id, pipeline_kind), int]`、structural refill BFS 撈到 Goal 前查、達 `N_block_after_failures=5` 跳過；pipeline 結束 outcome ∈ {exhausted, unproductive} → 計數 +1。in-memory only、scheduler 重啟即重置（P3 改 `goals.blocked_pipelines` 持久化後此檔刪掉）
12. **CLI**：`asterism run --daemon`（P2 起預設 daemon、`--once` 仍可用 forward-compat）、`asterism stop`（emit `control_signal(action=shutdown)` 走 reactor、不直接 SIGTERM 主 process——對齊 v3 §6 event model）
13. **Demo theorem 跑通 + acceptance test 寫成 pytest**

## 測試

- **Unit**：claude subprocess 模擬（mock claude binary 回傳 fixture）的 agent stage 行為
- **Unit (evil agent)**：fixture 用「無限 evil」mock（每次 retry 都回相同 evil response、嘗試在 staging 外寫檔）→ retry 必然燒到 `N_retry=10` 上限 outcome=`exhausted`。**重點**：驗 isolation + retry + exhaustion 三條路徑全 wired 對；evil prompt 不會收斂是設計，不是 bug
- **Unit**：validator 對 hypothesis carry pass / fail 各 case
- **Unit**：trust_set parse 對單 axiom / 多 axiom / 空（trivial proof）case
- **Integration**：demo theorem end-to-end pytest
- **Integration**：拒絕 axiom 場景（Problem.axioms 不含 Classical.choice，theorem 用了 → reject + pause）
- **Integration (stop-gap restart)**：fixture-controlled scheduler subprocess——inject 永久 exhaust 的 Goal、跑 5 個 BFS cycle、驗第 6 cycle 不 enqueue 該 Goal；SIGTERM scheduler、重啟、驗第 1 cycle 又 enqueue 一次（重置語意確認）
- **Stress**：4 個並發 Backward 各跑 30s 量級，觀察 lake cache 撞鎖頻率
- **Manual**：daemon mode 運行 1 小時，無 leak / 無僵屍 subprocess

## 風險與 open questions

- **claude CLI 穩定性**：spike-004 結果若顯示 `--add-dir` 隔離不夠強，要 fallback 到「先 git stash → run agent → check git status → unstash」這條更慢但更穩的路。會影響 agent stage 設計
- **Backward agent 寫不出有用 sub-Goal**：P2 沒 search subsystem，agent 只能靠語料知識。對 Mathlib 內常見定理可能 OK，對小眾命題可能滿目 hallucinate。Demo theorem 選什麼很關鍵——選太難 demo 失敗、選太簡單 P2 沒驗證到 cascade
- **Cascade upward 30s tick 延遲**：純靠 idle tick 觸發 + 每往上一層 = 一次 Builder lake build 時間（v3 §6 cascade upward 段）。**估算**：demo theorem 拆解層數 N → 約 N×30s tick 純空等（5 層 ≈ 2.5 min wait、佔 20 min budget ~12%）；20 min budget 對 N≤6 安全、深 graph 需重估。P3 引入 event-driven enqueue 可能改善
- **依賴的 Mathlib lemma 未證 → Builder exhausted**：Demo theorem 若拆出來的 sub-Goal 需要 Mathlib import 但沒被 Defs.lean 拉進來 → Builder 一直 type-check fail。需要明確 demo theorem 的 import 範本
- **Subprocess pool on Windows**：threading.ThreadPoolExecutor 跑 subprocess 在 Windows 上 GC / file handle 行為跟 Linux 不同，可能 leak。P2 開工首日驗
- **In-memory retry cap 的 trade-off**：scheduler 重啟即重置 → 若 P2 開發期 daemon 經常重啟（debug / config tweak），同個 stuck Goal 每次都會再撞 N=5 次失敗才被擋。P3 持久化後消失，但 P2 期間要接受。應變：CLI `asterism goal block <G_id> <pipeline_kind>` 手動標記、scheduler 啟動時讀取（可選未來機制）
