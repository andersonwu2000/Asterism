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
| **T3** | Manifest / Defs.lean amend 提案（單一 `RequestUserAmend(file)` decision、一次 commit 含草稿 + 等 user） | T1 / T2 衍生 |

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

{"kind": "RequestUserAmend", "problem": "residue_thm", "file": "Defs.lean",
 "proposed_body": "...new Defs.lean draft content...",
 "question": "Manifest mentions piecewise-smooth contours but Defs.lean only abbreviates smooth case; propose adding `def Contour := ...`. Accept / reject / edit?",
 "reason": "Bootstrap-time Defs covered only smooth contours; main proof needs piecewise."}

{"kind": "RequestUserAmend", "problem": "residue_thm", "file": "Manifest.md",
 "proposed_body": "...new Manifest.md draft content...",
 "question": "Manifest's `## Approach hints` section currently misleads — it suggests `MeasureTheory.integral_congr_ae` but the proof needs the piecewise variant. Propose replacing with named lemma list. Accept / reject / edit?",
 "reason": "Manifest hint led 3 Backward attempts down a dead-end strategy; updating hint will redirect future attempts."}
```

完整 decision kinds：

| Kind | 作用 | 文字欄位 |
|---|---|---|
| `Inject(pipeline, brief)` | 派指定 pipeline；Phase 2 只接受 `pipeline="Forward"`；brief 是 Strategist 給 Forward 的自由描述 | `brief` |
| `ConfirmShelve(target_goal_id)` | T2：真 dead end、轉終態 shelved | `reason` |
| `Reopen(target_goal_id, directive?)` | T2：值得再試、轉回 attempting；directive 寫入 problem-level directive 欄位 | `reason` |
| `EmitDirective(scope, body)` | 寫入 `problems.strategist_directive` column、覆蓋既有；給未來下游 pipeline 看的提醒；`body` 是 directive 內容（不是 `reason`） | `body`（同時可附 `reason` 解釋決策動機） |
| `InitializeDefs(problem, lean_body)` | T0：直接寫 `Defs.lean`（檔案不存在才能用） | `reason` |
| `RequestUserAmend(problem, file, proposed_body, question)` | T3：一次 commit 寫 `.proposed_<file>` 草稿 + emit human input request、等 user 處置（見 §2.5 + §4.3 gate）。`file` ∈ {`'Defs.lean'`, `'Manifest.md'`}——皆是 user-owned 檔、Strategist 不可直接改 | `reason`（含 `question` 給 user） |
| `Noop` | 顯式不動 | `reason` |

**Inject 設計選擇**：
- 沒 `InjectBackward`：Backward 整路由 BFS structural refill 派、Strategist 不介入
- 沒 `target_goal_id`：Forward 不 tie 特定 Goal、產的 lemma 通用、Strategist 在 brief 自由描述需求

`strategist_decisions.target_id` 欄位給 ConfirmShelve / Reopen 用、Inject row 該欄位空。

**Reopen 的 `directive` 欄位落點**：Reopen decision JSON 的 `directive`（optional）存入 `strategist_decisions.payload` JSON 內、不另建 column。commit 階段若該欄位非空、同時寫入 `problems.strategist_directive`（覆蓋既有）。`EmitDirective` 的 `body` 同樣走 payload JSON、`Inject` 的 `pipeline` 字串也是 payload；payload 是所有 non-text-content 結構化參數的共用 bag。

**T2 觸發下的 decision 不受限**：T2 看到 pending_review goal、若判斷「現有 library 不夠、直接 Reopen 會再 fail」、可輸出 `Inject(Forward, brief)` 先擴 library；G 留 pending_review 等下輪。只有 `ConfirmShelve` / `Reopen` 是 G 的終態判決、其他 decision 都保留 pending 狀態。next T1 routine 把 pending goal 帶進 sidecar 重新審視。

### 2.4 Stages

```
1. trigger_context   (pure)   依觸發類型 compile 對應 input
2. failure_replay    (pure)   讀 strategist_decisions 近 5 條
3. agent             (agent)  輸出單一 decision + reasoning
4. self_verify       (pure)   schema 驗、target_goal_id 存在性
5. commit            (pure)   執行該 decision：enqueue / 寫 directive column /
                              寫 Defs.lean 或 .proposed_<file> / mark goal status /
                              set goals.detached
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
| `Problems/<p>/.proposed_<file>` | `RequestUserAmend(file)` 寫入草稿（`<file>` ∈ Defs.lean / Manifest.md）|

Inject 的 brief 不另寫檔——存 `strategist_decisions.brief` column、由被 Inject 派的 pipeline 在 cold-start 從 DB 拉出注入 Context.md 一段（見 §4.4）。

Strategist **不直接修改既有的** `Defs.lean` / `Manifest.md`——只能初寫或寫草稿。維持 CLAUDE.md「Manifest + Defs.lean 是唯一人手檔」契約。

**T3 / `RequestUserAmend` 機制**：單一 decision、一次 commit 完成「寫草稿 + 等 user」兩件事。commit 階段做：
1. `tmp_path.write_text(proposed_body) → fsync`
2. INSERT `strategist_decisions` row（outcome 填 `awaiting_human`、`payload.file` 記載目標檔名）
3. `os.rename(tmp_path, .proposed_<file>)`——`<file>` 從 decision payload 取（`Defs.lean` 或 `Manifest.md`）

任一步失敗、整個 transaction 失敗、下次重來。檔案與 row 永遠 in sync。

dispatcher gate 直接看 DB：若該 problem 存在 outcome=`awaiting_human` 的 row → 跳過所有 Strategist 觸發、等 user 把 row 改成 `accepted` / `rejected`（手動 update DB 或未來補 CLI）。同一 problem 同時只允許一個 awaiting_human row（避免 Defs.lean 跟 Manifest.md 草稿同時等審、user 可能 cross-edit 衝突）；Strategist self_verify 階段檢查、若該 problem 已有 awaiting_human row 則拒絕新 RequestUserAmend。

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
3. agent            (agent)  在 attempts_dir 寫 new_<slug>.lean（statement + sorry body
                              或 sorry-free 完整 proof）
4. self_verify      (pure)   .lean 檔 type-checks（leading sorry OK；偵測是否 sorry-free）
5. dedupe           (pure)   跨 Library + alive Goals 去重（沿用既有 find_canonicals_batch）
6. commit           (pure)   move 到 proofs/L_<slug>.lean、INSERT goal
                              (kind=theorem, origin=forward；goals 表本身無 parent 欄位、
                              「Forward 產的、無上游」靠 origin=forward 識別)；
                              若 self_verify 偵測 sorry-free → goal.status='proved'、
                              不入 BFS（leaf-bypass、跟 Backward sorry-free patch.lean 機制對稱）
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
| `pipelines.target_id` | 保持 TEXT NOT NULL。Forward 用 `target_kind='Problem'` + `target_id=<problem_name>`（已是 TEXT、不衝突；見 migration_plan §C 選項 1）。Strategist target=problem.root.id 跟既有 Backward/Builder 同 |
| `pipelines.target_kind` | CHECK 加 `'Problem'`（既有 `'Goal'`/`'Strategy'`） |
| `queue.target_kind` | **新欄位** TEXT NOT NULL DEFAULT `'Goal'` CHECK(`'Goal'`/`'Strategy'`/`'Problem'`)。既有 queue 表無此欄位、dispatcher 用 queue.kind 推斷；Phase 2 為 Forward 顯式化 |
| `queue.decision_id` | 新欄位、int nullable、FK strategist_decisions(id)；非空表示此項由某 Inject decision 派出、pipeline cold-start 拉 brief 注入 Context.md |
| `goals.origin` | enum 加 `forward` |
| `goals.status` | enum 加 `pending_strategist_review`、`disproved`（既有 `shelved` 語義改、見下） |
| `goals.detached` | 新欄位、boolean default 0；Strategist Reopen 時若 ancestor 鏈斷、framework 自動設 1；BFS 把 detached=1 row 視同有 alive parent strategy、正常 dispatch |
| `problems.bootstrap_done` | 新欄位、boolean default false |
| `problems.strategist_directive` | 新欄位、text nullable、長度由 prompt 約束（不做 schema CHECK） |
| `problems.last_strategist_at` | 新欄位、ts nullable、用於 T1 wall-clock 計算 |
| `strategist_decisions` | 新表（見下） |
| `Manifest.entry_kind` 欄位 + `## Entry kind` section | **刪除**（強制 Strategist 預設、不再 user-configurable） |
| cli init | 改插入 `problems.bootstrap_done=false`、不再讀 Manifest entry_kind |

`goals.entry_kind` **全部保留、機制不動**——dispatcher 路由（`next_worker_kind`）、`prompts/backward*.md` 教 agent 寫 `-- entry_kind:` directive、`backward.py` 子目標 directive 解析、`db.SCHEMA goals.entry_kind` CHECK / migration、`update_goal_entry_kind` helper 全保留。Phase 2 只動三點：(a) `manifest.entry_kind` 欄位 + `## Entry kind` section + `manifest.py` parser、(b) `cli init` 不再讀 Manifest、root 寫死 `entry_kind='Backward'`、(c) Forward 產的新 Goal 預設 `entry_kind='Backward'`（leaf-適合直接攻就標 `Builder`、跟 Backward agent 寫 sub-goal 同邏輯）。

**SQLite CHECK 約束 migration 注意**：擴 `pipelines.kind` / `queue.kind` / `goals.status` / `goals.origin` 這幾個帶 CHECK 的 enum、SQLite 不支援 ALTER 既有 CHECK。必須走 table-rebuild（`CREATE TABLE new_X` 帶新 CHECK → `INSERT SELECT FROM X` → `DROP X` → `RENAME new_X TO X`、保留 FK 重建）。既有 `init_schema` 用的 `ALTER TABLE ADD COLUMN` 對純加欄位 OK、但 enum 擴張必須走 rebuild、在 dispatcher 啟動的 migration 步驟做、需測試 rollback 路徑。

**`disproved` 跟 `shelved` 的差別**（依 agent decline directive 分流）：
- `disproved`：agent 以 `unprovable` decline 關閉（給了 counterexample、statement 在此 scope 下為假）。**dedupe 會擋**形狀相同的新 Goal 提案、防 agent 提同樣 statement、Strategist 不 review。
- `shelved`：軟終態、可被 Strategist `Reopen`。**dedupe 不擋**——statement 在其他 scope 下可能有用、未來 Forward 提類似 lemma 不該被擋。涵蓋三條路徑：
  - agent decline `return_to_parent` → 直接 `shelved`（Phase 1 行為保留、無 Strategist review）
  - agent decline `shelve` → `pending_strategist_review` → Strategist `ConfirmShelve` → `shelved`
  - Strategist `ConfirmShelve(G)` 上行 cascade 觸發 descendants → `shelved`
- BFS 同樣 skip 兩種終態；prune 同樣清檔。
- dedupe 實作：`_eligible_shelved`（dedupe.py）只看 `status='disproved'`、不看 `shelved`。（原 helper 名稱可保留、語義改、或重新命名 `_eligible_disproved`。）

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

**新規則 1（agent decline 依 directive 分流）**：

實際 failure_reason 命名（見 `Tooling/pipeline/__init__.py:381` `DECLINE_TO_FAILURE_REASON`）：directive `unprovable` → `agent_infeasible`、`return_to_parent` → `parent_needs_fix`、`shelve` → `agent_shelved`、`needs_decomposition` → `agent_declined`。

```
when goal.status in ('open','attempting'):
    if failure_reason == agent_infeasible:    # directive `unprovable`
        goal.status ← 'disproved'
        _propagate_shelve(goal_id)            # 上游 cascade 沿用、descendants 走 Rule 2
    elif failure_reason == agent_shelved:     # directive `shelve`
        goal.status ← 'pending_strategist_review'
        enqueue Strategist (kind=Strategist, target=problem.root)
        (不直接 cascade 上游、等 Strategist review 後依結論再 cascade)
    elif failure_reason == parent_needs_fix:  # directive `return_to_parent`
        goal.status ← 'shelved'                # Phase 1 行為保留、無 Strategist review
        _propagate_shelve(goal_id)
```

`agent_infeasible`：agent 給了 counterexample、語義硬終態、直接 `disproved`、dedupe 之後會擋同形狀提案、不走 Strategist。
`agent_shelved`：agent 卡住無 counterexample、需 Strategist 判決、進 `pending_strategist_review`。enqueue 直接走 queue（無 event bus）、dedup 靠既有 in-flight (kind, problem) 檢查。
`parent_needs_fix`：父策略修了就能證、Phase 1 維持直接 shelve。`agent_declined`（Builder needs_decomposition）走既有 entry_kind switch 路徑、不在本規則範圍。

**新規則 2（ConfirmShelve 雙向 cascade）**：

```
ConfirmShelve(G) commit:
    G.status ← 'shelved'
    1. 上游：沿用既有 _propagate_shelve(G)（殺 parent strategies、attempts++、必要時 recurse）
    2. 下游：新 helper _cascade_shelve_descendants(G)：BFS walk strategy_subgoals、
            把後代 goal.status ∈ {open, attempting, pending_strategist_review} 的全改
            shelved（不改 proved / shelved / disproved 的、避免覆蓋 terminal）
```

實作備註：既有 `_propagate_shelve` 只殺 strategies + 觸發父 goal 的 attempts++、**不改 sub-goal status**。`_cascade_shelve_descendants` 是 ConfirmShelve 專用的新邏輯、與 `_propagate_shelve` 平行呼叫、互不替代。

下行用 `shelved`（軟終態）而非 `disproved`：descendants 本身沒被獨立判過、statement 在他處可能有用、未來 Forward 提類似 lemma 不該被 dedupe 擋（見 §4.1 status 差別說明）。同樣的 `shelved` 也涵蓋 `parent_needs_fix` 和 Strategist `ConfirmShelve` 三條路徑、一致語義。

**新規則 3（Reopen 安全閘 + auto-detach）**：

```
Reopen(G) commit:
    1. self_verify 前：walk G 的 ancestors、若任一 ancestor 狀態 ∈ {disproved}：
       → 拒絕該 decision、agent 必須改 ConfirmShelve（counterexample 已證 ancestor 為假、
         descendant 用該結論的論證都沒效）
    2. 通過後：
        a. goal.status ← 'attempting'
        b. 檢查 G 的 strategy_subgoals 鏈、若任一 ancestor strategy 是 dead/superseded
           （即上行鏈到 root 斷掉、G 是 orphan）→ goal.detached ← 1
        c. 若 directive 不空寫入 problems.strategist_directive、re-enqueue
```

`pending_strategist_review` 不算 terminal、可以是 ancestor。`shelved` ancestor **允許 Reopen 通過**——跟「shelved=可重開」語義一致。若上游 strategy 鏈斷、framework 自動把 G 標 `detached=1`、BFS 把 `detached=1` row 視同有 alive parent strategy、正常 dispatch。proof 完成後 G 就是一條獨立的 proved lemma、未來其他 Goal 透過 dedupe-alias 機制可援引。Strategist 不必為 chain 是否斷掉煩心、Reopen 一發即可。

設計選擇：把「鏈斷自動獨立」做進 framework、Strategist 不用在 Reopen / Inject(Forward) 之間糾結。Reopen 表達「這個 statement 值得攻」、framework 處理「怎麼讓它能被攻」。

### 4.3 Dispatcher 改動

T0 / T1 / T2 觸發邏輯：

| Trigger | 偵測 |
|---|---|
| T0 | 任一 problem `bootstrap_done=false` 且 root 非 terminal → enqueue Strategist（target=該 problem root）。Root 已 proved / shelved / disproved 的不算（與 T1 條件對齊）。 |
| T1 | 任一 problem 最後 Strategist 完成至今 ≥ `strategist.interval_min` 分鐘、且 root 非 terminal → enqueue Strategist |
| T2 | `goal_pending_review` event → 即時 enqueue Strategist |

優先序 T2 > T0 > T1（同 tick 多 trigger 時遵守）。

其他：
- Strategist queue 獨立優先（高於普通 Backward / Builder、低於 Verify housekeeping）
- `bfs_refill` 不主動派 Forward（必須 explicit inject）
- Forward 同 problem 同時最多 1 條 in-flight（per-problem dedup、非 per-(target,kind)）
- `pending_strategist_review` 狀態的 Goal **不入 bfs_refill 候選**
- `goals.detached=1` 的 Goal **視同有 alive parent strategy**、入 bfs_refill 候選；既有 `open_goals` walks the alive-strategy DAG 機制要加 `OR detached=1` 一條短路（見 §4.2 規則 3）
- 若該 problem 存在 `strategist_decisions` row、`decision_kind=RequestUserAmend` 且 `outcome='awaiting_human'`、跳過所有 Strategist 觸發（T0/T1/T2 都不 enqueue）、Backward / Builder / Forward 也暫停。operator 把 outcome 改成 `accepted` / `rejected` 後恢復 dispatch（手動 DB update 或未來補 CLI；無新 schema column）。同一 problem 同時只允許一個 awaiting_human row
- Strategist 失敗（schema_invalid 等）走 `_INFRA_REASONS` 路徑、不 burn root.attempts

`_INFRA_REASONS` 目前重複定義於 `dispatcher.py` 與 `backward.py`。Phase 2 順手抽到 `Tooling/pipeline/_infra.py` 共用 module、新增 `strategist_noop` / `strategist_schema_invalid` 兩 reason 同時收編、避免再 drift（pre-existing tech debt、Phase 2 拼一起改）。

### 4.4 Context.md 整合（directive + brief）

`compile_context`（Backward / Builder / Forward 共用）注入兩段：

| 段名 | 來源 | 何時出現 |
|---|---|---|
| `## Strategist directive` | `problems.strategist_directive`（非空時） | 所有 pipeline cold-start（problem-level、覆蓋寫、無 expire） |
| `## Strategist brief` | `strategist_decisions.brief`（透過 `queue.decision_id` FK 查） | 該 pipeline 由 Inject 派出時（per-pipeline one-shot） |

BFS 自動派的 pipeline 無 decision_id、只附 directive 段。純資料注入、不改 prompt 措辭。

### 4.5 新 failure_reason

| reason | 說明 |
|---|---|
| `strategist_noop` | Noop decision 的乾淨退出（infra-reason、不 burn attempts） |
| `strategist_schema_invalid` | self_verify 失敗（infra-reason、不 burn attempts） |
| `forward_no_new_goal` | Forward 沒新 Goal 進池——含兩種：agent 主動 decline（Library 已足夠）/ 提案全被 dedupe 擋。具體哪種記在 failure_detail |

Asterism 無 event bus（既有 `events.py` 是把 DB row 投影成 Event object、供 Context.md 用、非 pub/sub）。Phase 2 不引入 event 機制：decision audit 直接讀 `strategist_decisions` 表、狀態變化靠 cascade 直接 enqueue + DB row 存在性 gate。

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
| 通用 `RequestHumanInput` decision（user-owned 檔以外的場景） | 不開 | 目標最小化人類介入；Phase 2 只 `RequestUserAmend(file)` 一個 human-input 入口、其他狀況 Strategist 自決 |
| `HealthCheck / FrameworkAlert` | 不做 | Phase 2 先不做、未來若需要再加 |
| `DetectCircularSubgoaling` 專用 decision | 不做 | 由 `EmitDirective` 涵蓋 |
| 「subtree stuck」事件觸發 Strategist | 不做 | T1 wall-clock routine 順便處理、Strategist agent 自己看 inventory 判斷 |
| Forward outcome 事件觸發 Strategist | 不做 | 同上、Phase 2 不開 forward_finished event |
| 「queue idle」事件觸發 Strategist | 不做 | T1 wall-clock 涵蓋；queue idle 沒事做就讓系統等下次 routine |

---

## 7. 實作期細節（落地時決定、設計階段不 lock）

設計層概念已 lock、以下實作細節等寫程式時 calibrate：

- **Forward `target_kind='Problem'` 在 `_run_pipeline` 的分支**：既有 `_run_pipeline` 對 target 直接 `int(target_id)` 查 goal row。Forward target_id 是 problem name string、要新 branch（target_kind='Problem' → 查 problems 表、略過 goal-row lookup）。cli reset 的 `DELETE FROM pipelines WHERE target_kind=...` 也要涵蓋 'Problem' 路徑（見 migration_plan §C）
- **Strategist 失敗 retry 策略**：Strategist 無 root.attempts 概念、`_INFRA_REASONS` route 主要保證不 burn ancestor、但 retry / cooldown 細節由 `_retry.py` 介面決定（最簡：Strategist 失敗即終止本次、下次 trigger（T1 wall-clock 或 T2 event）再來）
- **`asterism strategist resume <problem>` CLI**：實作細節 — 是 sub-command 還是 flag、是否支援 `--all`、是否要先 prompt 確認用戶看過 `.proposed_<file>`（Defs.lean / Manifest.md 都可能）
- **`forward_no_new_goal` 兩個 producer 路徑**：
  - (a) agent 主動 decline：stage 3 寫一個 decline 文件（同 backward 既有 decline directive 機制）、stage 4 self_verify 認得、commit 不 INSERT、回 `forward_no_new_goal` + detail `agent declined: library sufficient`
  - (b) dedupe 全擋：stage 5 把 agent 提的 lemma 都濾掉、commit 不 INSERT、回 `forward_no_new_goal` + detail `dedupe blocked`
- **migration 順序**：cli reset 先清 queue（含 decision_id refs）再清 strategist_decisions、避免 FK orphan
