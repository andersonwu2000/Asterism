# 架構 v3 — 推理結構

## 0. 範圍與配對文件

本文講 **WHAT / WHY**：模型、不變量、組件契約 + 跨 pipeline 的高層規則。

姊妹文件：

- `architecture_v3_pipelines.md`——五個 pipeline 各自的 stage 序列、outcome、行為規則
- `architecture_v3_impl.md`——演算法、SQL、API 簽名、效能常數、spike 結果、實作取捨

設計重點：

- AND/OR graph 推理結構（§1）
- Goal 帶 `kind` (theorem / conjecture / construction) × `status` + `answer_data` × `evidence` 表達狀態（§2）
- 8 種 pipeline，每 kind 自動結構性派發：conjecture 三線（Backward + Counterexample + Refuter）；construction 兩線（Backward + ConstructionSearch；Builder 隨 Strategy 自動 enqueue）（§5–§6）
- 兩種 runtime：atomic pipeline（短跑 + 兩段式 commit + crash 整條重跑）vs continuous task（長運行 + checkpoint + 可 pause/resume），各自獨立 pool（§5）
- DB 為 metadata 真相，commit 走兩段式協議統一 INSERT / UPDATE 並支援 crash recovery；continuous task 走 checkpoint 協議（§5）
- `trust_set` 統一表達 Goal answer 的依賴（lean_axiom 為主、computational 為 fallback）；Problem 與 Library 各自獨立 axiom whitelist（§7.1、§8）
- Evolution subsystem 共用基礎建設，服務 Counterexample（找反例）與 ConstructionSearch（找構造）（§4.3）
- 硬閘門：trust accept rule、agent 修改範圍、per-kind depth 上限、validator 走 Lean meta 禁 regex、IH-trap 結構相似度偵測（§7）

## 目錄

- §1 AND/OR graph
- §2 Goal
- §3 Stage
- §4 Subsystem
- §5 Pipeline（含 commit 協議 + checkpoint 協議 + Session 策略）
- §6 動態管線
- §7 硬閘門（含 trust_set + axiom whitelist 兩層獨立）
- §8 配置（框架 + per-Problem 兩層獨立）
- §9 Storage（DB schema + file layout）

## 1. AND/OR graph

推理結構是個 **AND/OR graph**（Nilsson 1971）。二分圖，兩種節點交替：

```
Goal     : 陳述  → Strategy  （一個 Goal 可有多個競爭中 Strategy）
Strategy : 解法  → Goal      （一個 Strategy 可有多個 sub-Goal）
```

語意：

```
Goal     = OR   ：任一 Strategy 成功 → Goal 成功
Strategy = AND  ：所有 sub-Goal 成功 → Strategy 成功
```

葉子 Strategy 沒有 sub-Goal——就是直接證明嘗試。

## 2. Goal

### 2.1 Status

```
open / attempting / proved / refuted / shelved
```

由 Strategy 推導 + twin cascade：

```
open          ←  Goal 存在但無任何 Strategy（含 Backward 跑完 outcome=exhausted/unproductive 但
                 沒成功 INSERT Strategy 的情境——Goal 仍 open，可被 structural refill 重派）
attempting    ←  ≥1 個 Strategy 還活著（status='proposed' 或 'in_progress'）
proved        ←  任一 Strategy 成功（status='succeeded'）
refuted       ←  twin Goal proved（cascade，需 twin_of ≠ null），或
                 Counterexample 直接 silver verdict
shelved       ←  所有 Strategy 死亡，且無 generator 願再生；或
                 §7.3 D_max 自動 shelve；或 Strategist 主動 Shelve
```

**狀態 transition 注意**：Backward 失敗（exhausted / unproductive）**不**改 Goal status——只 INSERT dead_attempts。Goal 從 open 變 attempting 唯一途徑是 Backward outcome=success（INSERT 至少一個 Strategy）。

### 2.2 Goal metadata

存於 DB `goals` table（schema 見 §9.1）。.lean 檔本身不帶 frontmatter，純 Lean code。

關鍵欄位：

| 欄位 | 用途 |
|---|---|
| `origin` | root / backward / forward / generalizer / refuter_negation / construction_witness。`root` 為使用者注入頂層 target（Library promotion 條件）；`generalizer` 為 Generalizer 從 proved Goal 推出的 generalization 候選；`construction_witness` 為 ConstructionSearch silver 後 spawn 的 `∃X, P(X)` 輔助 Goal |
| `kind` | theorem / conjecture / construction。決定 structural refill 派哪些 pipeline、accept rule 怎麼分流 |
| `question` | json nullable，kind-dependent 問題定義。theorem/conjecture：NULL（內容在 lean_path 的 statement）；**construction**：`{spec_lean_path, scorer_module, mutation_operators?}`——spec predicate 寫在 .lean 檔、scorer 是 Python module 路徑、可選 per-Goal mutation operator override |
| `status` | open / attempting / proved / refuted / shelved（§2.1 推導） |
| `answer_data` | json nullable，依 status 不同帶 verdict 細節（schema 見下） |
| `evidence` | json，free-form 累積（如 `counterexample_tested_up_to` / `refuter_attempts_failed`）。所有 pipeline 透過 evidence_update stage 寫入 |
| `twin_of` | Goal 間唯一直接邊。Refuter 建立 ¬G 時雙向設定 |
| `depth` | 樹根（origin ∈ {root, forward, refuter_negation}）= 0；Backward sub-Goal = parent.depth + 1。Strategist 監控、§7.3 D_max 用 |

**answer_data schema（依 status）**：

| status | answer_data shape | 用途 |
|---|---|---|
| `open` | NULL | 尚未開始攻 |
| `attempting` | NULL 或 `{type: 'conjectural', confidence: float}` | 攻擊中；可選帶 Counterexample evidence_only 累積出的 confidence |
| `proved` | `{type: 'classical', lean_path: ...}` <br> 或 `{type: 'construction', witness_lean_path, score, evaluator_hash, generation, seed}` | classical = Builder 形式證明；construction = ConstructionSearch silver verdict（trust_set 在獨立 column） |
| `refuted` | `{type: 'classical', negation_lean_path: ..., negation_goal_id: ...}` <br> 或 `{type: 'witness', witness, evaluator_hash, range, seed}` | classical = Refuter 證 ¬G 後 cascade；witness = Counterexample silver verdict |
| `shelved` | 沿用 shelve 前最後一次 answer_data 或 NULL | 保留 evidence accumulated 但不再投資 |

`answer_data.type` 是 verdict 細節 discriminator；過濾用 SQL `answer_data->>'type' = 'witness'` 之類。

## 3. Stage

Pipeline 由 stage 序列組成。Stage 分兩類：**pure**（純程式）與 **agent**（LLM call）。

**Stage 間資料傳遞**

Pipeline runtime 維護一個 pipeline-local context（存於 `<target>/Staging/p<uuid>/context.json`）。每個 stage 的輸出寫入 context，後續 stage 讀取。Agent stage 的 prompt 為模板 + 從 context interpolate 出的內容。

**共用 stage**：

### 3.1 failure_replay

- **類型**：pure
- **用途**：把過去失敗摘要塞進後續 agent prompt，避免重複撞牆
- **輸入**：target id + target_kind（Goal / Strategy / forward）
- **行為**：讀該 target 最近 K_digest 條 dead_attempts，組成摘要 prompt fragment
- **輸出**：注入下一 agent stage
- **失敗處理**：無 row → 視為 empty，繼續

### 3.2 self_verify

- **類型**：pure
- **用途**：用 Lake 驗 staging 檔的型別正確性 / 證明 closure
- **模式**：
  - **single**：驗單一 staging 檔。Builder / Forward / Refuter 用
  - **multi**：驗多檔協同（含跨檔 import 解析）。Backward 用
- **輸出**：pass / fail + 錯誤訊息
- **失敗處理**：fail + retries < N → 餵錯訊息回上一 agent stage 重跑；retries 用盡 → pipeline outcome failed
- 具體 lake 命令見 impl §6

### 3.3 failure_archive

- **觸發**：pipeline runtime 偵測失敗 outcome
- **類型**：pure
- **行為**：INSERT dead_attempts row + 刪除 staging 目錄
- **輸出**：無（純副作用）

### 3.4 find_lemmas

- **類型**：pure / agent（cache hit / miss）
- **用途**：找可 apply 的 lemma 候選
- **scope**：`mathlib + library`
- **使用者**：Builder、Backward

### 3.5 evidence_update

- **類型**：pure
- **用途**：把 pipeline 過程中累積的部分證據寫進 target Goal 的 `evidence` json
- **輸入**：target_id + dict 形 evidence patch（如 `{counterexample_tested_up_to: 10000}`）
- **行為**：以 json_patch 合併進 `goals.evidence`，emit `evidence_updated` 事件給 Strategist 消費
- **使用者**：Counterexample（at K 無反例時）；未來 ConsistencyChecker / PatternMiner

## 4. Subsystem

### 4.1 Search

底層檢索服務。

- **scope**：`mathlib` / `library` / `local_goals`，可組合
- **cache + index**：`search_cache` table（query_hash → results, expires_at）；cache hit 純函數，miss 才實跑搜尋（可能呼叫 agent）
- **輸出格式**：catalog 一行一筆（id / signature / tags / path / status），預設 cap K=50
- **暴露為 agent tool**：agent 可在 session 內動態呼叫，介面與 cache 共用
- **Cache 失效**：
  - inspiration mode（`find_*`、`inventory`）走純 TTL，scope 分長/短（mathlib / library 長、local_goals 短、inventory 最短）
  - correctness mode（`dedupe`）走 mutation invalidation
  - 具體 TTL 數值與 invalidation 觸發 catalog → impl §2
- **使用者**：
  - stage：`find_lemmas`（§3.4）、`find_subgoals`（Backward inline）、`find_pattern` / `find_mathlib`（Forward inline）、`inventory`（Strategist inline）
  - agent tool：所有 pipeline 的 agent stage

### 4.2 Dedupe

候選 statement 是否與既有等價的判定服務。

- **輸入**：候選 statement + 比對 scope（`mathlib` / `library` / `local_goals`）+ mode
- **mode**：
  - `strict`（預設）：依 α-equivalence + definitional equality 判定
  - `iff_lite`：opt-in。額外跑 simp / decide 試 iff，timeout 內成功才算 dup
- **不涵蓋**：一般 iff（需要真實 proof 才能證的等價）。不同 formulation 框架視為不同 Goal
- **輸出**：matched 列表（含原 entity id）/ 全新
- **暴露為 agent tool**：agent 可在 session 內動態呼叫
- **使用者**：
  - stage：`dedupe (any)`（Forward inline）、`dedupe (local)`（Refuter inline、Backward inline）
  - agent tool：所有 pipeline 的 agent stage

實作走 Lean executable（具體見 impl §7）。

### 4.3 Evolution

具體 witness 搜尋的共用基礎建設。被 Counterexample（找反例）與 ConstructionSearch（找構造）共用。

- **輸入**：candidate generator + evaluator (scoring fn) + budget + （可選）mutation operators
- **核心 loop**：generate → compile（Lean type-check）→ evaluate（scorer 評分）→ select（top-K）→ checkpoint
- **Atomic mode**：單次跑 budget 內無 checkpoint
- **Continuous mode**：定期 checkpoint，可 pause / resume
- **輸出**：best-known candidate + score + reproducibility metadata（evaluator_hash + seed + generation）
- **mutation operators**：框架預先註冊基本 operators（small_random_change / column_swap / lean_synth）；Goal 可在 question 內加客製 operator
- **使用者**：Counterexample（atomic + 未來 continuous）、ConstructionSearch（continuous 為主）

## 5. Pipeline

Scheduler 派出去的單位是 **pipeline**——一條 stage 序列。八種 pipeline：

| Pipeline | 觸發於 | 產出 | Runtime |
|---|---|---|---|
| Builder    | 葉子 Strategy 待證 | Strategy proved / dead | atomic |
| Backward   | Goal 待拆 | 新 Strategy + sub-Goal | atomic |
| Refuter    | structural refill on kind=conjecture + Strategist inject | ¬G 新樹根 + twin_of 雙向 metadata | atomic |
| Forward    | Strategist inject | 新 Goal 入池（corollary） | atomic |
| Generalizer | Strategist inject | 新 Goal 入池（generalization 候選） | atomic |
| Counterexample | structural refill on kind=conjecture + Strategist inject | RefutedWitness verdict 或 evidence 累積 | atomic（未來可升 continuous） |
| ConstructionSearch | structural refill on kind=construction + Strategist inject | construction silver verdict 或 best-known evidence | continuous |
| Strategist | 每 K 個 pipeline_finished | task injection list | atomic |

**Runtime 規則**：

- **Atomic commit**：持久化只在 pipeline 完整成功後做一次（commit 協議見下）
- **整條冪等**：crash 重啟時 staging 不完整 → 整條重跑，stage 級不接續
- **佔 slot 整段**：pipeline 啟動到結束佔一個 concurrency slot
- **Retry pattern**：任何 `[fail → retry from step X]` 的 stage，runtime 自動：
  - 達 `N_retry`（§8 配置，預設 10）retry 或 `T_wall`（§8 配置，預設 30 min）wall-clock → pipeline outcome=`exhausted`
  - agent 早退 → pipeline outcome=agent 指定值
  - 失敗訊息透過 context 餵回指定 retry target stage
- **Outcome 分類**：每個 outcome 屬以下兩類之一，runtime 據此 dispatch 收尾：
  - **success class**（有產出）→ 跑該 pipeline 的 commit stage（commit 內部可依 outcome 變細分 INSERT/UPDATE/evidence_update 路徑）
  - **failure class**（無產出）→ 跑 failure_archive stage
  - 各 pipeline outcome 屬哪類在 pipelines.md 內聲明。Counterexample 為例：`refuted_with_witness` / `evidence_only` 屬 success class（commit 內分流），`unproductive` / `exhausted` 屬 failure class

**Commit 協議**（atomic pipeline）：DB（INSERT/UPDATE goals/strategies）與 FS（mv staging .lean）非原子，靠 row 上 `commit_state ∈ {pending, live}` 兩段式協調。所有 read query 一律 filter `commit_state='live'`，pending row 對外不存在。crash recovery 由 scheduler 啟動時掃 pending row 處理。詳細協議步驟、UPDATE recovery snapshot 機制、各 pipeline 的 INSERT/UPDATE 分流見 impl §1。

**Continuous task runtime**：跟 atomic pipeline 並列的第二類執行模式。差異：

- 長運行（小時到天），跨 atomic 的 T_wall=30 min 上限
- 進度走 **checkpoint 協議**（見下）：定期把 task 自管的 `checkpoint_state`（如 ConstructionSearch 的 generation / population / best_candidate）寫進 `continuous_tasks` 表
- crash 後從 last checkpoint 接續，**不**從頭重跑
- 可 pause / resume（control_signal 控制）
- 走獨立 background pool（cap = `P_continuous`，見 §8），避免長 task 餓死短 pipeline

**Checkpoint 協議**（continuous task）：

```
每 T_checkpoint（如 5 min）或 budget event：
  Step 1. BEGIN TX
          UPDATE continuous_tasks SET checkpoint_state = ..., last_checkpoint_at = now,
                 consumed_tokens += ..., consumed_wall_clock_sec += ...
          INSERT events (kind='task_checkpoint', payload)
          COMMIT
  Step 2. （可選）evidence_update on target Goal（如 best-known score 寫進 evidence）
  Step 3. （可選）promote 中間結果至 Library/Constructions/<G>.json（best-known 同檔覆寫）
```

continuous task 的 working dir **不在 task 內結束時刪**——保留到 task done / killed，便於人工 inspect 與接續。

**Paused 狀態 timeout**：lifecycle_state='paused' 超過 `T_pause_max`（§8 配置，預設 7 天）→ scheduler 自動轉 lifecycle_state='killed'、清 working dir、emit `task_checkpoint` 紀錄 paused-timeout 原因。避免 paused task 永遠占 disk。人類仍可在 timeout 前 control_signal resume 接續。

**Session 策略**：session 與 atomic pipeline 1:1，**不跨 pipeline 復用**。pipeline 結束即回收 session（刪 jsonl）。Continuous task 不長持 session：每次 agent 呼叫（如 generate stage）開短 session 跑完即丟。GC 細節見 impl。

各 pipeline 的 stage 序列、outcome、行為規則 → 見 `architecture_v3_pipelines.md`。

### 5.6 跨 pipeline invariants

- Builder 的 `bad_goal` outcome 觸發雙寫 dead_attempts（sub-Goal + 父 Goal），讓父 Goal 下個 Backward 學到（詳細 cascade 規則 §6 + pipelines.md §1）
- Backward commit 時為每個新 sub-Goal 計算 `parent_subgoal_max_similarity` 寫入 strategies table，給 Strategist 偵測 IH-trap（§7.5）
- Refuter commit 時對 ¬G 與 G 雙向 UPDATE `twin_of`（同 commit TX）
- Strategist decisions 的 enum 與 demux 規則（Refuter / Forward / Backward / Counterexample / ConstructionSearch → queue inject；Shelve → 直接 UPDATE）見 §6 task queue 段
- ConstructionSearch silver verdict (`status='proved'` AND `answer_data.type='construction'`) 觸發 cascade，spawn Builder for `∃ X, P(X)` 形式 Goal 試證（用 evidence 內 witness）；Builder 證成功 → upgrade 到 `answer_data.type='classical'`（gold formal proof）。trust 強度只允許單向升級

## 6. 動態管線

**Multi-Problem orchestration 邊界**：

- **Scheduler 是全域單 reactor**（一個 process / 一個 event loop），不是 per-Problem
- **Queue + pool 全 Problem 共享**——atomic queue / continuous queue / pools 都是全域，Problem 之間競爭 slot
- **Structural refill BFS 對所有 Problem 跑**——掃 goals table 全部 row（filter by `commit_state='live'`），不限 Problem
- **Strategist inventory per-Problem 視野**——每次 Strategist 跑時 inject 一個 Problem id 進 prompt，inventory 只聚合該 Problem 的 metrics（避免跨 Problem prompt 過大、語境混淆）。Strategist 觸發時 round-robin 不同 Problem
- **Cascade 與 cancellation per-Goal**——cascade 只影響該 Goal 的依賴鏈，不跨 Problem 連動
- **`derived_from` cascade 限同 Problem**——schema 不擋跨 Problem `derived_from` FK 寫入，但 cascade rule 預設加 `WHERE problem = ?` filter；`construction_witness` Goal 升原 G silver→gold 只在同 Problem 內 propagate；跨 Problem 升 gold 行為**未定義**（reject + emit alert）
- **Library promotion 共享**——所有 Problem 寫入同一個 `Library/Theorems/` `Library/Counterexamples/` `Library/Constructions/`

實作上等同單一 scheduler instance 管全域；多 instance 並發在同一 DB 不支援（schedulers table liveness check 防止）。

**事件**

四種：

| 事件 | 觸發 | payload |
|---|---|---|
| `pipeline_finished` | 任一 pipeline（atomic or continuous）結束 | 類型、target、outcome、產出 |
| `task_checkpoint` | continuous task 跑 checkpoint | task_id、generation / progress、best_score 等 |
| `control_signal`    | 人類介入 | action ∈ {pause, resume, shutdown, set_budget}、scope |
| `fatal`            | scheduler 偵測無法修復的不變量違反（如 cascade SQL fail / dual proved twin / continuous task 殘缺）| reason、affected entity ids |

Cascade（Goal proved / Strategy dead / ...）是 scheduler 處理 `pipeline_finished` 時同步算的副作用，不進事件 queue。Status override 走 DB 直接 UPDATE，不需事件。

**Scheduler**

```
事件 → FIFO queue → Scheduler（單執行緒 reactor）→ Pipeline pool（cap P）
                                                            ↓
                                            emit pipeline_finished 回 queue
```

每個事件 reactor 跑 6 步（見下方「步驟細節」）。無 iteration、無 batch boundary。Wall-clock 受最長 pipeline 限制。

**Idle 行為**：reactor pop 不到 event 時 **block 在 event_bus**（不 busy-loop poll），有新 event（pipeline_finished / task_checkpoint / control_signal / fatal）或 pool 有 slot 變動時喚醒。預設 wake-up timeout = 30s，作為 idle tick 觸發 structural refill 以兜底（避免 event-only 模型錯過某些被動狀態的 enqueue 機會）。

**步驟細節**

1. **Liveness check**：事件帶 source pipeline id。確認該 pipeline 仍該被處理：
   - 對應 Strategy / Goal 已被 cascade 標 dead/refuted → 結果無關，丟棄
   - pipeline 已被主動 kill（cancellation propagation）→ 丟棄
   - 否則繼續。避免處理 stale 事件浪費 cascade。

2. **讀相關 view**：從 DB 讀局部狀態，無記憶體 cache：
   - target Goal/Strategy 的 row（status / origin / twin_of）
   - 上下游引用鏈（父 Strategy / sub-Goal、twin Goal）
   - 該 target 的 dead_attempts 摘要（若需要）
   每次事件處理 fresh query，符合 DB 即 source of truth。

3. **Cascade + status update**：在單一 DB transaction 內套 cascade 規則。更新 `goals.status` / `goals.answer_data` / `strategies.status` 等 column。觸發 Lake build（按 build 策略）。

   **失敗處理**：cascade TX 內 SQL 失敗（如 unique constraint violation、JSON 格式錯、FK reference invalid）→ TX rollback、emit `fatal` event 含 reason + affected ids、scheduler halt（reactor 停 spawn 新 pipeline、保留 working dir + DB 現場給人類 review）。**不嘗試自動修復**——cascade 失敗暗示 spec / data 有 bug，silent retry 會放大不一致。重啟需人類確認 bug fix 後手動 resume。

   主要規則：

   - Builder/Backward 鏈成功 → Goal `status='proved'`、`answer_data={type:'classical', lean_path}`、`trust_set` 由 #print axioms 構造；twin（若有）`status='refuted'`、`answer_data={type:'classical', negation_lean_path, negation_goal_id}`、`trust_set` 從 ¬G 繼承
   - Strategy dead → 上游 Goal 可能連鎖回 open / shelved
   - **Counterexample 找到反例**：直接 G `status='refuted'`、`answer_data={type:'witness', witness, evaluator_hash, range, seed}`、`trust_set` 含 `kind=computational` entry，寫 Library/Counterexamples/<G>.json。witness 也存進 G.evidence 給後續 Refuter 用
   - **Counterexample 至 K 無反例（evidence_only）** → 走 evidence_update（§3.5），Goal status 不變，可選把 `answer_data` 設為 `{type:'conjectural', confidence: ...}` 反映目前 best assessment；emit `evidence_updated` 給 Strategist 消費
   - **Silver → Gold 升級（refuted 路徑）**：若 G 已 `status='refuted'` 且 `answer_data.type='witness'`（silver），Refuter 後續證 ¬G 成功（cascade twin） → UPDATE G `answer_data={type:'classical', negation_lean_path, ...}`、`trust_set` 換成 ¬G 繼承的 lean_axiom 全集、Library/Counterexamples/<G>.json 改寫 classical schema。trust 強度只允許單向升級（classical → witness 不可逆）
   - **ConstructionSearch 找到合格 instance H**：直接 G `status='proved'`、`answer_data={type:'construction', witness_lean_path, score, evaluator_hash, generation, seed}`、`trust_set` 含 `kind=computational` entry，寫 Library/Constructions/<G>.json。witness 也存進 G.evidence 給後續 Builder 用。同時 spawn 一個輔助 Goal `∃ X, P(X)` (origin='construction_witness', kind='theorem')，帶現成 Strategy（proof body 候選 `⟨H, by decide⟩` 等）入池
   - **Silver → Gold 升級（proved-construction 路徑）**：若 G 已 `status='proved'` 且 `answer_data.type='construction'`（silver），輔助 Goal 的 Builder 證成功 → cascade → UPDATE G `answer_data={type:'classical', lean_path}`、`trust_set` 換成 lean_axiom 集、Library/Constructions/<G>.json 改寫 classical schema（記 lean_path）
   - **ConstructionSearch budget 用盡無合格 instance**：evidence_update 寫 `best_known: {witness, score, generation}`，G status 不變（attempting）；emit `evidence_updated` 給 Strategist 消費

   **Cascade upward propagation（Goal proved 後往上傳）**：

   sub-Goal status 翻 'proved' 後，cascade 不直接動父 Strategy / 父 Goal——靠下個 reactor cycle 的 structural refill 偵測：

   1. cascade 處理完 sub-Goal proved（單 cycle 內所有 cascade 規則套用完）
   2. 下個 cycle 的 step 4 queue refill 跑 BFS：`SELECT strategies WHERE goal_id=父 AND commit_state='live' AND status='in_progress'` 跑「該 Strategy 的 strategy_subgoals 是否全 proved」檢查
   3. 全 proved 的 Strategy → enqueue Builder（pipelines.md §1）對該 Strategy 跑 lake build verify
   4. Builder 證該 Strategy 成功 → 該 Strategy status='succeeded' → cascade 規則套用「Builder/Backward 鏈成功 → 父 Goal status='proved'」
   5. 父 Goal status flip 後再進 1，遞迴往上傳到 root

   這個傳播鏈隱含在「structural refill + Builder + cascade」的組合，不是 cascade 規則的單一 rule——是多次 cycle 累積的結果。Wall-clock 上每往上一層大約 = 一次 Builder lake build 時間。

4. **Queue refill 判定**：若 pending task queue depth < P，立即查 goals table 找 actionable 項目 fill 到 P（real-time refresh，task 永遠反映最新 DB 狀態）。

5. **Strategist 觸發判定**：累計事件計數，達 K_strategist 且 Strategist 不在跑 → 注入 Strategist task 到 queue 左端。Strategist 自身完成時清 cooldown 旗標。

6. **Pop + spawn**：從 queue 左端（高優先優先）pop task，spawn 對應 pipeline。直到 pool 滿或 queue 空。

**Task queue 與兩種來源**

scheduler 不算 score，task queue 由兩個來源填：

- **Structural refill**（real-time，queue depth < P 觸發、補到 P）
  - 從 roots BFS 查 goals table（沿 strategy_subgoals 邊）
  - open Goal → enqueue Backward task
  - 全 sub-Goal proved 的 Strategy → enqueue Builder task
  - **`kind=conjecture` Goal 入池 → 額外 enqueue Counterexample (atomic) + Refuter，與 Backward 並排（三線並攻）**
  - **`kind=construction` Goal 入池 → 額外 enqueue ConstructionSearch (continuous，進 background pool)，與 Backward 並排**（兩線：Backward 試結構性拆解、ConstructionSearch 跑演化。Builder 不直接派——它對 leaf Strategy 派，由 Backward 後續產 Strategy 才走第二條結構 refill 規則自動 enqueue）
  - **每次 enqueue 前過濾 `goals.blocked_pipelines`**：若目標 pipeline kind 在 list 內 → 跳過
  - 純函數，順序由圖結構決定
  - 小 queue 確保 task 反映最新 DB 狀態，避免 stale

- **Strategist inject**（每 K_strategist 個 pipeline_finished 觸發）
  - Strategist pipeline 跑完寫 strategist_decisions row（≤ M_strategist 個 decision）
  - scheduler 讀後 demux：
    - `Refuter` / `Forward` / `Generalizer` / `Backward` / `Counterexample` / `ConstructionSearch` → INSERT queue（priority=high，左端 push）。**INSERT 前查 target Goal 的 `blocked_pipelines`，若該 pipeline kind 在 list 內 → 跳過該 decision**（同 structural refill 的過濾規則）
    - `Shelve` → 直接 UPDATE goals.status='shelved'（不入 queue、不派 pipeline）
  - cooldown：Strategist 沒跑完前不重派

queue 是 deque：高優先從左 push（Strategist）、結構性從右 push（refill）、永遠從左 pop。同優先級內 FIFO。

**Pipeline 觸發來源**

| Pipeline | 來源 | Pool |
|---|---|---|
| Builder | structural refill | atomic |
| Backward | structural refill（多數）+ Strategist inject（高優先案例） | atomic |
| Counterexample | structural refill（kind=conjecture）+ Strategist inject（加碼或對 theorem-kind sanity check） | atomic |
| Refuter | structural refill（kind=conjecture）+ Strategist inject（對 theorem-kind 派只能走 Strategist） | atomic |
| Forward | Strategist inject | atomic |
| Generalizer | Strategist inject | atomic |
| ConstructionSearch | structural refill（kind=construction）+ Strategist inject（加碼 budget / 換 mutation） | continuous（background pool） |
| Strategist | 事件計數觸發（每 K 個 pipeline_finished） | atomic |

**雙 pool**：atomic pool（cap=`P`）跟 continuous background pool（cap=`P_continuous`，預設 P/4）獨立。避免長運行 task 餓死短 pipeline、也避免相反。queue 與 dispatch 邏輯按 pool 分流。

**Pause / Shutdown 語意**

- `pause`：停止新 pipeline 派發，現有 pipeline 自然結束
- `shutdown`：強制 kill 所有 pipeline + 終止 scheduler

**Build 策略**

`pipeline_finished` 處理時：
1. 從變動檔往上 walk dependency graph，找「可能因此 close 的最高 Goal 集」
2. build 那些目標
3. 讀 build 結果更新 affected 的 `goals.status` column

避免「即時只 build 直接父 + 延遲全 build」的雙段拖延。具體 lake 命令見 impl §6。

**Library promotion**

cascade 依 `status` + `answer_data.type` + `origin` 分流：

- `status='proved'` + `answer_data.type='classical'` + `origin='root'` + `trust_set` 通過 `Library.whitelist` → append `Library/Theorems/proved.lean` re-export root theorem
- `status='proved'` + `answer_data.type='construction'` + `origin='root'`（ConstructionSearch silver verdict）→ 寫 `Library/Constructions/<problem>_<slug>.json` 紀錄 `{type: 'construction', witness_lean_path, score, evaluator_hash, generation, seed}`。後續若 Builder 證 `∃ X, P(X)` 成功，cascade 升級此 entry 為 type='classical' schema（同檔覆寫，記 lean_path）
- `status='refuted'` + `answer_data.type='classical'` + `origin='root'` → 寫 `Library/Counterexamples/<problem>_<slug>.json` 紀錄 `{type: 'classical', negation_lean_path, negation_goal_id}`
- `status='refuted'` + `answer_data.type='witness'` + `origin='root'` → 寫 `Library/Counterexamples/<problem>_<slug>.json` 紀錄 `{type: 'witness', witness, evaluator_hash, range, seed}`。後續升級到 classical schema 同 Counterexample 機制
- `status='attempting'` + `answer_data.type='conjectural'` → 不自動 promote（保留至 Library 引入 Conjectures/ 層後處理）

Library/Theorems/proved.lean 只收 user-injected root（origin='root'）proved；內部 lemma 由其他 Problem 直接 import 該 Problem 的 `proved.lean` 取用。Refuter ¬G、Counterexample-witness ¬P(w) 等輔助 Goal 自身不入 Library/Theorems/（雖然是 Lean-proved），但其證明結果經 cascade 傳給 user 的 root conjecture 後，記錄於 Library/Counterexamples/。

不通過 `Library.whitelist` 的 proved root（即使通過 `Problem.axioms` cascade verdict）→ 不入 Library/Theorems/，原 Goal 狀態不變。

**Cancellation propagation**

cascade 觸發 terminal status 時，依 verdict 種類用**正向白名單**列出該 cancel 的 pipeline 種類；不在白名單的（包含未列出的新 pipeline）保留：

| Verdict 觸發源 | 該 cancel 的 still-running pipeline kinds（針對同 Goal）|
|---|---|
| Builder/Backward 鏈 → Goal proved (full classical) | Builder, Backward, Refuter, Counterexample, ConstructionSearch（全 cancel） |
| Refuter→Builder 鏈 → twin G refuted (full classical) | 同上 |
| Counterexample silver (`type='witness'`) | Builder, Backward, Counterexample（**Refuter 留**——升級用） |
| ConstructionSearch silver (`type='construction'`) | Backward, ConstructionSearch（**Builder 留**——升級用、且自身是輔助 Goal 的對應 Builder） |
| Strategy dead 連鎖 Goal 退 open / shelved | Builder, Backward 對應 Strategy 的 still-running |

新加 pipeline 預設**不**入白名單（保守）。需要 cancel 時新增該 pipeline 進對應 verdict 的白名單。

配 liveness check 處理事件 queue 裡的 stale 事件。

**儀錶板**

由 CLI tool / web 從 DB on-demand render，無 push 機制。框架不主動通知 dashboard。需要實時觀察用 polling 或自行實作 file-watcher style 監聽 events table。

## 7. 硬閘門

跨 pipeline 的不變量，由 scheduler 或 runtime 強制。

### 7.1 Trust set 與 axiom whitelist

每個有 verdict 的 Goal 帶一個 `trust_set`：該 verdict 依賴的所有 trust 假設集合。每個 entry：

```
{ name, kind, provenance, confidence? }
  kind ∈ { lean_axiom, computational }
```

- `lean_axiom`：Lean `#print axioms` 輸出的 axiom name（最常見）
- `computational`：暴力枚舉 / decide 的計算證據，metadata 帶 evaluator_hash + range + seed

**兩個獨立 whitelist**（不再有「override」概念）：

- `Problem.axioms`：每個 Problem 在 META.md **強制宣告**的完整 axiom 集合（無 framework default 繼承）。Problem 內 cascade verdict accept rule 用此值。是該 Problem 的 axiom 基礎宣告，涵蓋 foundational 與 mathematical 兩層假設
- `Library.whitelist`：框架配置一個獨立全域值，定義 `Library/Theorems/proved.lean` 接受的 axiom 集合（典型為三公理）。跟 Problem 配置完全獨立

**Cascade 檢查**：scheduler cascade（§6 step 3）將 root Goal 確定 verdict 前構造並驗 trust_set。**接受規則依 `answer_data.type` 分流**：

```
status='proved'（answer_data.type='classical'，trust_set 應全 lean_axiom）：
  全 entry 滿足
    kind = lean_axiom  AND  name ∈ Problem.axioms

status='refuted', answer_data.type='witness'（trust_set 含 computational entry）：
  全 entry 滿足
    (kind = lean_axiom  AND  name ∈ Problem.axioms)
    OR (kind = computational  AND  has evaluator_hash + range + seed metadata)

status='refuted', answer_data.type='classical'（cascade 自 twin proved 推得）：
  繼承 twin Goal 的 trust_set（不另構造）
```

違反 → 不翻 verdict、保 `attempting`、dead_attempts 記 `trust_set rejected: <違規 entries>`、對該 root 派 `pause` control_signal（人類 review）。

**Library promotion 用 `Library.whitelist`（獨立 whitelist，不查 Problem.axioms）**：Problem 內可接受 RH 等 mathematical 假設並證出依賴 RH 的結果，但這些結果不會進共用 Library/Theorems/——Library 守 `Library.whitelist`（典型三公理）。Problem 內 RH-dependent 結果留在 `Problems/<name>/proved.lean`，其他 Problem 想用必須顯式 import + 自己的 META.md 也宣告 RH 在 axioms 內。詳細見 §8。

### 7.2 Agent 修改範圍

Agent stage 只可寫入 `Goals/<G>/Staging/<p_uuid>/`。其他位置（既有 `Goals/<G>/<slug>.lean`、`Strategies/<S_id>_<slug>.lean`、`Library/`、`Defs.lean`、`Root.lean`、其他 Problem、`Tooling/`、DB）一律唯讀。

執行：

- pipeline runtime 透過 `claude --add-dir` 把 agent 可見路徑限制在當前 Problem + 該 pipeline 的 staging dir
- agent stage 結束後 runtime 驗證「除 staging 外無檔案被改」（git status 等價檢查），違反 → 該 stage 視為 failed → 走 retry 路徑
- commit stage 才把 staging 檔搬到正式位置，由 runtime 執行（非 agent）

### 7.3 Depth 上限

任一 Goal `depth ≥ D_max[kind]` 由 scheduler 在 structural refill 階段直接 UPDATE `status='shelved'`，不入 queue、不派 pipeline。補強 Strategist 失職時的 runaway 遞迴防線。

per-kind 預設：

- `D_max[theorem] = 12`
- `D_max[conjecture] = 8`（更早 shelve，把算力釋放給 Counterexample / Refuter）
- `D_max[construction]`：不適用——construction Goal 通常無 sub-Goal 拆解（ConstructionSearch 是 evolution loop 不是 Backward 拆），depth 永遠 ≤ 1，由 evolution budget 限制壽命

per-Problem 可在 META.md 宣告（§8）。

### 7.4 Validator：禁 regex parse Lean 源碼

Backward §5.2 step 6 的 hypothesis carry 檢查必須走 Lean meta。**禁用 regex parse Lean 源碼**。具體工具介面與背景理由見 impl §4。

### 7.5 IH-trap 偵測訊號

Backward commit 時對每個新 sub-Goal 計算與父 Goal 的結構相似度（metric 由 spike 決定，候選 token Jaccard / identifier overlap / AST diff），取 max 存入 `strategies.parent_subgoal_max_similarity`。Strategist 在 inventory 中暴露此值；**訊號**：Strategy 連續 ≥ 2 次 unproductive AND `parent_subgoal_max_similarity ≥ 閾值` → 強訊號 Refuter / Shelve。

避免 IH-trap（sub-Goal 形狀同父、IH 永遠不可呼叫）燒到 `D_max` 才被 §7.3 兜底。Hadamard `sylvester_gallai L0005` 真踩過。

## 8. 框架配置

兩層獨立配置，無繼承 / override 關係：

- **框架配置**：全域、單一來源、典型寫在 framework config 檔。涵蓋 runtime 行為旋鈕 + Library 接受 whitelist
- **Per-Problem 配置**：每個 Problem 在 META.md 強制宣告，沒繼承機制。涵蓋該 Problem 的 axiom 基礎 + 該 Problem 範圍內的旋鈕

### 8.1 框架配置項

| 項目 | 預設 | 用處 | 章節 |
|---|---|---|---|
| `agent.providers` | `[claude]`（P5 起加 gemini / codex 為備援） | Agent stage 可用的 provider 列表，每個 entry 含 CLI path / API key env / scope-isolation 機制（如 claude 的 `--add-dir`） | §8.3 |
| `agent.fallback_chain` | `[claude]` | Agent invoke 失敗（連 N 次 retry / timeout）時依序 fallback 的 provider 順序 | §8.3 |
| `agent.model_defaults` | dict（見 §8.3） | 每個 (pipeline_kind, agent_stage) 的預設 model；解析三層覆寫順序：Strategist decision payload > Problem META.md `models?:` > 此預設 | §8.3 |
| `Library.whitelist` | `{propext, Quot.sound, Classical.choice}` | Library/Theorems/proved.lean promotion 接受的 axiom | §7.1 |
| `D_max[theorem]` | 12 | theorem-kind Goal depth 自動 shelve 上限 | §7.3 |
| `D_max[conjecture]` | 8 | conjecture-kind Goal depth 自動 shelve 上限 | §7.3 |
| `counterexample_atomic_budget` | 5 min | atomic Counterexample 單次 wall-clock 上限 | pipelines.md §6 |
| `counterexample_atomic_range_default` | 1000 | atomic Counterexample 預設枚舉範圍 | pipelines.md §6 |
| `P` | 待定 | atomic pipeline pool concurrency cap | §6 |
| `P_continuous` | P/4 | continuous task background pool cap | §6 |
| `T_checkpoint` | 5 min | continuous task checkpoint 間隔 | §5 |
| `T_pause_max` | 7 days | continuous task paused 自動 killed timeout | §5 |
| `N_retry` | 10 | atomic stage retry hard cap | §5 |
| `T_wall` | 30 min | atomic pipeline wall-clock 上限（continuous task 不適用，自帶 budget） | §5 |
| `K_strategist` | P×2 | Strategist 觸發的 pipeline_finished 事件數 | §6 |
| `M_strategist` | 5 | Strategist 每次 inject task 數的上限 | §5.5 |
| `K_digest` | 5 | failure_replay 從 dead_attempts 抽幾條 | §3.1 |
| `construction_atomic_budget_generations` | 100 | ConstructionSearch atomic 模式預設代數上限 | pipelines.md §7 |
| `construction_continuous_budget_wall_clock_sec` | 14400 | ConstructionSearch continuous 模式預設 wall-clock（4h） | pipelines.md §7 |
| `construction_score_plateau_generations` | 20 | 連續無改進代數，觸發 Strategist plateau signal | pipelines.md §7 |
| `ih_trap_similarity_threshold` | 待 spike | parent_subgoal_max_similarity ≥ 此值 + Strategy 連續 unproductive 觸發 IH-trap signal | §7.5 |
| `N_block_after_failures` | 5 | 任一 pipeline kind 對單一 Goal 連 N 次失敗後自動寫進 `blocked_pipelines` | §9.1 goals.blocked_pipelines |
| `lake_subprocess_timeout_sec` | 600 | 單次 `lake env lean` / `lake build` subprocess wall-clock | impl §6.2 |
| `validator.max_subgoals` | 8 | Backward 單次 PROPOSAL 最多 sub-Goal 數；超過 reject | impl §4 |
| `cancellation_sigterm_grace_sec` | 5 | cancel pipeline 時 SIGTERM 後等多久 SIGKILL fallback | §6 cancellation |
| `dedupe.subprocess_timeout_sec` | 30 | `tools/dedupe.lean` subprocess wall-clock 上限 | impl §7.1 |
| `dedupe.iff_lite_check_timeout_sec` | 5 | iff_lite mode `simp/decide` per pair timeout | impl §7.1 |
| `strategist.evidence_window` | 20 | Strategist agent prompt 內看最近 N 個 `evidence_updated` event | §6 Strategist |
| `strategist.decisions_lookback` | 10 | Strategist 過去 N 次 decisions outcome 反思進 prompt | §6 Strategist |

硬編碼（非 tunable，由架構決定）：

- queue 維持深度 = `P`（depth < P 即 refill 補回 P）
- search catalog cap = 50（inventory mode 無 cap）

**Runtime mutability category**：CLI `asterism config set` 對不同 category 不同行為，避免 retroactive / partial-effect bug：

| Category | Keys | `config set` 行為 |
|---|---|---|
| **mutable**（即時生效） | `strategist.enabled` / `K_strategist` / `M_strategist` / `K_digest` / `ih_trap_similarity_threshold` / `strategist.evidence_window` / `strategist.decisions_lookback` / `N_block_after_failures` / `D_max[*]` | UPDATE 即生效，下次 reactor cycle / pipeline 啟動讀新值 |
| **restart-required**（需重啟 daemon） | `P` / `P_continuous` / `T_checkpoint` / `T_pause_max` / `T_wall` / `N_retry` / `agent.providers` / `agent.fallback_chain` / `agent.model_defaults.*` | UPDATE 寫入 config 但 in-flight pipeline 用舊值；CLI 提示 user 重啟 |
| **immutable**（拒絕 runtime 改） | `Library.whitelist` / `Problem.axioms`（policy）| `config set` reject + 提示「請編輯 config 檔 + 跑 `asterism library audit` 重評既有 entry」（避免 retroactive 影響既有 Library promotion 結果） |

### 8.2 Per-Problem 配置（強制宣告）

每個 Problem 在 `Problems/<name>/META.md` 的 YAML frontmatter **強制完整宣告**。沒繼承、沒 fallback——讀 META.md 就完整知道該 Problem 的 axiom 基礎與旋鈕設定。具體格式見 impl §5.0。

`models?:` 是 META.md 的**選擇性**欄位，覆寫框架 `agent.model_defaults` 對該 Problem 內的 agent stage 用什麼 model（如「對難 Problem 整體升 sonnet → opus」）。未宣告 → 用框架預設。

**`axioms`（強制）**：該 Problem 的完整 axiom 集合，是 axiom 基礎宣告——這個 Problem 的所有結果都在此 axiom 集合上成立。涵蓋兩層次：

- **Foundational 層**（後設推理規則）：`propext` / `Quot.sound` / `Classical.choice` 等。可加嚴（純構造研究移除 `Classical.choice`）或放寬（加入 `Classical.indefiniteDescription` 等 Mathlib 常見 axiom）
- **Mathematical 層**（把未證命題當工作假設）：把已知未證的猜想當 axiom 引入（Riemann Hypothesis、ABC conjecture、P ≠ NP、Twin Primes、Continuum Hypothesis 等），研究「假設 X → 推出 Y」這種條件性結果——是研究數學的常規 mode

該 Problem 的所有依賴 X 的結果，其他 Problem import 時 consumer 必須在自己 META.md 的 axioms 也含 X 才能用。

**Library 隔離**：Problem 內 RH-dependent 結果不會自動進共用 `Library/Theorems/proved.lean`——後者用 `Library.whitelist`（典型三公理）為門檻。Problem 擴張的 axiom 集只影響該 Problem 內 cascade，不污染共用 Library。

### 8.3 Agent runtime（multi-provider）

Agent stage 的執行抽象為 **Provider** 介面：給定 `(model, prompt, scope_dirs)` → response。框架支援多 provider，但**單一 active + 失敗 fallback** 模式（不做動態混用）。

**支援 provider**：

- `claude`（P2 起，主力）：CLI `claude --add-dir <path>` 限制檔案系統視野
- `gemini`（P5 起，備援）：CLI tool scope 控制
- `codex`（P5 起，備援）：CLI sandbox / approval mode

各 provider 的 scope-isolation 機制不同——框架負責對齊到「除指定 staging dir 外無檔案被改」的不變量（§7.2），具體 wrapper 實作見 impl §6.6。

**Fallback 觸發**：active provider 對單一 agent stage 連 `N_retry` 次失敗（含 timeout、scope 違規、output 解析錯）→ 切 fallback chain 下一家、prompt 不變、retry 計數歸零。整條 fallback chain 用盡仍失敗 → pipeline outcome=`exhausted`。

**Model 解析三層**（從低優先到高）：

1. 框架預設 `agent.model_defaults`：每 (pipeline_kind, agent_stage) → model name
2. Problem META.md `models?:` 覆寫
3. Strategist decision payload `model?` / `provider?` 欄位（運行期單次覆寫，如「對 stuck Goal 加強用 opus」）

**預設 `agent.model_defaults`**（高頻 pipeline 用便宜 model、低頻關鍵 pipeline 用強 model）：

| Pipeline / Stage | 預設 model | 量級 |
|---|---|---|
| `builder.tactic_llm` | haiku | 高（每葉子 Strategy） |
| `construction_search.generate` | haiku | 高（每代 N 候選） |
| `backward.agent` | sonnet | 中 |
| `refuter.agent` | sonnet | 中 |
| `counterexample.agent` | sonnet | 低（一次 per Goal） |
| `forward.agent` | sonnet | 低（Strategist 才 inject） |
| `generalizer.agent` | sonnet | 低（Strategist 才 inject） |
| `strategist.agent` | opus | 低（K 個 pipeline_finished 才一次） |

Model name 採跨 provider 共用 tier 詞彙（haiku / sonnet / opus），各 provider wrapper 自行 map 到對應 model id（如 claude `haiku` → `claude-haiku-4-5`、gemini `haiku` → `gemini-flash-*`）。

**Prompt 共用 + 備援差異吸收**：`docs/prompts/<stage>.md` 一份 prompt 三家 provider 共吃。fallback 觸發時若效果差，靠 outcome 統計 + Strategist signal 反饋，**不**為單一 provider 深度調 prompt（避免 prompt 維護成本爆炸）。

## 9. Storage

DB 為 source of truth；.lean 檔僅存 Lean source code（Lake build 必需），不混 metadata。

### 9.1 DB Schema

主要 tables（SQLite 起步、scale 後 Postgres，schema 不變）：

**goals**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | PK | Goal 識別 |
| `problem` | text | 隸屬 Problem |
| `slug` | text | 可讀識別 |
| `lean_path` | text UNIQUE | Goal 檔路徑（UNIQUE：ID race / slug 撞的 defense in depth） |
| `statement_hash` | text | dedupe 用 |
| `origin` | enum | root / backward / forward / generalizer / refuter_negation / construction_witness；`root` 為使用者注入頂層 target |
| `kind` | enum | theorem / conjecture / construction（§2.2） |
| `question` | json nullable | kind-dependent 問題定義（theorem/conjecture: NULL，內容在 lean_path；construction: spec predicate + evaluator info）（§2.2） |
| `status` | enum | open / attempting / proved / refuted / shelved |
| `answer_data` | json nullable | verdict 細節 payload；schema 依 status 不同（§2.2） |
| `evidence` | json | free-form 累積；pipeline 透過 evidence_update 寫 |
| `twin_of` | FK goals nullable | ¬G 互指 |
| `derived_from` | FK goals nullable | 輔助 Goal 反向指原 G（construction_witness Goal 指 ConstructionSearch 原 Goal）。Cascade silver→gold 升級用 |
| `blocked_pipelines` | json，list of pipeline kind strings；預設 `[]` | 對該 Goal 不再派的 pipeline 種類；structural refill 與 Strategist inject 都需查此欄位過濾。寫入時機：(1) Counterexample unproductive、(2) **任一 pipeline kind 對該 Goal 連 `N_block_after_failures` 次（§8 配置，預設 5）outcome ∈ {exhausted, unproductive}**——避免 stuck Goal 反覆燒 token。寫入時 emit Strategist signal 提示加碼介入 |
| `depth` | int | root = 0；sub-Goal = parent.depth + 1 |
| `commit_state` | enum | pending / live（§5 commit 協議；read query 一律 filter `live`） |
| `prior_state_snapshot` | json nullable | UPDATE-case commit recovery 用；非 NULL 表 commit 進行中的 row 原始狀態 |
| `trust_set` | json nullable | proved 時填入；list of {name, kind, provenance, confidence?}（§7.1） |
| `status_changed_at` | ts | status 變動時間，Strategist `attempting_age` 用 |
| `created_at`, `updated_at` | ts | |

**strategies**

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | PK | |
| `goal_id` | FK goals | 父 Goal |
| `lean_path` | text UNIQUE | combinator .lean 檔（UNIQUE：同 goals.lean_path 理由） |
| `status` | enum | proposed / in_progress / succeeded / dead |
| `commit_state` | enum | pending / live（§5 commit 協議） |
| `prior_state_snapshot` | json nullable | UPDATE-case commit recovery 用 |
| `parent_subgoal_max_similarity` | float nullable | Backward commit 時計算；Strategist 偵測 IH-trap 用（§7.5） |
| `created_by` | FK pipelines | 哪個 pipeline 產出 |
| `created_at` | ts | |

**strategy_subgoals**（M:N）

| 欄位 | 型別 |
|---|---|
| `strategy_id` | FK strategies |
| `subgoal_id` | FK goals |
| `position` | int |

**pipelines**（active + 完成歷史）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | PK uuid | |
| `kind` | enum | Builder / Backward / Refuter / Forward / Generalizer / Counterexample / ConstructionSearch / Strategist |
| `runtime` | enum | atomic / continuous（後者 row 在 continuous_tasks 有對應）。當前跟 `kind` 為 1:1 映射（ConstructionSearch=continuous、其餘=atomic），保留獨立 enum 是為了未來 Counterexample 升 continuous 模式時不需 schema 變動 |
| `target_id`, `target_kind` | text, enum | Goal / Strategy / forward(global) |
| `status` | enum | running / succeeded / failed |
| `outcome` | text | proved / exhausted / unproductive / ... |
| `session_id` | text | claude session id（running 時） |
| `started_at`, `finished_at` | ts | |

**dead_attempts**（取代 Dead/digest.md，failure_replay 來源）

| 欄位 | 型別 |
|---|---|
| `id` | PK |
| `target_id`, `target_kind` | text, enum |
| `pipeline_id` | FK pipelines |
| `pipeline_kind` | enum |
| `outcome` | text |
| `reason_summary` | text（一行）|
| `ts` | ts |

**queue**（pending tasks，scheduler 用）

| 欄位 | 型別 |
|---|---|
| `id` | PK auto increment（FIFO 順序）|
| `kind` | enum pipeline 種類 |
| `target_id` | text |
| `priority` | int；**數字越大優先**（0 = structural / 1 = strategist inject；deque 從 priority desc + id asc 順序 pop）|
| `payload` | json |
| `created_at` | ts |

**continuous_tasks**（continuous runtime pipeline 的長週期狀態，§5）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `pipeline_id` | PK FK pipelines | 對應 pipelines.id（runtime='continuous'） |
| `checkpoint_state` | json | 該 task 自管的 progress（如 ConstructionSearch 含 generation / population / best_candidate）|
| `last_checkpoint_at` | ts | |
| `budget_tokens`, `budget_wall_clock_sec` | int | 上限 |
| `consumed_tokens`, `consumed_wall_clock_sec` | int | 累計 |
| `lifecycle_state` | enum | running / paused / done / killed |

**construction_attempts**（ConstructionSearch 演化系譜）

| 欄位 | 型別 |
|---|---|
| `id` | PK |
| `pipeline_id` | FK pipelines |
| `generation` | int |
| `parent_attempt_id` | FK self nullable |
| `candidate_lean_path` | text |
| `score` | float |
| `created_at` | ts |

**library_index**（Library 各層 entry 索引）

| 欄位 | 型別 |
|---|---|
| `(layer, name)` | composite PK |
| `layer` | enum: Theorems / Counterexamples / Constructions |
| `name` | text；Theorems 用 `<problem>.<slug>`、Counterexamples / Constructions 用 file 相對路徑 |
| `path` | text（disk 路徑） |
| `source_root_id` | FK goals |
| `committed_at` | ts |

**events**（取代 LOG.jsonl，audit log）

| 欄位 | 型別 |
|---|---|
| `id` | PK |
| `kind` | enum（pipeline_finished / control_signal / cascade / evidence_updated / task_checkpoint / ...）|
| `payload` | json |
| `ts` | ts |

**search_cache**

| 欄位 | 型別 |
|---|---|
| `query_hash` | PK |
| `scope`, `mode` | text |
| `results` | json |
| `expires_at` | ts |

**strategist_decisions**（最新決策快取）

| 欄位 | 型別 |
|---|---|
| `id` | PK |
| `decisions` | json |
| `ts` | ts |

**schedulers**（取代 .scheduler.lock，liveness）

| 欄位 | 型別 |
|---|---|
| `id` | PK |
| `host`, `pid` | text, int |
| `started_at`, `last_heartbeat` | ts |

### 9.2 File layout

只剩 Lean source 與 Tooling。Goal/Strategy 的 metadata、digest、log、PULSE 全在 DB。

```
Asterism/
├── asterism.db
├── Library/
│   ├── Theorems/
│   │   └── proved.lean                  # 跨 Problem 共享：root proved theorems re-export
│   ├── Counterexamples/
│   │   └── <problem>_<slug>.json        # Refuted verdict（witness 或 classical）
│   └── Constructions/
│       └── <problem>_<slug>.json        # Proved-with-construction verdict（witness 或 classical）
├── Problems/
│   └── <name>/
│       ├── Root.lean
│       ├── Defs.lean
│       ├── META.md                       # Problem 配置（強制宣告 axioms 等，§8.2）
│       ├── proved.lean                   # 該 Problem 內部所有 proved Goal re-export（含 sub-Goals）
│       ├── Goals/<G_id>_<slug>/
│       │   ├── <slug>.lean              # 純 Lean，無 frontmatter（construction kind 含 spec predicate）
│       │   ├── scorer.py                # construction kind only：Python evaluator
│       │   ├── Strategies/<S_id>_<slug>.lean
│       │   ├── Staging/<p_uuid>/        # transient atomic pipeline 寫入
│       │   │   ├── context.json
│       │   │   └── *.lean
│       │   └── Tasks/<task_uuid>/       # continuous task working dir（如 ConstructionSearch）
│       │       ├── checkpoint.json      # task 自管 progress（generation / population / best）
│       │       └── candidates/*.lean    # 演化候選 staging
├── Tooling/
└── docs/
```

**Library 與 Problem 內 proved.lean 的區別**：

- `Library/Theorems/proved.lean`：跨 Problem 共享，只收 `origin='root'` + `status='proved'` 的 root theorems
- `Problems/<name>/proved.lean`：該 Problem 內部完整 re-export（含 sub-Goal proved），給其他 Problem 透過 `import Problems.<name>.Proved` 取用
- `Library/Counterexamples/`：RefutedWitness verdict 的 json witness（不是 Lean 檔）

**Staging 生命週期**

- `Staging/` 留在 disk（transient agent 輸出，pipeline 結束就刪 / commit）
- 失敗 pipeline 的 staging 直接刪，不再保留——audit 看 dead_attempts table 就夠
