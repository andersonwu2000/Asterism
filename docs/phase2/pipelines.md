# Phase 2 — Pipeline 細部 spec

`design.md` 講概念、本檔講實作介面。讀順序：先 `design.md` 拿 mental model、再回本檔找 schema / stage / DB 細節。

---

## 1. 共通約定

| 屬性 | Strategist | Forward |
|---|---|---|
| Family | Coordinator | Generator |
| 觸發 | §2.1 | 只能由 Strategist `Inject(pipeline="Forward")` |
| 輸出 | 單一 decision object | 單一 `.lean` 檔（new lemma） |
| Runtime | atomic、佔 worker pool slot、wall / retry 沿用既有 dispatch + `run_with_session_retries` | 同 |

---

## 2. Strategist

### 2.1 任務 + 觸發

| ID | 任務 | 觸發條件 |
|---|---|---|
| **T0** | First-launch + Defs.lean 初寫（若需要） | `problems.bootstrap_done = false` |
| **T1** | Routine：看局勢、決定 `Inject(...)` / `EmitDirective` / `Noop` | 每 `strategist.interval_min` 分鐘（預設 60） |
| **T2** | `pending_strategist_review` Goal 處置（不限終態判決——可 Inject Forward 先擴 library，G 留 pending、下輪再決定） | `goal_pending_review` event |
| **T3** | Defs.lean amend 提案（單一 `RequestDefsAmend` decision、一次 commit 含草稿 + 等 user） | T1 / T2 衍生 |

優先序：T2 > T0 > T1。同時最多 1 條 Strategist（不重入）。

不做：
- 決定 Backward / Builder 派誰（BFS 自動）
- 調 queue 優先序（既有 priority 機制夠用）
- 主動 health check / framework alert（未來再加）
- 開場擱置 root（Phase 2 不處理「先派 Forward 再攻 root」的場景；root 預設先試 Backward、卡住才走 T1 處理）

T0 的 `bootstrap_done` 機制 + Manifest.entry_kind 移除細節見 §4.1；trigger logic 見 §4.3。

### 2.2 Input

每次跑時依任務 compile：

| 來源 | 內容 | 用於 |
|---|---|---|
| TREE.md | 既有 problem-level tree artifact、全結構 + status + dead cause | T1（所有任務基底） |
| active_goals_sidecar | status ∈ {open, attempting, pending_strategist_review} 的 Goal 列表、含 slug + statement（截斷 200 字） | T1 |
| failure_replay | strategist_decisions 表近 5 條 + 對應 outcome | 所有任務（self-feedback） |
| review_context | 觸發的 Goal full statement + ancestor 鏈 + 失敗 reason summary + 既有 strategy 內容 | T2 |
| problem_meta | Manifest + Defs.lean | T0 / T3 |

TREE.md 給結構但缺 statement 文字；sidecar 補 active goals 的 statement、proved / shelved 不附（不會是 Inject target）。

### 2.3 Output: decision schema

**單一 decision object**（非 list）——強迫 Strategist 每次聚焦最重要的一個動作。多個動作 → 多次 Strategist 觸發、自然 self-feedback 校正方向。

兩種文字欄位：
- **`brief`**（Inject 專屬）：給下游 pipeline 的任務指示、多段 markdown、長度由 prompt 規範
- **`reason`**（其他所有 decision）：給 operator + 下次 Strategist 看的判決理由、一段 markdown、長度由 prompt 規範

兩者皆 markdown content、不做 schema CHECK、不嚴格限長。

範例：

```json
{"kind": "Inject", "pipeline": "Forward",
 "brief": "## Need\nLibrary lacks named lemmas for piecewise-smooth contour deformation.\n\n## Context\nmain (residue_thm) has been attacked 4× with `unprovable` decline. Likely missing tool: deformation across removable singularities.\n\n## Suggested angle\nPropose contour-level lemma generic over piecewise paths; useful for residue_thm and future complex-analysis goals.\n\n## Avoid\nDuplicating Mathlib's existing smooth-curve formulation."}

{"kind": "ConfirmShelve", "target_goal_id": 1480,
 "reason": "no viable approach found; statement may be open or out of scope"}

{"kind": "EmitDirective", "scope": "problem:residue_thm",
 "body": "Library now has contour_deformation_piecewise; prefer it over manual case-split."}

{"kind": "RequestDefsAmend", "problem": "residue_thm",
 "proposed_body": "...new Defs.lean draft content...",
 "question": "Manifest mentions piecewise-smooth contours but Defs.lean only abbreviates smooth case; propose adding `def Contour := ...`. Accept / reject / edit?",
 "reason": "Bootstrap-time Defs covered only smooth contours; main proof needs piecewise."}
```

完整 decision kinds：

| Kind | 作用 | 文字欄位 |
|---|---|---|
| `Inject(pipeline, brief)` | 派指定 pipeline；Phase 2 只接受 `pipeline="Forward"`；brief 是 Strategist 給 Forward 的自由描述 | `brief` |
| `ConfirmShelve(target_goal_id)` | T2：真 dead end、轉終態 shelved | `reason` |
| `Reopen(target_goal_id, directive?)` | T2：值得再試、轉回 attempting；directive 寫入 problem-level directive 欄位 | `reason` |
| `EmitDirective(scope, body)` | 寫入 `problems.strategist_directive` column、覆蓋既有；給未來下游 pipeline 看的提醒；`body` 是 directive 內容（不是 `reason`） | `body`（同時可附 `reason` 解釋決策動機） |
| `InitializeDefs(problem, lean_body)` | T0：直接寫 `Defs.lean`（檔案不存在才能用） | `reason` |
| `RequestDefsAmend(problem, proposed_body, question)` | T3：一次 commit 寫 `.proposed_defs.lean` 草稿 + emit human input request、等 user 處置（見 §2.5 + §4.3 gate） | `reason`（含 `question` 給 user） |
| `Noop` | 顯式不動 | `reason` |

**Inject 設計選擇**：
- 沒 `InjectBackward`：Backward 整路由 BFS structural refill 派、Strategist 不介入
- 沒 `target_goal_id`：Forward 不 tie 特定 Goal、產的 lemma 通用、Strategist 在 brief 自由描述需求

`strategist_decisions.target_id` 欄位給 ConfirmShelve / Reopen 用、Inject row 該欄位空。

**T2 觸發下的 decision 不受限**：T2 看到 pending_review goal、若判斷「現有 library 不夠、直接 Reopen 會再 fail」、可輸出 `Inject(Forward, brief)` 先擴 library；G 留 pending_review 等下輪。只有 `ConfirmShelve` / `Reopen` 是 G 的終態判決、其他 decision 都保留 pending 狀態。next T1 routine 把 pending goal 帶進 sidecar 重新審視。

### 2.4 Stages

```
1. trigger_context   (pure)   依觸發類型 compile 對應 input
2. failure_replay    (pure)   讀 strategist_decisions 近 5 條
3. agent             (agent)  輸出單一 decision + reasoning
4. self_verify       (pure)   schema 驗、target_goal_id 存在性
5. commit            (pure)   執行該 decision：enqueue / 寫 directive column /
                              寫 Defs.lean 或 .proposed_defs.lean / mark goal status
```

### 2.5 寫出物

| 目標 | 用途 |
|---|---|
| `strategist_decisions` 表 | 每條 decision 一 row、含 tick、kind、target、brief / reason、outcome（cascade 回填） |
| `problems.strategist_directive` column | 單一 text 欄位、覆蓋寫 |
| `problems.bootstrap_done` column | T0 commit 後設 true |
| `problems.last_strategist_at` column | 每次 Strategist commit 更新、T1 wall-clock 計算用 |
| `goals.status` | T2 commit 可改：`pending_strategist_review` → `shelved` / `attempting` |
| `Problems/<p>/Defs.lean` | `InitializeDefs` 寫入（檔案不存在時） |
| `Problems/<p>/.proposed_defs.lean` | `RequestDefsAmend` 寫入草稿 |

Inject 的 brief 不另寫檔——存 `strategist_decisions.brief` column、由被 Inject 派的 pipeline 在 cold-start 從 DB 拉出注入 Context.md 一段（見 §4.4）。

Strategist **不直接修改既有的** `Defs.lean` / `Manifest.md`——只能初寫或寫草稿。維持 CLAUDE.md「Manifest + Defs.lean 是唯一人手檔」契約。

**T3 / `RequestDefsAmend` 機制**：單一 decision、一次 commit 完成「寫草稿 + 等 user」兩件事。commit 階段做：
1. `tmp_path.write_text(proposed_body) → fsync`
2. INSERT `strategist_decisions` row（outcome 填 `awaiting_human`）
3. `os.rename(tmp_path, .proposed_defs.lean)`

任一步失敗、整個 transaction 失敗、下次重來。檔案與 row 永遠 in sync。

dispatcher gate 直接看 DB：若該 problem 存在 outcome=`awaiting_human` 的 row → 跳過所有 Strategist 觸發、等 user 把 row 改成 `accepted` / `rejected`（手動 update DB 或未來補 CLI）。

### 2.6 Self-feedback loop

`failure_replay` 拉近 5 條 decisions（含 outcome）、agent 看 trace 學「上次 X、結果 Y」。不需 explicit reward signal。

---

## 3. Forward

### 3.1 任務 + 觸發

讀 Strategist 的 brief（自由 markdown 描述當前需求）+ 看 Library 與 Mathlib state、產出**一條**新 `kind=theorem` Goal（含 statement + sorry stub）進池、之後由 Backward / Builder 攻。產出的 lemma 應該是 framework 認為 known-true、且通用、預期多個未來 Goal 都可援引。

只能由 Strategist 的 `Inject(pipeline="Forward")` decision 觸發。`bfs_refill` 不主動派。

**Dedup**：每 problem 同時最多 1 條 Forward in-flight（dispatcher 檢查、避免並發產出衝突或重複 domain 探索）。

### 3.2 Input

| 來源 | 內容 |
|---|---|
| Strategist brief | Inject 帶來的描述（domain / 卡點 / 角度建議）、由 compile_context 注入 Context.md 一段 |
| Library state | 同 problem + cross-problem 已 proved 的 lemma 名單 + 簽名 |
| Mathlib | lemma_lookup 拿候選相關 lemma 簽名 |
| forward_history | 該 problem 過去 Forward 結果（防重複提案） |
| TREE.md（precompiled）| problem 結構概覽、agent 可看哪個方向卡住 |

Forward agent 不 tie 任何特定 Goal——根據 brief 自行判斷該補什麼。

### 3.3 Output

**單一 `.lean` 檔**——跟 Backward 產出 sub-goal 結構一致：agent 在 attempts_dir 寫 `new_<slug>.lean`、內含 theorem statement + `:= by sorry`。Pipeline 驗 + 落到 `Problems/<p>/proofs/L_<slug>.lean`、INSERT goal（kind=theorem、status=open）、之後由 Backward / Builder 攻。

範例 `new_contour_deformation_piecewise.lean`：

```lean
-- Forward rationale: bridge between Mathlib's smooth-curve contour
-- lemmas and the piecewise case needed for residue-style integrals.
import Mathlib

theorem contour_deformation_piecewise (γ : ℝ → ℂ) ... : ... := by sorry
```

leading comment 的 `Forward rationale:` 寫入 goal.evidence 欄位、後續 Strategist self-feedback 可讀到。

新 lemma 是**獨立 Goal**、`origin=forward`、不掛任何 target 下方。多輪 Forward 由 Strategist 在不同 T1 觸發中各別 inject、之間夾 Backward 攻擊、自然形成迭代。

### 3.4 Stages

```
1. failure_replay   (pure)   讀 problem 過去 Forward 結果（避免重複提案）
2. compile_context  (pure)   寫 Context.md（含 Strategist brief + Library + Mathlib 候選
                              + TREE.md 概覽）
3. agent            (agent)  在 attempts_dir 寫 new_<slug>.lean（statement + sorry body）
4. self_verify      (pure)   .lean 檔 type-checks（leading sorry OK）
5. dedupe           (pure)   跨 Library + alive Goals 去重（沿用既有 find_canonicals_batch）
6. commit           (pure)   move 到 proofs/L_<slug>.lean、INSERT goal
                              (kind=theorem, origin=forward, target_id=NULL)
```

Context.md 跟 Backward / Builder 同模式（既有 `compile_context` 擴出 Forward 變體）、brief 直接成為 Context.md 內一段。`new_<slug>.lean` 落地路徑沿用 backward.py 內既有 helper。

### 3.5 防亂提兩道防線

1. **dedupe**：跟既有 alive / proved 重複的直接濾掉、轉 `forward_no_new_goal`（detail = `dedupe blocked`）
2. **Strategist self-feedback**：上次 Forward 結果差 → 下次 Strategist 不再 InjectForward

---

## 4. Infrastructure 改動

### 4.1 DB schema

| Table | 改動 |
|---|---|
| `pipelines.kind`、`queue.kind` | enum 加 `Strategist`、`Forward` |
| `pipelines.target_id` | 允許 null（Forward case；既有 Backward / Builder 仍非空） |
| `queue.decision_id` | 新欄位、int nullable、FK strategist_decisions(id)；非空表示此項由某 Inject decision 派出、pipeline cold-start 拉 brief 注入 Context.md |
| `goals.origin` | enum 加 `forward` |
| `goals.status` | enum 加 `pending_strategist_review`、`cascade_shelved` |
| `problems.bootstrap_done` | 新欄位、boolean default false |
| `problems.strategist_directive` | 新欄位、text nullable、長度由 prompt 約束（不做 schema CHECK） |
| `problems.last_strategist_at` | 新欄位、ts nullable、用於 T1 wall-clock 計算 |
| `strategist_decisions` | 新表（見下） |
| `Manifest.entry_kind` 欄位 + `## Entry kind` section | **刪除**（強制 Strategist 預設、不再 user-configurable） |
| cli init | 改插入 `problems.bootstrap_done=false`、不再讀 Manifest entry_kind |

`goals.entry_kind` 不擴 enum——Forward 產的新 Goal 預設 `Backward`（如 Backward agent 寫 sub-goal 一樣、leaf-適合直接攻就標 `Builder`）。

**SQLite CHECK 約束 migration 注意**：擴 `pipelines.kind` / `queue.kind` / `goals.status` / `goals.origin` 這幾個帶 CHECK 的 enum、SQLite 不支援 ALTER 既有 CHECK。必須走 table-rebuild（`CREATE TABLE new_X` 帶新 CHECK → `INSERT SELECT FROM X` → `DROP X` → `RENAME new_X TO X`、保留 FK 重建）。既有 `init_schema` 用的 `ALTER TABLE ADD COLUMN` 對純加欄位 OK、但 enum 擴張必須走 rebuild、在 dispatcher 啟動的 migration 步驟做、需測試 rollback 路徑。

**`cascade_shelved` 跟 `shelved` 的差別**：
- `shelved`：agent 或 Strategist 主動判定該 Goal dead end、未來不再嘗試。**dedupe 會擋**形狀相同的新 Goal 提案（#112 機制）、防止 agent 提同樣 statement。
- `cascade_shelved`：parent 被 ConfirmShelve 時、descendants 連帶 shelve 釋放 BFS。**dedupe 不擋**——descendants 本身可能有獨立價值、未來 Forward 提類似 lemma 不該被擋。BFS 同樣 skip、prune 同樣清檔。
- dedupe 實作改：既有 `_eligible_shelved`（dedupe.py）只看 `status='shelved'`、不看 `cascade_shelved`。

`strategist_decisions`：

| 欄位 | 型別 |
|---|---|
| `id` | PK |
| `triggered_at_tick` | int |
| `trigger_kind` | enum (`first_launch` / `pending_review` / `routine`) |
| `decision_kind` | enum (見 §2.3 列表) |
| `target_id` | int nullable |
| `brief` | text nullable（Inject 用、其他 decision 為空） |
| `reason` | text nullable（非 Inject decision 用、Inject 為空） |
| `payload` | json（其他結構化參數、如 `pipeline` 字串、`scope`、`topic` 等） |
| `outcome` | text nullable (cascade 回填) |
| `created_at`, `updated_at` | ts |

### 4.2 Cascade 規則改動

**新規則 1（agent_shelved 不再直接 terminal）**：

```
when failure_reason == agent_shelved AND goal.status in ('open','attempting'):
    goal.status ← 'pending_strategist_review'
    enqueue Strategist (kind=Strategist, target=problem.root)
    (不直接 cascade 上游、等 Strategist review 後依結論再 cascade)
```

直接 enqueue Strategist、不走 events 表（Asterism 目前無 event bus、polling 機制重）。dedup 靠既有 in-flight (kind, problem) 檢查。

**新規則 2（ConfirmShelve 雙向 cascade）**：

```
ConfirmShelve(G) commit:
    1. 上游：沿用既有 _propagate_shelve（G → parents → ... 走 strategy AND/OR 規則）
    2. 下游：walk G 的所有 descendants（透過 strategy_subgoals）、
            把 status ∈ {open, attempting, pending_strategist_review} 的全改 cascade_shelved
            （不改 proved / shelved / 已 cascade_shelved 的、避免覆蓋 terminal）
```

下行用新 status `cascade_shelved` 而非 `shelved`：descendants 本身可能有獨立價值、未來 Forward 提類似 lemma 不該被 dedupe 擋（見 §4.1 status 差別說明）。

**新規則 3（Reopen 安全閘）**：

```
Reopen(G) commit:
    1. self_verify 前：walk G 的 ancestors、若任一 ancestor 狀態 ∈ {shelved, cascade_shelved}：
       → 拒絕該 decision、agent 必須改 ConfirmShelve（ancestors terminal、Reopen 會 orphan G）
    2. 通過後：goal.status ← 'attempting'、若 directive 不空寫入 problems.strategist_directive、re-enqueue
```

`pending_strategist_review` 不算 terminal（Strategist 還在 review）、可以是 ancestor。

### 4.3 Dispatcher 改動

T0 / T1 / T2 觸發邏輯：

| Trigger | 偵測 |
|---|---|
| T0 | 任一 problem `bootstrap_done=false` → enqueue Strategist（target=該 problem root） |
| T1 | 任一 problem 最後 Strategist 完成至今 ≥ `strategist.interval_min` 分鐘、且 root 非 terminal → enqueue Strategist |
| T2 | `goal_pending_review` event → 即時 enqueue Strategist |

優先序 T2 > T0 > T1（同 tick 多 trigger 時遵守）。

其他：
- Strategist queue 獨立優先（高於普通 Backward / Builder、低於 Verify housekeeping）
- `bfs_refill` 不主動派 Forward（必須 explicit inject）
- Forward 同 problem 同時最多 1 條 in-flight（per-problem dedup、非 per-(target,kind)）
- `pending_strategist_review` 狀態的 Goal **不入 bfs_refill 候選**
- 若該 problem 存在 `strategist_decisions` row、`decision_kind=RequestDefsAmend` 且 `outcome='awaiting_human'`、跳過所有 Strategist 觸發（T0/T1/T2 都不 enqueue）、Backward / Builder / Forward 也暫停。operator 把 outcome 改成 `accepted` / `rejected` 後恢復 dispatch（手動 DB update 或未來補 CLI；無新 schema column）
- Strategist 失敗（schema_invalid 等）走 `_INFRA_REASONS` 路徑、不 burn root.attempts

### 4.4 Context.md 整合（directive + brief）

`compile_context`（Backward / Builder / Forward 共用）注入兩段：

| 段名 | 來源 | 何時出現 |
|---|---|---|
| `## Strategist directive` | `problems.strategist_directive`（非空時） | 所有 pipeline cold-start（problem-level、覆蓋寫、無 expire） |
| `## Strategist brief` | `strategist_decisions.brief`（透過 `queue.decision_id` FK 查） | 該 pipeline 由 Inject 派出時（per-pipeline one-shot） |

BFS 自動派的 pipeline 無 decision_id、只附 directive 段。純資料注入、不改 prompt 措辭。

### 4.5 新 failure_reason / event_type

failure_reason：

| reason | 說明 |
|---|---|
| `strategist_noop` | Noop decision 的乾淨退出（infra-reason、不 burn attempts） |
| `strategist_schema_invalid` | self_verify 失敗（infra-reason、不 burn attempts） |
| `forward_no_new_goal` | Forward 沒新 Goal 進池——含兩種：agent 主動 decline（Library 已足夠）/ 提案全被 dedupe 擋。具體哪種記在 failure_detail |

events：`strategist_decision_committed`（每條 decision commit 後 emit、給 dashboard / log 用）。其他狀態變化（goal pending_review、awaiting_human）靠 cascade 直接 enqueue 或 DB row 存在性 gate、不發 event。

---

## 5. 參數

| 參數 | 預設 | 用途 |
|---|---|---|
| `strategist.interval_min` | 60 | T1 routine 間隔（分鐘、wall-clock） |

可在 Asterism.yaml 覆寫、env var 也支援。其他常數（failure_replay window=5、單一 decision / 單一 lemma 上限、reason / directive 長度）寫死實作、不暴露。

---

## 6. 延後 / 不做

| 項目 | 處置 | 原因 |
|---|---|---|
| `ReformulateGoal(target, new_statement)` | 延後 Phase 2.5+ | 需要 cluster relation 護欄、且不可用於 root |
| `PauseGoal` / `UnpauseGoal` decisions | 延後 Phase 2.5+ | 配套「先派 Forward、暫不攻 root」場景、Phase 2 不開 |
| 新 agent decline directive（如 `needs_review`） | 不加 | 沿用既有 `shelve`、cascade 規則處理差異 |
| 通用 `RequestHumanInput` decision（非 Defs 場景） | 不開 | 目標最小化人類介入；Phase 2 只 `RequestDefsAmend` 一個 human-input 入口、其他狀況 Strategist 自決 |
| `HealthCheck / FrameworkAlert` | 不做 | Phase 2 先不做、未來若需要再加 |
| `DetectCircularSubgoaling` 專用 decision | 不做 | 由 `EmitDirective` 涵蓋 |
| 「subtree stuck」事件觸發 Strategist | 不做 | T1 wall-clock routine 順便處理、Strategist agent 自己看 inventory 判斷 |
| Forward outcome 事件觸發 Strategist | 不做 | 同上、Phase 2 不開 forward_finished event |
| 「queue idle」事件觸發 Strategist | 不做 | T1 wall-clock 涵蓋；queue idle 沒事做就讓系統等下次 routine |

---

## 7. 實作期細節（落地時決定、設計階段不 lock）

設計層概念已 lock、以下實作細節等寫程式時 calibrate：

- **Forward `target_id=NULL` 在 cascade 入口的分支**：既有 `_run_pipeline` 直接 `int(target_id)`、Forward target=null 要新 branch（target_kind=None / 略過 goal-row lookup）
- **Strategist 失敗 retry 策略**：Strategist 無 root.attempts 概念、`_INFRA_REASONS` route 主要保證不 burn ancestor、但 retry / cooldown 細節由 `_retry.py` 介面決定（最簡：Strategist 失敗即終止本次、下次 trigger（T1 wall-clock 或 T2 event）再來）
- **`asterism strategist resume <problem>` CLI**：實作細節 — 是 sub-command 還是 flag、是否支援 `--all`、是否要先 prompt 確認用戶看過 `.proposed_defs.lean`
- **`forward_no_new_goal` 兩個 producer 路徑**：
  - (a) agent 主動 decline：stage 3 寫一個 decline 文件（同 backward 既有 decline directive 機制）、stage 4 self_verify 認得、commit 不 INSERT、回 `forward_no_new_goal` + detail `agent declined: library sufficient`
  - (b) dedupe 全擋：stage 5 把 agent 提的 lemma 都濾掉、commit 不 INSERT、回 `forward_no_new_goal` + detail `dedupe blocked`
- **migration 順序**：cli reset 先清 queue（含 decision_id refs）再清 strategist_decisions、避免 FK orphan
