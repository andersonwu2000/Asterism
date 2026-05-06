# Asterism — Pipeline outcomes & failure modes

寫於 2026-05-06。

每條 pipeline 結束時產出一個 outcome；非成功 outcome 帶 `failure_reason` 給 forensic
+ event 投影。本檔是 `failure_reason` / `event_type` 的 **single source of truth**。

新增 reason / event_type → 改本檔 + 改 events.py 投影邏輯，**不在其他 doc 加對照表**。

---

## 1. Pipeline outcomes

每條 pipeline 終結時的 outcome 字串（pipeline.PipelineResult.outcome）：

| outcome | 適用 | 意義 | cascade 大原則 |
|---|---|---|---|
| `proved` | Builder | 證明完成（Phase 1 hint 或 Phase 2 patch 過） | goal `proved` |
| `success` | Backward | strategy 提交（patch + sub-goals 落定 + lake build 過） | goal `attempting` |
| `failed` | Builder + Backward | 帶 `failure_reason`、見 §2（terminal decline / infra rc / Phase 1 直接返回 / goal_not_found） | 依 reason 變 |
| `exhausted` | Builder + Backward (Phase 7) | helper budget 用盡、最後 retry 的 reason 反映在 `failure_reason` | (helper 已 ++ attempts)；過 SHELVE 才 shelve；否則 status 不動讓下次 dispatch 重派 |
| `moot` | Builder + Backward (Phase 7) | helper 入場 / mid-loop cascade re-check 發現 goal 已終態 | uniform no-op（不動 state、不寫 dead_attempts、不 ++ attempts） |

**cascade 共通規則**（以下表格欄省略相同部分、只列 reason 特異處）：
- 預設：失敗 spawn 由 helper buffer 一筆 dead_attempt + attempts++（dispatcher 在 pipelines INSERT 後 flush）；達 SHELVE_THRESHOLD（預設 8）→ goal `shelved` + `_propagate_shelve` 上拋
- 過 BUILDER_THRESHOLD（預設 3）→ 下次 dispatch 自動由 `next_worker_kind` 改派 Backward
- spawn_fast_fail / quota_exhausted / missing_dep → 不增 attempts、不寫 dead_attempt、設 30s cooldown（CONSEC daemon-exit 只對 spawn_fast_fail 觸發）
- agent_declined → cascade attempts++ 一次 + `entry_kind='Backward'`（路由不再用 attempts 灌到 BUILDER_THRESHOLD 的 hack）
- agent_infeasible → cascade attempts++ 一次 + goal 直接 `shelved` + `_propagate_shelve`

---

## 2. Failure reasons（master table）

Phase 7 後 retry 邏輯下沉到 in-pipeline retry helper（`Tooling/pipeline/_retry.py`）。
attempts ↔ dead_attempts 的 1:1 invariant：每個失敗 spawn 都 buffer 一筆 dead_attempt
記錄、由 dispatcher 在 pipelines INSERT 後 flush（buffer-then-flush 給 all-or-nothing
crash 語意）。cascade 對非 terminal-decline 的失敗（lake error、forbidden_lemma 等）
只做 status transition、不再做 attempts++（已由 helper buffer 內計數）。

| failure_reason | 出處 | 觸發條件 | helper 處理 | cascade 處理 | event_type 投影 |
|---|---|---|---|---|---|
| `lake_build_error` | Builder + Backward | Phase 2 patch / Backward strategy 組裝 build 失敗 | buffer + 同 session 下一輪 retry（retry_context 帶 stderr） | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `forbidden_lemma` | Builder + Backward | patch 文本命中 Manifest `forbidden_lemmas` | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `parse_proposal_fail` | Backward | patch.lean 缺；或 patch=1 new=0 + sorry body + 無 decline directive（Phase 6.5 後 patch body 非 sorry 視為 leaf-bypass、不算失敗）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `patch_signature_mismatch` | Backward (F52) | agent 改了鎖死的 `theorem sX <binders> : <type>` 簽名 | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `naming_violation` | Backward | sub-goal slug 違反 charset / length lint（lowercase `[a-z][a-z0-9_]*`、≤ 60 chars；衝突 framework auto-suffix、不算 violation） | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_no_annotation` | Builder + Backward (Phase 2) | rc=0、build 過但 patch.lean leading comment 空白 | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_no_output` | Builder Phase 2 | rc=0 但 agent 沒寫 `patch*.lean` | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_rc_nonzero` | Builder + Backward | rc≠0、rc≠124/125/126/127、wall-clock ≥ 10s（一般 hard fail）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_timeout` | Builder + Backward | claude rc=124（SIGKILL at WORKER_TIMEOUT_SEC、預設 600s） | postmortem（寫 `.drafts/`、F55）+ buffer + 強制 exhaust（不再續 retry） | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_declined` | Builder | agent 在 patch.lean 檔頂寫 `-- decline: too_hard`（Phase 6） | terminal exit（不 buffer 自身）| **attempts++** + `entry_kind='Backward'`（Phase 7：路由用 entry_kind、不再灌 attempts 到 BUILDER_THRESHOLD） | `direct_attempt` |
| `agent_infeasible` | Builder + Backward | agent 寫 `-- decline: parent_type_infeasible`（含反例、Phase 6） | terminal exit（不 buffer 自身）| **attempts++** + goal `shelved` + `_propagate_shelve`（cascade 上拋讓父 strategy 重拆） | `infeasible_sub`（投到 parent goal、不到自己） |
| `goal_no_longer_open` | Backward (F24-A) | parse 階段 race 偵測：lake build 完但 goal 已 proved/shelved | terminal exit（不 buffer 自身）| 走 generic `failed`/attempts++（dispatcher 寫 final dead_attempt） | `direct_attempt` |
| `quota_exhausted` | Builder + Backward | rc=126（gemini quota 耗盡）| 早返、不 buffer 自身、不耗 budget | **不增 attempts**、設 30s cooldown、不進 CONSEC | 不投影（infra） |
| `missing_dep` | Builder + Backward | rc=127（CLI 缺）| 早返、不 buffer 自身、不耗 budget | **不增 attempts**、設 30s cooldown、不進 CONSEC | 不投影（infra） |
| `spawn_fast_fail` | Builder + Backward (F46) | rc≠0 且 wall-clock < 10s（claude.exe crash / cwd） | 早返、不 buffer 自身、不耗 budget | **不增 attempts**、設 30s cooldown、CONSEC=10 觸發 daemon 退出 rc=2 | 不投影（infra） |
| `superseded` (legacy) | pre-F56 Verify worker | F56 後不再產生新 row、僅歷史 db 有 | n/a | n/a | 不投影 |

**outcome 分類**（Phase 7 新增 / 變更）：

| outcome | 語意 |
|---|---|
| `proved` | Builder 成功 |
| `success` | Backward strategy commit 成功 |
| `failed` | helper 早返：terminal-decline reasons / infra rcs / goal_not_found |
| `exhausted` | helper budget 用盡、最後 retry 的 reason 是 helper buffered 的最末筆 |
| `moot` | helper 入場或 mid-loop cascade re-check 偵測 goal 已終態（sibling proved / shelved）；no-op、不寫 dead_attempts、不 attempts++ |

**Framework-level reasons（罕見、framework / DB / FS race 觸發）**：

| failure_reason | 出處 | 觸發條件 |
|---|---|---|
| `goal_not_found` | Builder + Backward | `db.get_goal(goal_id)` 回 None（DB / dispatch race） |
| `lean_file_missing` | Builder | parent goal 的 `.lean` 在 disk 不存在 |
| `missing_parent_stub` | Backward | 讀 parent lean 失敗（OSError） |
| `parent_stub_not_decomposable` | Backward | F52 skeleton 從 parent stub 抽不出簽名 |
| `goal_no_longer_open` | Backward | 跑到中途 goal status 已非 `'open'`（race protection、_abort 前回滾寫入的檔） |
| `unknown_kind` | dispatcher | `_run_pipeline` 收到非 Builder/Backward 的 task_kind（unreachable in current code、enum 完整性保留） |

這些都走 generic cascade（attempts++、過 SHELVE 就 shelved）；**event 不投影**（agent 看不到也不能改、跟 `spawn_fast_fail` 同類處理 — `dead_attempts` 仍 INSERT 給 operator forensic、events.py 投影層 filter out）。觸發頻率極低、未來可考慮獨立 cooldown / retry 策略。

**Notes**：
- spawn 失敗的三條 reason（`agent_timeout` / `agent_rc_nonzero` / `agent_no_output`）按 rc + agent 行為精確分類，retry agent / event renderer 可依 reason 直接 dispatch、不需要 parse `failure_detail`。
- `agent_declined` **只在 Builder**。Backward 沒 declined channel；Backward agent 想退出走 `agent_infeasible`（必須含反例）。
- `lake_build_error` 在 Builder 來自 patch 套上去 build 失敗；在 Backward 來自 strategy 組裝（sub-goal sorry stubs + scratch 一起 build batch）失敗。

---

## 3. Event types（goal_history v1）

`Tooling/context.py` 的 `compile_context` 經 `events.py` 投影層產生 event 物件、注入到
`## Goal history` umbrella section（refactor 進行中、見 `goal_history_unified.md`）。

| event_type | DB 來源 | digest 結構 | 注入到誰的 Context.md | actionability |
|---|---|---|---|---|
| `direct_attempt` | `dead_attempts` where `target_kind='Goal'` AND `failure_reason NOT IN _NON_AGENT_REASONS` | `failure_reason` + 截斷 `failure_detail` + 簡短 PROPOSAL excerpt | `dead_attempts.target_id`（自己這個 goal） | must-see |
| `verify_failure` | `dead_attempts` where `target_kind='Strategy'`（pre-F56 row、F56 後不再產生） | strategy 的 `proposal_md` 截斷 + lake stderr 摘要 | `strategies.goal_id` | must-see |
| `dead_strategy` | `strategies` where `status='dead'` AND `proposal_md != ''` AND ≥1 linked sub-goal | `proposal_md` 截斷 + 該 strategy 拆出的 sub-goal slug 列表 | `strategies.goal_id` | must-see |
| `infeasible_sub` | `dead_attempts` where `failure_reason='agent_infeasible'` JOIN `strategy_subgoals` 找 parent | sub-goal slug + counterexample 摘要（從 PROPOSAL.md `## Root cause` / `## Counterexample` 抽，沿用 `_extract_root_cause`） | **parent goal id**（不是失敗的 sub 自己） | must-see |
| (filtered out) | `dead_attempts` where `failure_reason IN _NON_AGENT_REASONS` | — | — | 不投影 |

**`_NON_AGENT_REASONS`** — events.py 統一定義的不投影 reason set、SQL `NOT IN` 引用：
- `spawn_fast_fail` — infra 故障（claude.exe crash / cwd / quota）
- `agent_infeasible` — 改投成 `infeasible_sub`、不在自己 goal 出現
- `goal_not_found`, `lean_file_missing`, `missing_parent_stub`, `parent_stub_not_decomposable`, `goal_no_longer_open`, `unknown_kind` — framework / DB / FS race、agent 看不到也不能改

**audience 規則的兩個 axis**（不再 kind-gate Builder/Backward）：

1. **Target locality** — event 的 target 跟當下 dispatch goal 的關係（自己 / 自己的 strategy / parent 的 sub）
2. **Actionability** — must-see / on-demand / 不投影

詳細 axis 設計、kind-gating 為何能消失、實作 mapping → `docs/dev/goal_history_unified.md` §「Audience 規則」。

**Edge cases**：

- **`dead_strategy` ↔ `verify_failure` 重疊**：同一條 dead strategy 可能在兩處都有對應 row（status='dead' + dead_attempts target_kind='Strategy'）。投影層 dedupe — `dead_strategy` 取得的 strategy id 集合先扣掉 `verify_failure` 涵蓋的，避免 umbrella 重複。當前 `_section_dead_strategies` 已有此 filter（context.py:642-651）。
- **`agent_infeasible` 雙身分**：DB row 跟其他 direct_attempt 同形（`target_kind='Goal'`、`target_id=失敗的 sub-goal`），但 actionable signal 在 parent。投影層判斷 `failure_reason == 'agent_infeasible'` 改投成 `infeasible_sub`、`target_goal` 改 parent。沒 parent（root 自己 infeasible，理論上不可能）→ drop。
- **Empty bucket**：某 event_type 在某 goal 為空 → sub-section header 不寫、companion 檔不寫（避免空檔污染 sandbox）。

---

## 4. 跨參考

- 動態 flow（pipeline 完整流程含失敗）：`docs/data-flow.md`
- 在飛設計（goal_history v1 audience 規則 / 實作步驟）：`docs/dev/goal_history_unified.md`
- DB schema CHECK 與 column 定義：`Tooling/db.py`
- cascade 完整邏輯：`Tooling/dispatcher.py` `cascade_one`
- session / postmortem 機制：`Tooling/pipeline/builder.py` rc 處理、`pipeline/_drafts.py`
