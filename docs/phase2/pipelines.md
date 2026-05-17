# Phase 2 — Pipeline 細部 spec

`design.md` 講概念、本檔講實作介面。讀順序：先 `design.md` 拿 mental model、再回本檔找 schema / stage / DB 細節。

---

## 1. 共通約定

兩條新 pipeline 都 atomic、佔 worker pool slot、wall budget 沿用 `dispatch.spawn_timeout_sec`、retry 沿用 `run_with_session_retries`。Phase 2 不引入 continuous_task runtime。

| 屬性 | Strategist | Forward |
|---|---|---|
| Family | Coordinator | Generator |
| 觸發 | 見 §2.1 | 只能由 Strategist `InjectForward` |
| 輸出 | 單一 decision object | 單一 lemma proposal |

---

## 2. Strategist

### 2.1 任務 + 觸發

| ID | 任務 | 觸發條件 |
|---|---|---|
| **T0** | First-launch + Defs.lean 初寫（若需要） | `problems.bootstrap_done = false` |
| **T1** | Routine：看局勢、決定 `Inject(...)` / `EmitDirective` / `Noop` | 每 `strategist.interval_min` 分鐘（預設 60） |
| **T2** | `pending_strategist_review` Goal 判決 | `goal_pending_review` event |
| **T3** | Defs.lean amend 提案 + 下次跑時補 `RequestHumanInput` | T1 / T2 衍生 |

優先序：T2 > T0 > T1。同時最多 1 條 Strategist（不重入）。

不做：
- 決定 Backward / Builder 派誰（BFS 自動）
- 調 queue 優先序（既有 priority 機制夠用）
- 主動 health check / framework alert（未來再加）
- 開場擱置 root（Phase 2 不處理「先派 Forward 再攻 root」的場景；root 預設先試 Backward、卡住才走 T1 處理）

**T0 機制**：`Manifest.entry_kind` 欄位 + `## Entry kind` Manifest section 刪除。新加 `problems.bootstrap_done` boolean column。cli init 插 `bootstrap_done=false`、dispatcher 偵測到該值就 enqueue Strategist（target=root）、Strategist commit 後設 `bootstrap_done=true`。`cli reset` 後該 flag 重設、自然 re-bootstrap。Strategist 失敗（schema_invalid 等）走 `_INFRA_REASONS` 路徑、不 burn root.attempts。

### 2.2 Input

每次跑時依任務 compile：

| 來源 | 內容 | 用於 |
|---|---|---|
| TREE.md | 既有 problem-level tree artifact、全結構 + status + dead cause | T1（所有任務基底） |
| active_goals_sidecar | status ∈ {open, attempting, pending_strategist_review} 的 Goal 列表、含 slug + statement（截斷 200 字） | T1 |
| failure_replay | strategist_decisions 表近 5 條 + 對應 outcome | 所有任務（self-feedback） |
| review_context | 觸發的 Goal full statement + ancestor 鏈 + 失敗 reason summary + 既有 strategy 內容 | T2 |
| problem_meta | Manifest + Defs.lean | T0 / T3 |

TREE.md 已給結構 + status + slug、但缺 statement 文字；sidecar 補 active goals 的 statement、proved / shelved 不附（穩定、不會是 Inject target）。residue_thm scale 預期 ≤ 20 active goals、prompt 重量可控。未來大規模再考慮 MCP 懶載入。

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
 "reason": "Library now has contour_deformation_piecewise; prefer it over manual case-split."}
```

完整 decision kinds：

| Kind | 作用 | 文字欄位 |
|---|---|---|
| `Inject(pipeline, brief)` | 派指定 pipeline；Phase 2 只接受 `pipeline="Forward"`；brief 是 Strategist 給 Forward 的自由描述 | `brief` |
| `ConfirmShelve(target_goal_id)` | T2：真 dead end、轉終態 shelved | `reason` |
| `Reopen(target_goal_id, directive?)` | T2：值得再試、轉回 attempting；directive 寫入 problem-level directive 欄位 | `reason` |
| `EmitDirective(scope, body)` | 寫入 problem-level DB column、覆蓋既有；給未來下游 pipeline 看的提醒 | `reason`（提醒內容） |
| `InitializeDefs(problem, lean_body)` | T0：直接寫 `Defs.lean`（檔案不存在才能用） | `reason` |
| `ProposeDefsAmend(problem, proposed_body)` | T3：寫 `.proposed_defs.lean` 草稿；下次 Strategist 跑時自動補 `RequestHumanInput` | `reason` |
| `RequestHumanInput(scope, topic, question)` | 只用於 Manifest / Defs 相關（topic ∈ `{manifest_amend, defs_amend}`） | `reason` |
| `Noop` | 顯式不動 | `reason` |

**Inject 為何沒 InjectBackward**：Backward 派發整路由 BFS structural refill 處理、Strategist 不介入。T0 bootstrap 後 BFS 自動 enqueue root；T1 routine 看到卡住的 Goal 不直接派 Backward、而是 InjectForward 補 library 後、BFS 自然再派 Backward 重試。

**Inject 為何沒 target_goal_id**：Forward 不 tie 特定 Goal、輸出的 lemma 通用、可能多 Goal 都援引。Strategist 在 brief 內自由描述需求（可能提具體 Goal、可能提 domain、可能混合）、Forward agent 讀 brief + Library + Mathlib state 自行判斷產什麼 lemma。

`strategist_decisions` schema 仍保留 `target_id` 欄位（給 ConfirmShelve / Reopen 等其他 decision 用）、Inject row 該欄位空。未來 Refuter / Curator 等 pipeline 若需要 target、re-use 同欄位。

deferred 到 Phase 2.5+：
- `ReformulateGoal(target, new_statement, rationale)` — 改寫 Goal statement、原 Goal 標 superseded。不可用於 root。需要 cluster relation 護欄、等 v3 doc §3 落地
- `PauseGoal` / `UnpauseGoal` — 配套「先派 Forward、暫不攻 root」場景、Phase 2 不開

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
| `Problems/<p>/.proposed_defs.lean` | `ProposeDefsAmend` 寫入草稿 |

Inject 的 brief 不另寫檔——存 `strategist_decisions.brief` column、由被 Inject 派的 pipeline 在 cold-start 從 DB 拉出注入 Context.md 一段（見 §4.4）。

Strategist **不直接修改既有的** `Defs.lean` / `Manifest.md`——只能初寫或寫草稿。維持 CLAUDE.md「Manifest + Defs.lean 是唯一人手檔」契約。

### 2.6 Self-feedback loop

下次 Strategist 跑時 `failure_replay` 拉近 5 條 decisions、agent 看到「上次我建議 X、結果 Y」、靠 trace 自己學。不需 explicit reward signal。

例：上次 `Reopen(G=1480, directive=...)`、後續 Backward 仍失敗 → 學會該 directive 沒效、下次該 case 改 `ConfirmShelve`。

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

1. **dedupe**：與既有 alive / proved 重複的直接濾掉、轉 `forward_all_dedupe` 結果
2. **Strategist self-feedback**：上次 Forward 結果差（dedupe 全濾掉、或 lemma 始終攻不下來）→ 下次 Strategist 不再 InjectForward

Forward 不負責 strategy 設計（那是 Backward 的事）。Forward 產的新 Goal 進池後、`bfs_refill` 自動派 Backward 去攻。

---

## 4. Infrastructure 改動

### 4.1 DB schema

| Table | 改動 |
|---|---|
| `pipelines.kind`、`queue.kind` | enum 加 `Strategist`、`Forward` |
| `pipelines.target_id` | 允許 null（Forward case；既有 Backward / Builder 仍非空） |
| `queue.decision_id` | 新欄位、int nullable、FK strategist_decisions(id)；非空表示此項由某 Inject decision 派出、pipeline cold-start 拉 brief 注入 Context.md |
| `goals.origin` | enum 加 `forward` |
| `goals.status` | enum 加 `pending_strategist_review` |
| `problems.bootstrap_done` | 新欄位、boolean default false |
| `problems.strategist_directive` | 新欄位、text nullable、長度由 prompt 約束（不做 schema CHECK） |
| `problems.last_strategist_at` | 新欄位、ts nullable、用於 T1 wall-clock 計算 |
| `strategist_decisions` | 新表（見下） |
| `Manifest.entry_kind` 欄位 + `## Entry kind` section | **刪除**（強制 Strategist 預設、不再 user-configurable） |
| cli init | 改插入 `problems.bootstrap_done=false`、不再讀 Manifest entry_kind |

`goals.entry_kind` 不擴 enum——Forward 產的新 Goal 預設 `Backward`（如 Backward agent 寫 sub-goal 一樣、leaf-適合直接攻就標 `Builder`）。

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

新增一條：

```
when failure_reason == agent_shelved AND goal.status in ('open','attempting'):
    goal.status ← 'pending_strategist_review'
    emit goal_pending_review
    (不直接 cascade 上游、等 Strategist review 後依結論再 cascade)
```

`ConfirmShelve` commit 階段執行真正的 shelve cascade（沿用既有邏輯）。
`Reopen` commit 階段：goal.status ← 'attempting'、若 directive 不空寫入 `problems.strategist_directive`、re-enqueue。

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
- `strategist_awaiting_human` outcome 後、該 scope 後續 dispatch 暫停、需 operator 手動 resume
- Strategist 失敗（schema_invalid 等）走 `_INFRA_REASONS` 路徑、不 burn root.attempts

### 4.4 Context.md 整合（directive + brief）

Backward / Builder / Forward cold-start 的 `compile_context` 增加兩段 markdown 注入：

| 段名 | 來源 | 何時出現 |
|---|---|---|
| `## Strategist directive` | `problems.strategist_directive` column | 非空時、所有 pipeline cold-start 都附（problem-level、persistent） |
| `## Strategist brief` | `strategist_decisions.brief`（依該 pipeline 對應 decision_id 查） | 該 pipeline 由 Inject 派出時才附（per-pipeline、one-shot） |

純資料注入 Context.md、不動 prompt 措辭。

**鏈接機制**：Strategist commit 階段 enqueue 時、queue row payload 帶 `decision_id`。dispatcher pop_queue 後派 pipeline、把 decision_id 傳給 `compile_context`、由它查 DB 拉 brief 文字注入 Context.md。

- BFS 自動派的 pipeline 沒 decision_id、跳過 brief 段（只有 directive 段、若該 problem 有 directive 的話）
- directive 無 expire 機制（單槽位、自然由下次覆蓋淘汰）
- brief 是 per-decision、不複用、不會跨多次 pipeline 出現

### 4.5 新 failure_reason / event_type

failure_reason：

| reason | 說明 |
|---|---|
| `strategist_noop` | Noop decision 的乾淨退出（infra-reason、不 burn attempts） |
| `strategist_schema_invalid` | self_verify 失敗（infra-reason、不 burn attempts） |
| `strategist_awaiting_human` | RequestHumanInput 已 emit、等 user（infra-reason） |
| `forward_no_useful_lemmas` | agent 認為 Library 已足夠 |
| `forward_all_dedupe` | 提案全被 dedupe 濾掉 |

events：`goal_pending_review`、`strategist_decision_committed`、`human_input_requested`。

### 4.6 不需要動

1:1 worker-pipeline binding、gateway、dedupe、existing Backward / Builder prompt 措辭、agent decline directive 集合（沿用既有 `shelve` 觸發 pending_review）。

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
| `RequestHumanInput` 用於非 Manifest 狀況 | 不啟用 | 目標最小化人類介入；只在 Manifest / Defs 相關才呼叫 |
| `HealthCheck / FrameworkAlert` | 不做 | Phase 2 先不做、未來若需要再加 |
| `DetectCircularSubgoaling` 專用 decision | 不做 | 由 `EmitDirective` 涵蓋 |
| 「subtree stuck」事件觸發 Strategist | 不做 | T1 wall-clock routine 順便處理、Strategist agent 自己看 inventory 判斷 |
| Forward outcome 事件觸發 Strategist | 不做 | 同上、Phase 2 不開 forward_finished event |
| 「queue idle」事件觸發 Strategist | 不做 | T1 wall-clock 涵蓋；queue idle 沒事做就讓系統等下次 routine |
