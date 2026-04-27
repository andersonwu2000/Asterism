# Phase 3 — Cache

## 目標

P2 的 Backward / Builder 已經能跑通拆解 + 證明，但每次都「裸跑」——同一 sub-Goal 可能被不同分支重複拆、Backward agent 沒看過去失敗就一直撞同樣的牆、IH-trap 要等到 `D_max` 才被兜底。
P3 引入 Search / Dedupe subsystem、`failure_replay` 接真實 dead_attempts、IH-trap signal、`blocked_pipelines` 自動寫入機制。
**這 phase 是性能 + correctness 雙修**：cache 與 dedupe 省 token，IH-trap 與 blocked_pipelines 防無限燒。

## Scope

### In

- **Search subsystem**（v3 §4.1）
  - `search_cache` table、query_hash 構造（impl §2.2）
  - TTL per scope（impl §2.1）：mathlib 3600s / library 3600s / local_goals 300s / inventory 30s
  - Mutation invalidation 觸發 catalog（impl §2.3）：goals INSERT/UPDATE → 殺 local_goals + dedupe；library 寫入 → 殺 library scope
  - 暴露為 stage（`find_lemmas` / `find_subgoals` / `find_pattern` / `find_mathlib`）+ 暴露為 agent tool（agent stage 內可動態呼叫）
  - 實作：Lean exe `tools/search.lean`（mathlib + library scope 用 elab 找 declaration）+ Python 端 SQL（local_goals scope 直接查 goals table）+ search_cache 中間層
- **Dedupe subsystem**（v3 §4.2）升級
  - `tools/dedupe.lean` 完整版（impl §7.1）：strict mode 走 `Lean.Meta.isDefEq`、iff_lite mode opt-in 跑 simp/decide
  - elaborate 失敗 → 回 NOVEL 容錯
  - cache 走 mutation invalidation
  - 取代 P2 的 statement_hash 簡化版
- **failure_replay 接實**（impl §6.1 SQL）：拉真實 dead_attempts 摘要餵進 Backward / Builder agent prompt
  - K_digest=5 預設
- **IH-trap 偵測**（v3 §7.5）
  - Backward commit 時對每個新 sub-Goal 算 `parent_subgoal_max_similarity`、寫入 strategies row（**啟用 P1 預留欄位、不是新加 schema**）
  - similarity metric 由 spike 決定（候選：token Jaccard / identifier overlap / AST diff）
  - **Strategist 仍未啟用**——P3 把 metric 算出來、寫入 DB，當作 P7 Strategist signal 的素材；P3 內不消費
- **blocked_pipelines 自動寫入機制**（v3 §9.1 goals.blocked_pipelines）
  - 啟用 P1 預留 `goals.blocked_pipelines` json 欄位（預設 `[]`）
  - 兩條規則並存（明確互動）：
    1. **通用**：任一 pipeline kind 對單一 Goal 連 `N_block_after_failures=5` 次 outcome ∈ **{exhausted, unproductive}** → 寫入。**Builder 的 `needs_decomp` / `bad_goal` 不計入**——前者是預期的「請拆」分支、後者是 sub-Goal 級教訓（語意不同；對父 Goal 寫 dead_attempts 由 P2 已處理）
    2. **IH-trap 強信號 special-case**：Strategy 連續 ≥ 2 次 unproductive AND `parent_subgoal_max_similarity ≥ ih_trap_similarity_threshold` → 立即寫入 `['Backward']`（不等 N=5）
  - Counter 走 SQL（**不是 in-memory**）：每次 failure_archive 跑時 `SELECT COUNT(*) FROM dead_attempts WHERE target_id=? AND pipeline_kind=? AND outcome IN ('exhausted','unproductive')`，達 N → CommitWriter UPDATE goals.blocked_pipelines
  - **JSON list patch 防 race**：UPDATE 走 SQLite `json_patch` + WHERE clause 比對 commit_state（避免兩個 pipeline 同時觸發 lost update）；獨立 spike-011 驗 SQLite 對 json_patch 的 atomicity；不夠則加 application-level lock
  - Counterexample 暫不存在（P4 才有），但 Backward / Builder 已有，所以 P3 起 Backward / Builder 都會觸發
  - structural refill 與（未來的）Strategist inject 都查 blocked_pipelines 過濾
  - **人工 unblock CLI**：`asterism goal unblock <G_id> <pipeline_kind>` / `asterism goal unblock <G_id> --all`（純 SQL UPDATE 移除 list 內 entry，P3 demo 期人類撞到誤封 Goal 救援用）
- **Cascade rules dispatch 表覆蓋範圍明確**：dispatch 表只覆蓋直接 effect（status flip / cancellation / library promotion 等 (pipeline_kind, outcome) → CascadeAction 形式）。**Cascade upward propagation 不入 dispatch 表**——「sub-Goal proved → 下個 cycle structural refill 偵測 Strategy 全 sub-Goal proved → enqueue Builder」是隱含鏈，仍走 P2 的 BFS 偵測機制（v3 §6 cascade upward 段）
- **Cascade rules dispatch 表**（impl §10.2「Cascade rules 中央 dispatch 表」設計模式）
  - P2 cascade 寫死成 if-else 鏈，P3 重構成 `cascade_table: dict[(pipeline_kind, outcome), list[CascadeAction]]`
  - **覆蓋範圍見上「Cascade rules dispatch 表覆蓋範圍明確」段**——只直接 effect、cascade upward 不入表
  - **`CascadeAction` 結構預留 `target_ids: list[id]` 參數**（不是單一 target_id），P3 暫時所有 action 都 single-target，但 forward-compat 給 P4 twin propagation 用（cancel 同時影響 G + ¬G 兩個 target_id）
  - 為 P4–P7 加新 pipeline 鋪路，避免每次動 reactor 主迴圈
- **Reactor cycle 補齊 step 1（liveness check）**（v3 §6 step 1）
  - 處理事件前過濾：對應 Goal/Strategy 已被 cascade 標 dead/refuted 的事件丟棄、被主動 kill 的 pipeline 結果丟棄
  - P2 沒做、所以 P2 處理 stale 事件可能跑些無謂的 cascade；P3 補
- **Reactor cycle step 5（Strategist 觸發判定）留 stub**——v3 §6 step 5 的完整實作在 P7；P3 起在 reactor 主迴圈該位置加空 hook function（`maybe_trigger_strategist()` no-op）+ TODO 註記，避免 P7 真實實作時動 reactor 主迴圈結構

### Out

- Strategist pipeline（P7 才完整啟用；P3 把 IH-trap signal 算出來但暫無消費者）
- Refuter / Counterexample / Forward / Generalizer / ConstructionSearch
- Multi-Problem
- Library promotion
- Trust set 內 `kind=computational`
- Cache 對未實作的 scope（construction、Forward 用的 `find_pattern` 留 P5/P7）

## Demo

兩個 demo，分別驗 dedupe 與 IH-trap。

### Demo D1：dedupe 共享 sub-Goal

兩個 root 都要拆出共同 sub-lemma `l ++ [] = l`（避開 trivial / rfl 直接證得的 case，否則 Backward 不會拆，dedupe 無從驗證）：

```bash
asterism init --problem dedupe_demo
# Defs.lean 內容範本：import Mathlib（讓 Goal .lean 共享 List 操作）

asterism goal add --problem dedupe_demo --slug demo_a --kind theorem \
  --spec "∀ l : List Nat, (l ++ []) ++ l = l ++ l"
asterism goal add --problem dedupe_demo --slug demo_b --kind theorem \
  --spec "∀ l : List Nat, l ++ ([] ++ l) = l ++ l"
# 兩個 root 都需要 sub-Goal `l ++ [] = l`（demo_a 化簡左側）或 `[] ++ l = l`（demo_b 化簡右括號內）
# 取決於 Backward agent 的拆解選擇——典型結果：兩者都拆出 `l ++ [] = l`，dedupe 撈到既有

asterism run
# 預期：
#   Backward(demo_a) 拆出 sub-Goal G_x: "l ++ [] = l"
#   Backward(demo_b) 拆解時 dedupe (local) 偵測 sub-Goal 跟 G_x α-equiv → claim 既有
#   Builder(G_x) 跑一次（by simp 過）；demo_b 的 strategy 直接 reference G_x（strategy_subgoals.subgoal_id = G_x.id）
```

### Demo D2：IH-trap 提前抓到

具體 IH-trap 例子（從 Hadamard `sylvester_gallai L0005` 撈，Backward 拆解時 sub-Goal 形式跟父幾乎相同——換 P 為 P.erase x、形成 IH 不可呼叫）。Demo 用 Mathlib 既有 `Affine.Collinear` / `EuclideanSpace`，Defs.lean 範本與 Goal .lean 落 `docs/demo/sg/ih_trap_demo.lean.tmpl`：

```bash
# Problems/dedupe_demo/Defs.lean 範本（已建）：
#   import Mathlib.Analysis.InnerProductSpace.EuclideanDist
#   import Mathlib.LinearAlgebra.AffineSpace.AffineSubspace
#   open EuclideanSpace Affine

asterism goal add --problem dedupe_demo --slug ih_trap_demo --kind theorem \
  --spec-file docs/demo/sg/ih_trap_demo.lean.tmpl
# tmpl 內容：
#   import Problems.dedupe_demo.Defs
#   theorem ih_trap_demo : ∀ (P : Finset (EuclideanSpace ℝ (Fin 2))),
#       3 ≤ P.card →
#       (∀ p q ∈ P, p ≠ q → ∃ r ∈ P, Collinear ℝ ({p, q, r} : Set _)) →
#       ∃ p q ∈ P, ∀ r ∈ P, r = p ∨ r = q ∨ ¬ Collinear ℝ ({p, q, r} : Set _) := by sorry

asterism run
# 預期：
#   Backward 拆出 sub-Goal，similarity 寫入 strategies.parent_subgoal_max_similarity
#   連續第 2 次 Backward 對同 Goal exhausted/unproductive AND similarity ≥ threshold
#   → 自動寫 blocked_pipelines += ['Backward']
#   structural refill 不再對該 Goal 派 Backward
#   Goal 留 attempting（P3 沒 Strategist 主動 Shelve）
```

CLI `--spec-file <path>` 是 P3 新 flag（給長 / 含特殊符號 statement 用）；`--spec` 仍接 inline string。

## Acceptance criteria

0a. **Demo D1 end-to-end**：上面 §Demo D1 整段 bash 跑完、SQL `SELECT COUNT(*) FROM strategy_subgoals WHERE subgoal_id = G_x` ≥ 2（兩個 root strategy 共用同一 sub-Goal）。**這是 D1 的 single sanity gate**——直接驗共用行為、不靠 wall-clock noisy metric
0b. **Demo D2 end-to-end**：上面 §Demo D2 整段 bash 跑完、第 2 次 Backward 失敗後 30s 內 `goals.blocked_pipelines` 含 `'Backward'`、第 3 cycle 起 BFS 不 enqueue 該 Goal 的 Backward
1. **Cache hit**：對同一 query 連跑 2 次（在 TTL 內）→ 第 2 次走 cache，無 subprocess 呼叫。pytest 用 `SEARCH_MOCK=record_calls` env hook 計次（對齊 P1 `COMMIT_FAULT` 風格）
2. **Cache invalidation**：INSERT goals 後對應 local_goals scope 的 cache row 被刪除（SQL 直接驗）。**P6 multi-Problem 上線時補 acceptance**：「Problem A INSERT 不殺 Problem B 的 local_goals cache row」（P3 cache 邏輯 forward-compatible、impl §2.3 的 `WHERE problem_scope='X'` 機制 P3 就要寫對，P6 才有測試對象）
3. **Dedupe Lean exe**：對 `∀ x, P x` 與 `∀ y, P y` 比 → strict mode 回 hit；對 `f x = g x` 與 `g x = f x` → strict miss、iff_lite hit
4. **Dedupe elaborate 失敗容錯**：餵含 sorry 的 candidate → dedupe 回 NOVEL 不報錯
5. **failure_replay**：對 Goal 連跑兩次 Backward 都 exhausted → 第三次跑時 agent prompt 內含前兩次 dead_attempts 摘要。**驗法**：agent stage 寫的 prompt 落地檔（`Staging/<p_uuid>/context.json` 內 `prompt` 欄位）pytest 直接讀，比對含 dead_attempts summary 字串
6. **IH-trap special-case 抓到**：Demo D2 場景，連 2 次 unproductive AND similarity ≥ threshold → blocked_pipelines 立即寫入（不等 N=5）
6a. **通用 N=5 trigger**：人為注入 Goal 連 5 次 Backward exhausted（透過 `BACKWARD_FORCE=exhausted` env mock）→ blocked_pipelines 寫入；驗 IH-trap special-case 與通用 trigger 兩條規則互不干擾
7. **blocked_pipelines 過濾**：手動在 goals 表寫 `blocked_pipelines=['Backward']` → 對應 Goal 不再被 enqueue
8. **Cascade dispatch 表**：cascade rules 改寫成 dispatch 表後，P2 的 acceptance test 全 pass（無迴歸）。CI 迴歸 gate 規則見 `phases.md` §跨 phase 規則
9. **Liveness check**：對已被 cascade 標 dead 的 Strategy 對應的 stale Builder pipeline_finished 事件 → reactor 丟棄、無多餘 cascade
10. **In-memory cap 移除（functional check）**：跑 P2 acceptance #11 fixture 在 P3 codebase 上 → fixture 預期「重啟後重試一輪」**fail**（即重啟後仍跳過、持久化版生效）。grep 不用做 acceptance（脆弱、重命名變數即誤報），lint 階段順手檢查即可

## 依賴

### 前置 phase

- P1 + P2 完成

### 必跑 spike

- **spike-008 IH-trap similarity metric**——P2 demo theorem + 一兩個 IH-trap 已知案例，比較三個 metric（token Jaccard / identifier overlap / AST diff）的 false positive / false negative 率。決定 `ih_trap_similarity_threshold` 預設值
- **spike-009 Lean.Meta.isDefEq 性能**——對 Mathlib 內 100 條 lemma 跑 dedupe，測 wall-clock 與 token 量級（dedupe.lean subprocess overhead）。決定是否需 batch 化或 daemon 化；順帶驗 iff_lite false positive
- **spike-010 search_cache hit rate 估算**——P2 跑過的 Backward / Builder log 跑模擬 cache，看 hit rate（以決定 cache 設計值不值）
- **spike-011 SQLite json_patch atomicity**——兩個 process 同時對同一 row 跑 `UPDATE goals SET blocked_pipelines = json_patch(blocked_pipelines, ?) WHERE id=? AND commit_state='live'` 是否 atomic / 會不會 lost update？決定 blocked_pipelines 寫入是否需 application-level lock（影響 §In blocked_pipelines 機制 race 防護）

## 引入元件

### Subsystem

- **Search**：`tools/search.lean` + Python 端 cache 包裝（`Tooling/subsystems/search.py`）
- **Dedupe**：`tools/dedupe.lean` 完整版（**完全取代** P2 statement_hash 簡化版——P2 simple-hash code 從 codebase 刪除，遵守「不寫孤島模組」）

### Test infrastructure

- `SEARCH_MOCK` env hook（test-only，新增）：mode ∈ `{record_calls, force_miss, force_hit}`，對齊 P1 `COMMIT_FAULT` 風格給 pytest 控制 search subsystem 行為
- `BACKWARD_FORCE` env hook（test-only，新增）：mode ∈ `{exhausted, unproductive, succeed}`，給 acceptance #6a 跑通用 N=5 trigger 用

### DB table（啟用 P1 預留 schema）

P1 schema 已含全部 v3 §9.1 表與欄位（codex review #12 決策）。**P3 不擴 schema**——只是開始消費：

- `search_cache`：P3 起真實寫入（P1 schema 預留、P2 不消費）
- `strategies.parent_subgoal_max_similarity`：P3 起 Backward commit 時計算寫入
- `goals.blocked_pipelines`：P3 起 failure_archive / IH-trap special-case 寫入

### Config

| key | P3 預設 |
|---|---|
| `K_digest` | 5（P2 沿用） |
| `ih_trap_similarity_threshold` | spike-008 結果決定（暫填 0.85） |
| `N_block_after_failures` | 5 |
| dedupe.lean subprocess timeout | 30s |
| iff_lite check timeout（per pair） | 5s |
| cache TTL：mathlib | 3600s |
| cache TTL：library | 3600s |
| cache TTL：local_goals | 300s |
| cache TTL：inventory | 30s |

### Stage 升級

- `failure_replay`：stub → 真實 SQL 查 dead_attempts
- `find_lemmas`：stub → cache 包裝 + Lean exe（mathlib + library scope）
- `find_subgoals`：stub → cache 包裝 + SQL（local_goals scope）
- `dedupe (local)` in Backward：statement_hash 比 → dedupe.lean strict mode

### Reactor

- Cascade rules 改寫成 dispatch 表（為 P4 鋪路）
- 補 step 1 liveness check
- structural refill 加「IH-trap 兜底」：查 strategies similarity 連續 unproductive 的 case 寫 blocked_pipelines

## 任務序列

DB 端 P3 不需 schema migration（P1 已建全 schema、§引入元件 §DB table 段已說明），任務序列只列實作動作：

1. **spike-008 / 009 / 010 / 011 跑完**——結果落 `docs/spikes.md`
2. **`tools/dedupe.lean` 完整版**（對齊 impl §7.1）；**完全取代** P2 statement_hash code（從 codebase 刪除、不留 fallback config switch——遵守「不寫孤島模組」；若 spike-009 顯示 dedupe.lean 慢得不能用就回頭升級 P3 plan，不是把 hash 留在 codebase）
3. **`tools/search.lean`** + Python 端 cache 包裝（`Tooling/subsystems/search.py`）
4. **Cache mutation invalidation hooks**：CommitWriter `finalize()` 加 `cache.invalidate(scope_filter)` 鉤子；P3 觸發點 goals INSERT/UPDATE → 殺 local_goals + dedupe。**Library 寫入觸發點 P6 才接上**（P3/P4/P5 沒 Library promotion code path）
5. **failure_replay stage 接實**（`Tooling/stages/failure_replay.py`）
6. **find_lemmas / find_subgoals stage 接實**（`Tooling/stages/find_*.py`）
7. **Backward dedupe (local) 換成 dedupe.lean 呼叫**
8. **IH-trap 計算**：Backward commit hook 加 similarity 算法（依 spike-008 結果），寫入 strategies row
9. **blocked_pipelines 機制（兩條規則並存）**：
    - 通用：failure_archive stage 跑時 SQL `COUNT(*) FROM dead_attempts WHERE target_id=? AND pipeline_kind=? AND outcome IN ('exhausted','unproductive')`，達 `N_block_after_failures=5` → CommitWriter UPDATE goals.blocked_pipelines。Builder `needs_decomp` / `bad_goal` outcome 不計入（§In 規格）
    - IH-trap special-case：similarity 計算後直接判 「Strategy 連續 ≥ 2 次 unproductive AND parent_subgoal_max_similarity ≥ threshold」 → 立即 UPDATE blocked_pipelines（不等 N=5）
    - JSON list patch 走 SQLite `json_patch` + WHERE commit_state='live' 防 race（spike-011 驗 atomicity；不夠則 application-level lock）
    - structural refill / 未來 Strategist inject 加過濾
10. **移除 P2 in-memory retry cap**：刪除 P2 reactor 內 `failure_count: dict[(goal_id, pipeline_kind), int]` 與相關 BFS 過濾；持久化版完整取代
11. **Cascade dispatch 表重構**（`Tooling/cascade.py`）：覆蓋直接 effect；cascade upward 仍走 BFS 偵測機制（§In 明列）
12. **Reactor step 1 liveness check 補上**
13. **Reactor step 5 stub**：`maybe_trigger_strategist()` no-op + TODO 註記，P7 補真實邏輯
14. **CLI 擴**：`asterism goal unblock <G_id> <pipeline_kind>` / `--all`（人工救援誤封 Goal）；`asterism goal add --spec-file <path>`（取代 inline `--spec` 對長 statement）
15. **Test infrastructure**：`SEARCH_MOCK` / `BACKWARD_FORCE` env hook（test-only）
16. **Demo D1 / D2 跑通 + acceptance test 寫成 pytest**

## 測試

- **Unit**：dedupe.lean 對 strict / iff_lite / elaborate fail 三 case
- **Unit**：search_cache hit / miss / TTL 過期 / mutation invalidation 各 case
- **Unit**：similarity metric 對人為製造的 IH-trap pair / 非 IH-trap pair 各驗
- **Integration**：Demo D1 token 量對照（兩 root vs 單 root）
- **Integration**：Demo D2 IH-trap 提前抓到
- **Integration**：blocked_pipelines 阻擋後續 enqueue
- **Stress**：開大 graph（人為注入 100 個 root）測 search_cache 命中率

## 風險與 open questions

- **similarity metric 沒 ground truth**：spike-008 只能憑「直覺像不像 IH-trap」決定，threshold 可能要 P4 / P7 真實跑過 conjecture 後再調
- **dedupe.lean 對 quantifier-heavy statement 慢**：spike-009 結果若顯示 isDefEq subprocess overhead 太大（如 > 5s），dedupe (local) 變成 Backward 的 bottleneck。應變：dedupe stage 限 timeout 直接 NOVEL fallback、後續再被 cache 抓
- **search Lean exe 啟動 overhead**：每次 subprocess 啟動 Lean elab 要幾秒。spike-010 會驗。應變：搞個常駐 daemon mode 的 Lean executable + IPC（這是大工程，留待 P5/P6 真有需要再做）
- **blocked_pipelines 過早封死**：N_block_after_failures=5 可能對某些難命題太緊（一連 5 次 exhausted 後就再也不試了）。Counter 是否要分 sliding window？P3 先用 hard 5 + 人工 unblock CLI（`asterism goal unblock` 已落 §In / 任務序列 #14）；P4/P5 真實跑過再調
- **iff_lite false positive**：simp / decide 在弱 setup 下可能誤判等價。spike-009 順便驗
- **Cache mutation invalidation 漏點**：所有寫入 goals / library 的點都要記得呼 invalidate；P3 暴露點少（Backward / Builder commit + 未來 Library promotion），漏的話 cache 給 stale 結果。應變：CommitWriter `finalize()` 統一鉤子
