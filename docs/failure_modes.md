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
| `proved` | Builder | 證明完成（Phase 1 hint 或 Phase 2 patch 過） | goal `proved`、清 session |
| `success` | Backward | strategy 提交（patch + sub-goals 落定 + lake build 過） | goal `attempting`、清 session |
| `failed` | Builder + Backward | 帶 `failure_reason`、見 §2 | 依 reason 變、預設 attempts++ |

**cascade 共通規則**（以下表格欄省略相同部分、只列 reason 特異處）：
- 預設：`attempts++`、達 SHELVE_THRESHOLD（預設 8）→ goal `shelved` + `_propagate_shelve` 上拋
- 過 BUILDER_THRESHOLD（預設 3）→ 清 builder_session（下次 dispatch 變 Backward）
- spawn_fast_fail → 不增 attempts、設 30s cooldown、CONSEC=10 觸發 daemon 退出
- agent_infeasible → 不增 attempts、goal 直接 `shelved` + `_propagate_shelve`

---

## 2. Failure reasons（cross-pipeline master table）

| failure_reason | 出處 | 觸發條件 | session 處理 | cascade 處理 | event_type 投影 |
|---|---|---|---|---|---|
| `lake_build_error` | Builder + Backward | Phase 2 patch / Backward strategy 組裝 build 失敗 | 保留（warm retry 帶 stderr 進 retry_context） | attempts++ | `direct_attempt` |
| `forbidden_lemma` | Builder + Backward | patch 文本命中 Manifest `forbidden_lemmas` | 保留 | attempts++ | `direct_attempt` |
| `parse_proposal_fail` | Backward | PROPOSAL.md / patch_*.lean / new_*.lean 缺一 | 保留 | attempts++ | `direct_attempt` |
| `patch_signature_mismatch` | Backward (F52) | agent 改了鎖死的 `theorem sX <binders> : <type>` 簽名 | 保留 | attempts++ | `direct_attempt` |
| `naming_violation` | Backward | sub-goal slug 不含 `s<sid>_` 前綴 | 保留 | attempts++ | `direct_attempt` |
| `agent_declined` | Builder (F48) | agent 寫 PROPOSAL 但無 patch + frontmatter `decline_reason: too_hard` | 清（next dispatch 是 Backward） | attempts 跳到 BUILDER_THRESHOLD（一次燒掉 Builder 預算） | `direct_attempt`（subtype） |
| `agent_infeasible` | Builder + Backward (F48) | agent 在 PROPOSAL 標 `decline_reason: parent_type_infeasible`（含反例） | 清 | goal 直接 `shelved` + `_propagate_shelve`（**不增 attempts**、cascade 上拋讓父 strategy 重拆） | `infeasible_sub`（投到 parent goal、不到自己） |
| `agent_timeout` | Builder + Backward | claude rc=124（SIGKILL at WORKER_TIMEOUT_SEC、預設 600s） | 清（postmortem 跑完 + 寫 `.drafts/`、F55） | attempts++ | `direct_attempt` |
| `agent_rc_nonzero` | Builder + Backward | rc≠0、rc≠124、wall-clock ≥ 10s（一般 hard fail：crash / parser error / etc.） | 保留（warm retry 帶 stderr） | attempts++ | `direct_attempt` |
| `agent_no_output` | Builder Phase 2 | rc=0 但 agent 沒寫 `patch*.lean` 也沒 PROPOSAL.md（agent 不 follow 格式） | 保留 | attempts++ | `direct_attempt` |
| `spawn_fast_fail` | Builder + Backward (F46) | rc≠0 且 wall-clock < 10s（infra 故障：claude.exe crash / cwd / quota） | 不變 | **不增 attempts**、設 30s cooldown、CONSEC=10 觸發 daemon 退出 rc=2 | 不投影（純 framework noise） |
| `superseded` (legacy) | pre-F56 Verify worker | F56 後不再產生新 row、僅歷史 db 有 | n/a | n/a | 不投影 |

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
