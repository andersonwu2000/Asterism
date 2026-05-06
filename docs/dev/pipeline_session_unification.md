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
  goal = db.get_goal(goal_id)
  threshold = BUILDER_THRESHOLD if kind == 'Builder' else SHELVE_THRESHOLD
  budget = threshold - goal.attempts          # 動態 budget（決策 1）
  if budget <= 0:
      return PipelineResult(outcome="moot")   # 防呆、bfs_refill 應已過濾

  sid = mint_session()                        # local var、pipeline 級、不入 DB
  last_err = None

  for attempt in range(budget):
      if not goal_still_active(goal_id):      # cascade re-check
          return PipelineResult(outcome="moot")

      cold = (attempt == 0)
      # cold:  claude --session-id <sid>      # 第 1 次新 session
      # warm:  claude --resume <sid>          # 後續同 session、agent 記憶連續
      result = spawn_agent(sid, cold=cold, retry_context=last_err)

      if result.rc == 125 and not cold:       # stale_session: in-place cold mint（決策 4）
          sid = mint_session()
          result = spawn_agent(sid, cold=True, retry_context=last_err)

      if result.rc == 124:                    # timeout: postmortem + 強制 exhaust（決策 3）
          run_postmortem(sid)                 # 寫 .drafts/<kind>_g<gid>.md
          db.attempts++
          db.record_dead_attempt(reason='agent_timeout', artifacts=snapshot('.attempts/'))
          return PipelineResult(outcome="exhausted")

      outcome = parse_and_commit(result)
      if outcome.terminal:                    # proved / agent_declined / agent_infeasible
          return outcome

      db.attempts++                           # 決策 5：per-spawn ++
      db.record_dead_attempt(reason=outcome.reason,
                             artifacts=snapshot('.attempts/'))  # 決策 6：per-retry snapshot
      last_err = outcome.detail

  return PipelineResult(outcome="exhausted")  # budget 用盡、未終態

dispatcher 看到 outcome:
  proved / success / agent_declined / agent_infeasible: cascade（attempts 已 ++）
  exhausted: re-queue 下個 pipeline（fresh session）；attempts hit threshold 時
             bfs_refill 升 kind 或 cascade shelve
  moot: no-op（不動 state；goal 已終態、bfs_refill 自然不撈）
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

Model B-soft 的 pipeline 持有 pool slot 時間 = `budget × avg_spawn_time`、
budget 是該 kind 的剩餘 threshold（決策 1、dynamic、非固定）：

- Builder：上限 3 次 retry × ~6 min = ~18 min（attempts=0 第一次 dispatch）
- Backward：上限 8 次 retry × ~6 min = ~48 min（attempts=0；實務罕見、多數
  backward 1-2 次就 success / decline / infeasible 提早返回釋放 slot）

實務 avg 遠低於上限（多數 spawn 跑完就 terminal）。

對 PN 級（pool=12、active goals ~15-20）：oversubscription 比當前 cross-
pipeline 增加 ~2-3x、但仍不到 pool starvation。對深題（cantor / SG、active
goals 30+）若 throughput 退化、可調 BUILDER_THRESHOLD / SHELVE_THRESHOLD
（不引入獨立 budget knob）。本階段按現有 (3, 8) 執行、PN 驗證、深題實測再 tune。

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
  helper、含 cascade re-check、dynamic budget 計算、session resumption、
  stale_session in-place fallback
- `Tooling/pipeline/builder.py:run_builder` 改用 helper、retry loop 內部化
- `Tooling/pipeline/backward.py:run_backward` 同
- 不引入獨立 budget config（決策 1：budget = 該 kind 剩餘 threshold、
  跟既有 BUILDER_THRESHOLD / SHELVE_THRESHOLD 對齊）

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

Model B 下（決策 6）：
- `pipelines` row 仍 1 row per pipeline（內部 retry 不算獨立 pipeline）；
  `outcome` 反映最終結果（`proved` / `success` / `failed` / `exhausted` /
  `moot`）
- `dead_attempts` 1 row per failed retry attempt（保留粒度、attempts ↔
  dead_attempts 1:1、events.py 投影才能看到完整 retry 軌跡）；retry loop
  body 內 commit
- `dead_attempts.artifacts` JSON 每 retry snapshot（每次失敗前把當下
  `.attempts/<pid>/` 內容打包；retry 之間 `.attempts/` 累積、builder 失敗
  會 restore parent.lean backup、backward 失敗會 unlink 寫進的 proofs/）
- `moot` outcome **不寫** `dead_attempts`（決策 2：沒 LLM call、不算失敗）
- `spawn_fast_fail` (rc≠0 wall<10s) 行為不變（infra 噪訊）、不寫
  `dead_attempts`、不消耗 budget

## attempts counter 行為

當前：cascade_one 每次 pipeline failure 把 `goals.attempts++`。

Model B 下（決策 5）：retry loop body 內每次失敗 spawn 把 `goals.attempts++`、
跟 `dead_attempts` 1:1。cascade_one 不再做 attempts++（只做 status transition：
shelve / 升 kind）。BUILDER_THRESHOLD=3 / SHELVE_THRESHOLD=8 數值不動、
語意不變（LLM call 失敗總次數）、只是觸發點下沉到 retry loop body。
一個 goal 從 attempts=0 到 shelve 的 LLM call 總成本不變。

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

## 決策已敲定（2026-05-06）

8 個原開放決策點落定如下：

1. **`IN_PIPELINE_BUDGET` → 動態**：budget = 該 kind 的剩餘 threshold
   （Builder = `BUILDER_THRESHOLD - attempts`、Backward = `SHELVE_THRESHOLD
   - attempts`）。不引入獨立 config knob、不 hard-code 固定數字。
   理由：避免 budget 跟 cascade threshold 雙重邏輯；既有 threshold 仍是
   cascade 層 SoT、in-pipeline 只是「剩多少給我用」。

2. **`moot` outcome → uniform no-op**：dispatcher 收到 moot 不動 attempts、
   不 re-queue（goal 已終態、bfs_refill 自然不撈）；`pipelines` row 仍寫
   （outcome=`moot`、forensic 留證）；`dead_attempts` 不寫（沒 LLM 成本）。
   不主動 shelve case 2 orphan（避免破壞 F42 cross-strategy reuse）；orphan
   清理留給 prune 階段、不混進 cascade。

3. **timeout (rc=124) → 強制 exhaust pipeline**：F55 postmortem 仍跑
   （寫 `.drafts/<kind>_g<gid>.md`）；postmortem 完成後 retry loop 不繼續、
   pipeline return outcome=`exhausted`、dispatcher 重派 fresh session
   （讀 `.drafts` 接續）。仍 attempts++（timeout 是有 LLM 成本的失敗）。
   理由：timeout 表 agent 思考路徑卡死、同 session resume 會撞同卡點；
   `.drafts` 持久化的整個目的就是給 cold restart 用。

4. **stale_session (rc=125) → 不算 budget、就地 cold mint**：retry loop 內
   偵測 rc=125 且非首次 spawn → 重 mint sid + 改 cold spawn 補一次、
   不消耗 budget、不 attempts++。補的那次也失敗則按 normal failure 處理。
   理由：stale_session 是 infra 噪訊、不該扣 agent budget。

5. **`goals.attempts` 語意 → LLM call 失敗總次數**：per-spawn ++、跟
   `dead_attempts` 1:1。BUILDER_THRESHOLD=3 / SHELVE_THRESHOLD=8 數值不動、
   語意不變、觸發點從 cascade_one 下沉到 retry loop body。
   一個 goal 從 attempts=0 到 shelve 的 LLM call 總成本不變。

6. **forensic 粒度 → per-retry**：retry loop 內每次失敗 1 row dead_attempts；
   attempts ↔ dead_attempts 1:1（events.py 投影才能看到完整 retry 軌跡）；
   `dead_attempts.artifacts` JSON 每 retry snapshot（`.attempts/<pid>/` 內容）；
   `pipelines` 仍 1 row per pipeline、outcome 反映最終結果。

7. **column drop 時機 → 7-D 一次性**：7-B / 7-C 期間 `builder_session_id` /
   `backward_session_id` column 保留為孤兒（無人讀寫但合法 NULL）；7-D 一次
   drop 雙 column + 清所有 reference + tests assert。
   理由：每階段獨立可 revert（7-B revert 時 column 還在、行為回退無礙）；
   schema migration 集中在 stable phase；test 同步成本集中。

8. **F33 / F53 命名退役 → commit 標明 + docs/code 全清**：7-D commit message
   寫「F33 / F53 retired」+ 退役理由；docs/code 中所有 `F33` / `F53` 引用
   改寫為 in-pipeline retry 對應描述；不留 `(deprecated)` 標記（噪訊）。
   commit history 是天然 reasoning 保存點、`git log -S F33` 永遠搜得到。

### 核心 invariant（決策過程中額外鎖定）

- **in-pipeline retry 共用 same session**：`sid` 是 pipeline 函數的 local
  var、attempt 0 cold spawn `claude --session-id <sid>`、後續 warm spawn
  `claude --resume <sid>`、agent 記憶連續。這是把當前
  `goals.builder_session_id` column 在乾的 hack「session 跨 pipeline 接續」、
  變成 in-pipeline 的自然結果。
- **F55 postmortem 機制保留**：`.drafts/` 是 timeout/exhausted 後 cold
  restart 的接續媒介。
- **`pipelines` table 仍 1 row per pipeline**（不變）、不細分到 retry 級。

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
