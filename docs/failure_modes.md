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
- **Strategist Inject 例外**：pipeline 帶 `decision_id` 非 None 時、helper 的 budget gate（BUILDER/SHELVE_THRESHOLD）+ goal_still_active 的 attempts 上限**完全 bypass**。Strategist 看完 failure_replay 認可後 framework 不二猜；唯一守住的是 goal status 已 terminal 仍 moot。收斂責任落 Strategist ConfirmShelve 紀律（`Tooling/prompts/strategist/pending_review.md`）
- spawn_fast_fail / quota_exhausted / missing_dep / gateway_unreachable / transient_timeout → 不增 attempts、不寫 dead_attempt、設 30s cooldown（CONSEC daemon-exit：spawn_fast_fail=10、gateway_unreachable=8、transient_timeout 不進 CONSEC）
- agent_declined → cascade attempts++ 一次 + `entry_kind='Backward'`（路由不再用 attempts 灌到 BUILDER_THRESHOLD 的 hack）
- agent_infeasible → cascade attempts++ 一次 + goal 直接 `disproved` + `_propagate_disproved`
- parent_needs_fix → cascade attempts++ 一次 + goal 直接 `dead` + `_propagate_dead`
- agent_shelved → cascade attempts++ 一次 + `_enqueue_strategist_review`（轉 pending_strategist_review、不 propagate）

---

## 2. Failure reasons（master table）

Phase 7 後 retry 邏輯下沉到 in-pipeline retry helper（`Tooling/pipeline/_retry.py`）。
attempts ↔ dead_attempts 的 1:1 invariant：每個失敗 spawn 都 buffer 一筆 dead_attempt
記錄、由 dispatcher 在 pipelines INSERT 後 flush（buffer-then-flush 給 all-or-nothing
crash 語意）。cascade 對非 terminal-decline 的失敗（lake error、forbidden_lemma 等）
只做 status transition、不再做 attempts++（已由 helper buffer 內計數）。

> 名詞：「verify-collapse」= 把舊版的 Verify worker_kind 折疊成主迴圈 inline
> housekeeping。pre-collapse 的 Strategy-target `dead_attempts` row 留在 DB
> 作為歷史；新 pipeline 不再產生這類 row。詳見 `data-flow.md` §4。

| failure_reason | 出處 | 觸發條件 | helper 處理 | cascade 處理 | event_type 投影 |
|---|---|---|---|---|---|
| `lake_build_error` | Builder + Backward | Phase 2 patch / Backward strategy 組裝 build 失敗 | buffer + 同 session 下一輪 retry（retry_context 帶 stderr） | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `forbidden_lemma` | Builder + Backward | patch 文本命中 Manifest `forbidden_lemmas` | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `parse_proposal_fail` | Backward | patch.lean 缺；或 patch=1 new=0 + sorry body + 無 decline directive（Phase 6.5 後 patch body 非 sorry 視為 leaf-bypass、不算失敗）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `patch_signature_mismatch` | Backward | agent 改了鎖死的 `theorem sX <binders> : <type>` 簽名 | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `naming_violation` | Backward | sub-goal slug 違反 charset / length lint（lowercase `[a-z][a-z0-9_]*`、≤ 60 chars；衝突 framework auto-suffix、不算 violation） | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_no_annotation` | Builder + Backward (Phase 2) | rc=0、build 過但 patch.lean leading comment 空白 | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_no_output` | Builder Phase 2 | rc=0 但 agent 沒寫 `patch*.lean` | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_rc_nonzero` | Builder + Backward | rc≠0、rc≠124/125/126/127、wall-clock ≥ 10s（一般 hard fail）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_timeout` | Builder + Backward | claude rc=124（SIGKILL at WORKER_TIMEOUT_SEC、預設 600s） | **salvage parse 一次**（idle-window guard 後 active agent 可能 disk 上有 valid output 但沒 exit 乾淨）：parse 返 terminal-success / decline → 直接 attach；返 non-terminal failure → fold 到 detail、走原 postmortem（寫 `.drafts/`）+ buffer + 強制 exhaust（不再續 retry） | (helper 已 ++)；exhausted → status transition；salvage 成功時 reason 走 success/decline 而非 timeout | `direct_attempt` |
| `agent_declined` | Builder | agent 寫 `-- decline: needs_decomposition`（unified directive system, 2026-05-10；舊名 `too_hard`） | terminal exit（不 buffer 自身）| **attempts++** + `entry_kind='Backward'`（路由用 entry_kind、不再灌 attempts 到 BUILDER_THRESHOLD） | `direct_attempt` |
| `agent_infeasible` | Builder + Backward | agent 寫 `-- decline: unprovable`（含反例；舊名 `parent_type_infeasible`） | terminal exit（不 buffer 自身）| **attempts++** + goal `disproved` + `_propagate_disproved` | `infeasible_sub`（投到 parent goal、不到自己；filter `_NON_AGENT_REASONS` 排除 self） |
| `parent_needs_fix` | Builder + Backward | agent 寫 `-- decline: return_to_parent`（含具體 fix hint：缺哪個 hypothesis / 換哪個結構） | terminal exit（不 buffer 自身）| **attempts++** + goal `dead` + `_propagate_dead`；description 投到 parent context 的 fix hint section | `infeasible_sub`（同上；renderer 用 `failure_reason` 區分 fix-hint vs counterexample） |
| `agent_shelved` | Builder + Backward | agent 寫 `-- decline: shelve`（無反例、純 give up） | terminal exit（不 buffer 自身）| **attempts++** + `_enqueue_strategist_review`（轉 pending_strategist_review、不 propagate） | `infeasible_sub`（同上；soft 訊號、留給 Strategist 將來覆核） |
| `agent_bailed` | Backward (rescue option d) | watchdog wall_cap → rescue spawn 中、agent 自評沒把握、寫 `_progress.md` 到 attempts_dir 後退出（無 patch.lean / 無 split） | terminal exit（不 buffer 自身）| **attempts++** + 過 SHELVE 才 shelve（goal 留 open / attempting、下次 dispatch 再派）；outer wrapper 把 `_progress.md` persist 到 `.drafts/backward_g<id>.md` 給下輪 cold-spawn 看 | `direct_attempt` |
| `goal_no_longer_open` | Backward | parse 階段 race 偵測：lake build 完但 goal 已 proved/shelved | terminal exit（不 buffer 自身）| 走 generic `failed`/attempts++（dispatcher 寫 final dead_attempt） | `direct_attempt` |
| `quota_exhausted` | Builder + Backward | rc=126（gemini quota 耗盡）| 早返、不 buffer 自身、不耗 budget | **不增 attempts**、設 30s cooldown、不進 CONSEC | 不投影（infra） |
| `missing_dep` | Builder + Backward | rc=127（CLI 缺）| 早返、不 buffer 自身、不耗 budget | **不增 attempts**、設 30s cooldown、不進 CONSEC | 不投影（infra） |
| `spawn_fast_fail` | Builder + Backward | rc≠0 且 wall-clock < 10s（claude.exe crash / cwd） | 早返、不 buffer 自身、不耗 budget | **不增 attempts**、設 30s cooldown、CONSEC=10 觸發 daemon 退出 rc=2 | 不投影（infra） |
| `gateway_unreachable` | Builder + Backward (1db4e8c) | worker thread 收到 URLError / OSError(ECONNREFUSED/ECONNRESET/ENETUNREACH/ETIMEDOUT) / Windows WinError 10061/10054/64 — gateway HTTP transport 完全失聯 | 早返（dispatcher 端、不進 helper）| **不增 attempts**、設 30s cooldown、CONSEC=8 觸發 daemon 退出 rc=2（gateway 永久死亡時不無限重試） | 不投影（infra） |
| `transient_timeout` | Builder + Backward (post-pilot fix) | worker thread 收到 `TimeoutError`（lsp_client.py:169 的 `$/lean/rpc/call` 超時、slot 競爭 RPC 等不到等）| 早返（dispatcher 端）| **不增 attempts**、設 30s cooldown、**不進 CONSEC**（slot 競爭是健康過載、不是 gateway 死、若併計 circuit breaker 會在 244-題 benchmark 下誤殺） | 不投影（infra） |
| `superseded` (legacy) | pre-collapse Verify worker | verify-collapse 後不再產生新 row、僅歷史 db 有 | n/a | n/a | 不投影 |

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
| `parent_stub_not_decomposable` | Backward | skeleton 從 parent stub 抽不出簽名 |
| `goal_no_longer_open` | Backward | 跑到中途 goal status 已非 `'open'`（race protection、_abort 前回滾寫入的檔） |
| `unknown_kind` | dispatcher | `_run_pipeline` 收到非 Builder/Backward 的 task_kind（unreachable in current code、enum 完整性保留） |

這些都走 generic cascade（attempts++、過 SHELVE 就 shelved）；**event 不投影**（agent 看不到也不能改、跟 `spawn_fast_fail` 同類處理 — `dead_attempts` 仍 INSERT 給 operator forensic、events.py 投影層 filter out）。觸發頻率極低、未來可考慮獨立 cooldown / retry 策略。

**Notes**：
- spawn 失敗的三條 reason（`agent_timeout` / `agent_rc_nonzero` / `agent_no_output`）按 rc + agent 行為精確分類，retry agent / event renderer 可依 reason 直接 dispatch、不需要 parse `failure_detail`。
- `agent_declined`（`needs_decomposition` directive）**只在 Builder**。Backward 是 decomposer 自己、沒有「需要拆解」的 escape；Backward agent 退出用 `unprovable` / `return_to_parent` / `shelve` 三條。
- 詳細的 directive 詞彙設計（4 個 directive × 2 pipeline、何時用哪條、description 規範）見 `docs/archive/decline_directives.md`。
- `lake_build_error` 在 Builder 來自 patch 套上去 build 失敗；在 Backward 來自 strategy 組裝（sub-goal sorry stubs + scratch 一起 build batch）失敗。

---

## 3. Event types（goal_history v1）

`Tooling/agent/context.py` 的 `compile_context` 經 `events.py` 投影層產生 event 物件、注入到
`## Goal history` umbrella section（refactor 進行中、見 `goal_history_unified.md`）。

| event_type | DB 來源 | digest 結構 | 注入到誰的 Context.md | actionability |
|---|---|---|---|---|
| `direct_attempt` | `dead_attempts` where `target_kind='Goal'` AND `failure_reason NOT IN _NON_AGENT_REASONS` | `failure_reason` + 截斷 `failure_detail` + 簡短 PROPOSAL excerpt | `dead_attempts.target_id`（自己這個 goal） | must-see |
| `verify_failure` | `dead_attempts` where `target_kind='Strategy'`（pre-collapse row、verify-collapse 後不再產生） | strategy 的 `proposal_md` 截斷 + lake stderr 摘要 | `strategies.goal_id` | must-see |
| `dead_strategy` | `strategies` where `status='dead'` AND `proposal_md != ''` AND ≥1 linked sub-goal | `proposal_md` 截斷 + 該 strategy 拆出的 sub-goal slug 列表 | `strategies.goal_id` | must-see |
| `infeasible_sub` | `dead_attempts` where `failure_reason IN ('agent_infeasible','parent_needs_fix','agent_shelved')` JOIN `strategy_subgoals` 找 parent | sub-goal slug + `failure_reason` tag + 摘要（`_extract_root_cause` 抽 `## Root cause` / `## Fix hint` / `## Counterexample`）| **parent goal id**（不是失敗的 sub 自己） | must-see |
| (filtered out) | `dead_attempts` where `failure_reason IN _NON_AGENT_REASONS` | — | — | 不投影 |

**`_NON_AGENT_REASONS`** — events.py 統一定義的不投影 reason set、SQL `NOT IN` 引用：
- `spawn_fast_fail` — infra 故障（claude.exe crash / cwd / quota）
- `agent_infeasible` — 改投成 `infeasible_sub`、不在自己 goal 出現
- `goal_not_found`, `lean_file_missing`, `missing_parent_stub`, `parent_stub_not_decomposable`, `goal_no_longer_open`, `unknown_kind` — framework / DB / FS race、agent 看不到也不能改

**audience 規則的兩個 axis**（不再 kind-gate Builder/Backward）：

1. **Target locality** — event 的 target 跟當下 dispatch goal 的關係（自己 / 自己的 strategy / parent 的 sub）
2. **Actionability** — must-see / on-demand / 不投影

詳細 axis 設計、kind-gating 為何能消失、實作 mapping → `docs/archive/goal_history_unified.md` §「Audience 規則」。

**Edge cases**：

- **`dead_strategy` ↔ `verify_failure` 重疊**：同一條 dead strategy 可能在兩處都有對應 row（status='dead' + dead_attempts target_kind='Strategy'）。投影層 dedupe — `dead_strategy` 取得的 strategy id 集合先扣掉 `verify_failure` 涵蓋的，避免 umbrella 重複。當前 `_section_dead_strategies` 已有此 filter（context.py:642-651）。
- **`agent_infeasible` 雙身分**：DB row 跟其他 direct_attempt 同形（`target_kind='Goal'`、`target_id=失敗的 sub-goal`），但 actionable signal 在 parent。投影層判斷 `failure_reason == 'agent_infeasible'` 改投成 `infeasible_sub`、`target_goal` 改 parent。沒 parent（root 自己 infeasible，理論上不可能）→ drop。
- **Empty bucket**：某 event_type 在某 goal 為空 → sub-section header 不寫、companion 檔不寫（避免空檔污染 sandbox）。

---

## 4. 跨參考

- 動態 flow（pipeline 完整流程含失敗）：`docs/data-flow.md`
- goal_history v1 audience 規則 / 實作步驟設計史：`docs/archive/goal_history_unified.md`
- DB schema CHECK 與 column 定義：`Tooling/db.py`
- cascade 完整邏輯：`Tooling/dispatcher.py` `cascade_one`
- session / postmortem 機制：`Tooling/pipeline/builder.py` rc 處理、`pipeline/_drafts.py`
