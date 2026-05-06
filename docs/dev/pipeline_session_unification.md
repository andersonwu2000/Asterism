# Pipeline / Session 統一 — retry model 從 cross-pipeline 改 in-pipeline-bounded

Status: planned (2026-05-06). 架構整頓 phase、要在 BRIEF.md / LESSONS.md
落地前完成、避免後續 phase 再 stacking 在錯誤心智模型上。

## 動機

當前代碼的「pipeline」「session」「retry」三層概念邊界錯配、是過去演化累積的
技術債、需要正本清源：

- **代碼裡**：pipeline = 一次 `run_builder`/`run_backward` call = 一次 LLM
  spawn。retry 由 dispatcher 重派下個 pipeline、跨 pipeline 用 `goals.
  builder_session_id` / `backward_session_id` column 攜帶 claude session id
  讓下個 pipeline 用 `--resume` 接續同個 agent 對話（F33 / F53 mechanism）。
- **使用者心智模型**：pipeline 呼叫 = 一個 agent session 把該 goal 處理完
  （含內部 retry）。pipeline 結束 = session 結束。

兩個 model 運行邏輯等價、但概念邊界顯著不同。當前實作是把「session 跨多
pipeline」**用 session_id column 硬接起來**、F33/F53 等命名本身就是補丁的
證據。

不整頓的代價：

1. 後續 phase（BRIEF.md / LESSONS.md / Strategist / Forward / Generalize）的
   reflection / pipeline-end / session-terminal 等概念都會被現有錯位影響、
   設計 doc 必須持續解釋「pipeline ≠ session、需要靠 session_id column」、
   生 cognitive overhead。
2. 新增 pipeline kind（Refuter / Counterexample / ConstructionSearch、v3
   archive 規劃）每種都要實作 cross-pipeline session 攜帶、邏輯複製。
3. cascade rule、SHELVE_THRESHOLD、F33/F53、F55 postmortem 等機制邊界混
   亂、debug 痛苦（PN run 時數次出現「session 何時被清」「下次 pipeline 是
   warm 還是 cold」相關 confusion）。

## 目標：Model B-soft

```
pipeline 入口（run_builder / run_backward）
  sid = mint_session()      # local var、不存 DB
  for attempt in range(IN_PIPELINE_BUDGET):  # e.g. 3
      if cascade_changed_status(goal_id):   # sibling proved / shelved / etc
          return PipelineResult(outcome="moot")
      spawn agent (sid, is_retry=(attempt > 0), retry_context=last_err)
      result = parse + lake_build + commit
      if result.proved or result.terminal:
          return result
      attempts_in_db += 1
      record dead_attempt（含本次 retry context、forensic 粒度同現在）
  return PipelineResult(outcome="exhausted")  # in-pipeline budget 到、未終態

dispatcher 看到 outcome:
  proved / shelved / decline / infeasible: 標記 goal、cascade
  exhausted: re-queue 為下個 pipeline（fresh session、新 sid）
  goal.attempts >= SHELVE_THRESHOLD: shelve 整 goal
```

核心對應：

| 概念 | Model B-soft 邊界 |
|---|---|
| Pipeline | 一次 session 的容器、跑到 proved / terminal / budget 用盡 |
| Session | 跟 pipeline 同邊界、agent 對話 lifetime = pipeline 內部 |
| In-pipeline retry | session 內 LLM call 重試（同 sid + `--resume`） |
| Cross-pipeline retry | session 用盡、下個 pipeline = fresh session（新 sid、cold start） |
| F33 / F53 | 不存在、退役名稱、自然行為 |
| `goals.builder_session_id` / `backward_session_id` column | 移除 |

## 為何 Model B-soft 是長期正解

### 1. 心智模型對齊

「pipeline 處理一個 session 的 lifecycle」是 agent-centric 的自然 framing。
當前 cross-pipeline + session_id column 是把 session 概念硬塞進 scheduler-
centric 的 pipeline 抽象、造成解釋負擔。

### 2. 移除冗餘 DB state

session_id column 跨 pipeline 攜帶 claude session 編號、純粹是當前架構的
workaround。Model B 把 sid 收進 pipeline 函數的 local var、無 DB column、
無 lifecycle 邏輯（何時 set / 何時 clear）。**一個 column 砍、5-6 處 set/
clear site 全消失**。

### 3. 邏輯下沉、共享 helper

新增 pipeline kind 不需要再各自處理 cross-pipeline session 攜帶。共享
`run_with_session_retries(...)` helper 做 cascade re-check + retry budget +
session resumption、所有 pipeline kind 用同一份。

### 4. Reflection 觸發點清晰

`agent_brief_lessons.md` 設計的 reflection spawn 該在 pipeline terminal
觸發。Model B 下「pipeline terminal = session terminal」是 by definition、
不需特別解釋「為何只在 success pipeline 觸發」。

### 5. 對齊未來 pipeline 多樣化

v3 archive 規劃 8 種 pipeline kind。Model B 下每個 pipeline kind 的「session
邊界」邏輯一致、可 generalize。Model A 下每個 kind 都要實作 cross-pipeline
session 攜帶、邏輯複製。

## Pool slot trade-off（明確認知）

Model B-soft 的 pipeline 持有 pool slot 的時間 = `IN_PIPELINE_BUDGET ×
avg_spawn_time` ≈ 3 × 6 min = ~18 min。當前 cross-pipeline 平均 ~6-10 min。

對 PN 級（pool=12、active goals ~15-20）：oversubscription 程度增加 ~2-3x、
但仍不到 pool starvation 等級。**緩解 knob = `IN_PIPELINE_BUDGET`、可 tune**。

對深題（cantor / SG、active goals 30+）：可能需要降 budget（e.g. 2）或加大
pool。本階段先設 budget=3、PN 驗證、深題實測再 tune。

## 移除 / 改名 list

### 移除的代碼

- `goals.builder_session_id` / `goals.backward_session_id` column（DB schema
  migration、bump 版本）
- `db.get_builder_session_id` / `set_builder_session_id` 等 column accessor
  helper（4 個函數）
- 同 backward 版（4 個函數）
- F33 mechanism 的 session-id 跨 pipeline 攜帶程式碼（4 個 set/clear sites
  in builder.py）
- 同 backward 版（6 個 sites in backward.py）
- `_fetch_last_builder_error` / `_fetch_last_backward_error`（retry_context
  從 in-pipeline `last_err` local var 直接拿、不再從 DB 撈上一次失敗）

### 新增 / 改寫的代碼

- `Tooling/pipeline/_retry.py`（新模組）：`run_with_session_retries(...)`
  helper、含 cascade re-check、retry budget、session resumption
- `Tooling/pipeline/builder.py:run_builder` 改用 helper、retry loop 內部化
- `Tooling/pipeline/backward.py:run_backward` 同
- `IN_PIPELINE_BUDGET` config（dispatch.in_pipeline_budget、預設 3、env
  override `ASTERISM_IN_PIPELINE_BUDGET`）

### 名稱退役

- `F33` / `F53` 兩個 feature flag 編號退役（functionality 內部化、不再是獨立
  feature）。docs / 註解中所有 `F33` / `F53` 引用全部清理或改成「same-session
  retry within pipeline」。
- `_fetch_last_builder_error` 等改名 / 移除。

## Cascade re-evaluation helper

當前由 dispatcher tick 之間隱含完成的 cascade 安全性、改用顯式 helper 在
retry loop 內每次重試前執行：

```python
def goal_still_active(conn, goal_id) -> bool:
    """Cascade re-check: 確認 goal 還在 retry-able 狀態（open / attempting）、
    沒被 sibling 證掉、沒被 parent 上拋 shelve、沒到 SHELVE_THRESHOLD。
    """
    fresh = db.get_goal(conn, goal_id)
    if fresh is None: return False
    if fresh["status"] not in ("open", "attempting"): return False
    if fresh["attempts"] >= SHELVE_THRESHOLD: return False
    return True
```

retry loop 每次 spawn 前 call 一次。這個 helper 是新 pipeline kind 都會用
的共享資源、放 `Tooling/pipeline/_retry.py`。

## Forensic / dead_attempts 行為

當前每個 pipeline 結束（success or fail）寫一筆 `pipelines` row + 失敗時
一筆 `dead_attempts` row。

Model B 下：
- pipelines row 仍是 1 row per pipeline（內部 retry 不算獨立 pipeline）
- dead_attempts 仍是 1 row per failed retry attempt（**保留粒度、不退步**）
  → 在 retry loop 內部 commit 每次 dead_attempt
- pipelines.outcome 反映最終 outcome（proved / failed / exhausted / moot）

代價：retry loop 內部要做 db.record_dead_attempt 不是只在 pipeline 結束
做。一兩行的事、不複雜。

## attempts counter 行為

當前：cascade_one 每次 pipeline failure 把 `goals.attempts++`。

Model B 下：retry loop 內部每次失敗 attempt 都要 `goals.attempts++`、
保持 SHELVE_THRESHOLD 邏輯不變。Pipeline 級的 attempts 累計變成「budget 用
盡 = goals.attempts += BUDGET 次」。

## 實作順序（建議）

phase 拆分：

1. **PHASE 7-A**：抽 retry helper、定義邊界
   - 新建 `Tooling/pipeline/_retry.py`、`goal_still_active` + `run_with_
     session_retries` 骨架
   - 新增 config knob `dispatch.in_pipeline_budget`
   - 不改 builder.py / backward.py、helper 暫無 caller

2. **PHASE 7-B**：builder.py 改 in-pipeline retry
   - `run_builder_inner` 改為 helper 包覆的 retry loop
   - 移除 F33 session_id 跨 pipeline 攜帶（builder 端）
   - dispatcher.cascade 端對應調整（builder 不再期待 session_id 持久）
   - `goals.builder_session_id` column **保留先**（避免 schema 改動 + 其他
     code 同時動）
   - 跑 PN 驗證

3. **PHASE 7-C**：backward.py 改 in-pipeline retry
   - 同 builder、symmetric
   - F53 session_id 跨 pipeline 攜帶（backward 端）退役

4. **PHASE 7-D**：移除 session_id column
   - schema migration（drop columns）
   - 砍 db.py / context.py 等所有引用 column 的程式碼
   - 砍 retry tests 中對 column 的 assertion
   - 跑 全 test suite + PN 驗證

5. **PHASE 7-E**：docs 同步
   - architecture.md：新增「Pipeline = session lifecycle」一節、舊「F33/F53」
     段落退役註記
   - data-flow.md：retry flow 圖更新
   - failure_modes.md：retry-related 描述更新
   - dev/goal_history_unified.md / dev/agent_brief_lessons.md / 其他 dev 設計
     doc 反映新 model

每階段獨立 commit、可獨立 revert。

## 受影響 tests

需要重寫 / 大改的 test files（粗估）：

- `tests/test_pipeline_backward_retry.py`：F53 session_id 跨 pipeline 攜帶
  完全改設、retry 不再跨 pipeline、改測 in-pipeline retry budget 行為
- `tests/test_pipeline_builder.py`：F33 同上
- `tests/test_dispatcher.py`：attempts counter 增加 / cascade 邏輯邊界調整
- `tests/test_infeasible_escape.py`：少量更新（cascade 行為一致）
- `tests/test_builder_decline.py`：少量更新

新增 test：

- `tests/test_pipeline_retry_helper.py`：cover `goal_still_active` +
  `run_with_session_retries` helper 行為
- in-pipeline budget 各邊界 case（hits budget、cascade bail mid-loop、
  proved on retry N 等）

## 受影響 docs

- `architecture.md` §6 dispatcher 主迴圈、§7 cascade rules、§13 不變量
- `data-flow.md` §3.1 / §3.2 / §6 等 pipeline 流程描述
- `failure_modes.md` 整體 reread、retry 相關描述更新
- `STATUS.md` header / 近期落地 / next session
- `dev/agent_brief_lessons.md` reflection 觸發點重述為「pipeline terminal =
  session terminal」、移除「success pipeline terminal」這個半補丁措辭
- `dev/goal_history_unified.md` 若有引用 F33/F53 處更新
- `dev/goal_naming_annotation.md` 若有引用更新

## 開放決策點（next session 起手回答）

1. **`IN_PIPELINE_BUDGET` 預設值**：3 / 5 / 7 哪個？衡量 session 連貫性 vs
   pool fairness。傾向 3（保守起步、PN 驗證後再 tune）。
2. **「moot」outcome 的處理**：Pipeline 因 cascade bail（goal 已 shelved /
   proved by sibling）回 outcome="moot"。dispatcher 接到 moot 後是 cascade
   no-op 還是清 attempts？傾向 no-op、attempts 不增（goal 已終態、不該再
   懲罰）。
3. **timeout (rc=124) 的處理**：當前 timeout → F55 postmortem → 該 pipeline
   結束 → 下次 dispatch fresh session。Model B 下 timeout 該不該佔 retry
   budget 的一格、還是視同 session 必須結束（pipeline return exhausted、
   讓 dispatcher fresh session）？傾向後者（timeout 表示 agent 卡死、繼續同
   session 沒意義）。
4. **stale_session (rc=125) 的處理**：當前 in-pipeline mint 新 sid 重試
   一次。Model B 下自然行為（retry loop 下一輪 mint 新 sid）、不需特例邏
   輯。退役當前 fallback 程式碼。
5. **`goals.attempts` 的語意**：當前 = pipeline 失敗次數 = 跟 SHELVE_THRESHOLD
   比。Model B 下 = retry attempt 失敗次數（含 in-pipeline retry）。語意
   一致、但比較尺度從「pipeline 數」變成「LLM call 數」、SHELVE_THRESHOLD
   數值要重新考慮。傾向保留當前數字、實證調整。
6. **forensic per-retry 還是 per-pipeline**：當前 dead_attempts 一條 per
   pipeline failure。Model B 下保留同粒度（per failed retry）、要在 retry
   loop 內部 commit 多筆。確認這沒違反任何 invariant（spot-check
   `events.py` 投影邏輯）。
7. **session_id column drop 時機**：PHASE 7-D 才動 schema、還是 7-B 就動？
   傾向 7-D（避免 builder/backward 半轉狀態下 column 既存又無用）。
8. **`F33` / `F53` 命名退役如何記錄**：commit message 標明退役、docs 全清
   引用、保留 commit history 即可。不需 deprecation period（內部代碼、非
   公共 API）。

## 不做（當前階段）

- 不改 dispatcher 的 worker pool 模型（仍 ThreadPoolExecutor、pool size
  不動、cancellation propagation 不引入）
- 不引入 priority queue / preemption（當前 BFS-style refill 保留）
- 不改 cascade rule 本身（cascade event types 不變、只改 retry trigger 點）
- 不引入 cross-problem session sharing（每 problem 獨立、跟現在一樣）

## 跨參考

- 當前實作：`Tooling/pipeline/builder.py:run_builder_inner`、`Tooling/
  pipeline/backward.py:run_backward`、`Tooling/db.py:set_builder_session_id`
  / `set_backward_session_id`
- F33 / F53 mechanism docs：`docs/architecture.md` §0 status table、F33/F53
  各條
- F55 timeout postmortem：`Tooling/pipeline/__init__.py:_attempt_postmortem`
  （Model B 下保留行為、但 trigger 邏輯內部化）
- 後續 dependency：`docs/dev/agent_brief_lessons.md`（reflection 觸發點需
  Model B 才清晰落地）
- 業界對照：K8s Job retry、Airflow task retry、Temporal workflow retry —
  scheduler-managed retry as separate task instances 是 Asterism 當前做法、
  但 Asterism 跟那些系統的關鍵差別是 agent session continuity 是核心、
  scheduler-managed retry 反而強加邊界。Asterism 的「pipeline = session」
  選擇對 agent-driven 系統更合理。

## 為何此刻就要做、不能延後

1. `agent_brief_lessons.md` 的 reflection trigger 設計依賴 pipeline /
   session 邊界清晰、Model B 落地後 trigger 點是 by-definition 自然點、不需
   半補丁措辭
2. 後續 Strategist / Forward / Generalize 等新 pipeline kind 若在 Model A
   上開工、每個都要實作 cross-pipeline session 攜帶邏輯、再整頓成本翻倍
3. 用戶監管早期沒抓到、現在抓到、不在更多 phase stacking 後做 → 工程量會
   隨後續 phase 數量線性增長
