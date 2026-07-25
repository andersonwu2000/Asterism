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
| `naming_violation` | Backward | sub-goal slug 違反 charset / length lint（lowercase `[a-z][a-z0-9_]*`、≤ 60 chars；camelCase framework auto-normalize、衝突 framework auto-suffix，皆不算 violation；只剩 digit-start / punctuation / unicode 等不可機械修者） | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `circular_decomposition` | Backward | sub-goal verbatim 重述其 strict ancestor（同名 + theorem-head 全等）= proving X by reducing to X、零進展;`_2` auto-suffix 會掩蓋成無限退化子樹 | buffer + retry（retry_context 帶「換個分解」提示） | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `batch_reference_cycle` | Backward | 同批 sub-goal stub 互相引用成環——Lean 模組不可互 import、無擺放順序（task #84 起非環邊由框架機械注入 import,環是唯一不可注入者;mirror 會在 session 內預測） | buffer + retry（合併 statement 或改寫消引用） | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `axiom_violation` | Builder + Backward | Manifest 有 `axioms_whitelist` 時，confirm-build 報 `axiom_error` 或用到 whitelist 外的 rogue axiom（含 `sorryAx`）→ 還原 backup、reject | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `cite_unproved_sibling` | Builder + Backward | cite-gate：patch 引用的 sibling `L_<slug>` 尚未 proved（orphan / open / dead / disproved）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `patch_body_contains_sorry` | Backward | leaf-bypass patch body 仍含 `sorry`（既非合法 decomposition、也非真 leaf）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `same_as_disproved` | Backward | sub-goal verbatim 重述本 problem 內已 `disproved` 的 statement（`_retry.py` `_TERMINAL_DECLINE_REASONS`）| terminal exit（不 retry）| (helper 已 ++)；走 generic failed | `direct_attempt` |
| `same_as_dead_unchanged` | Backward | sub-goal 重述本 problem 內 `dead` twin,且 twin 死後無任何新 proved——世界未變的盲重試;detail 附 twin 最後失敗 forensic;twin 死後有新 proved 則放行為 novel | terminal exit（不 retry）| 走 generic failed | `direct_attempt` |
| `duplicate_strategy` | Backward | 分解無 novel sub-goal 且 link 集合與同 goal 上既有 proposed/stalled 策略完全相同——byte-identical 再主張（P3;detail 點名既有 s<id>）| terminal exit（不 retry）| 走 generic failed | `direct_attempt` |
| `no_progress` | Backward | sub-goal 經 isDefEq 偵測 definitionally 等於正在拆的 goal 本身（零進展；比 `circular_decomposition` 的同名文字比對更深的 dedupe tier）| buffer + retry（換個分解）| (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_no_annotation` | Builder + Backward (Phase 2) | rc=0、build 過但 patch.lean leading comment 空白 | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_no_output` | Builder Phase 2 | rc=0 但 agent 沒寫 `patch*.lean` | buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_rc_nonzero` | Builder + Backward | rc≠0、rc≠124/125/126/127、wall-clock ≥ 10s（一般 hard fail）| buffer + retry | (helper 已 ++)；exhausted → status transition | `direct_attempt` |
| `agent_timeout` | Builder + Backward | claude rc=124（SIGKILL at WORKER_TIMEOUT_SEC、預設 600s） | **salvage parse 一次**（idle-window guard 後 active agent 可能 disk 上有 valid output 但沒 exit 乾淨）：parse 返 terminal-success / decline → 直接 attach；返 non-terminal failure → fold 到 detail、走原 postmortem（寫 `.drafts/`）+ buffer + 強制 exhaust（不再續 retry） | (helper 已 ++)；exhausted → status transition；salvage 成功時 reason 走 success/decline 而非 timeout | `direct_attempt` |
| `agent_declined` | Builder | agent 寫 `-- decline: needs_decomposition`（unified directive system, 2026-05-10；舊名 `too_hard`） | terminal exit（不 buffer 自身）| **attempts++** + `entry_kind='Backward'`（路由用 entry_kind、不再灌 attempts 到 BUILDER_THRESHOLD） | `direct_attempt` |
| `agent_infeasible` | Builder + Backward | agent 寫 `-- decline: unprovable`（含反例；舊名 `parent_type_infeasible`） | terminal exit（不 buffer 自身）| **attempts++** + goal `disproved` + `_propagate_disproved` | `infeasible_sub`（投到 parent goal、不到自己；filter `_NON_AGENT_REASONS` 排除 self） |
| `parent_needs_fix` | Builder + Backward | agent 寫 `-- decline: return_to_parent`（含具體 fix hint：缺哪個 hypothesis / 換哪個結構） | terminal exit（不 buffer 自身）| **attempts++** + goal `dead` + `_propagate_dead`；description 投到 parent context 的 fix hint section | `infeasible_sub`（同上；renderer 用 `failure_reason` 區分 fix-hint vs counterexample） |
| `agent_shelved` | Builder + Backward | agent 寫 `-- decline: shelve`（無反例、純 give up） | terminal exit（不 buffer 自身）| **attempts++** + `_enqueue_strategist_review`（轉 pending_strategist_review、不 propagate） | `infeasible_sub`（同上；soft 訊號、留給 Strategist 將來覆核） |
| `no_nl_correspondence` | Builder + Backward | agent 寫 `-- decline: no_nl_correspondence`（NL-first 2026-07-25:goal 或必須發明的 sub-goal 對應不到任何 Programme Proof 步驟——不發明數學,上交） | terminal exit(不 buffer 自身)| **attempts++** + `_enqueue_strategist_review`(轉 pending_strategist_review、不 propagate;Strategist 在 Proof 裡論證到封閉或退役該宣稱) | 不投影(`agent_visible=False`;decline note 經 review context 呈給 Strategist) |
| `agent_bailed` | Backward (rescue option d) | watchdog wall_cap → rescue spawn 中、agent 自評沒把握、寫 `_progress.md` 到 attempts_dir 後退出（無 patch.lean / 無 split） | terminal exit（不 buffer 自身）| **attempts++** + 過 SHELVE 才 shelve（goal 留 open / attempting、下次 dispatch 再派）；outer wrapper 把 `_progress.md` persist 到 `.drafts/backward_g<id>.md` 給下輪 cold-spawn 看 | `direct_attempt` |
| `goal_no_longer_open` | Backward | parse 階段 race 偵測：lake build 完但 goal 已 proved/shelved | terminal exit（不 buffer 自身）| 走 generic `failed`/attempts++（dispatcher 寫 final dead_attempt） | `direct_attempt` |
| `subgoal_slug_collision` | Backward | placement 前 `proof_store` ownership guard：sub-goal 的 `L_<slug>.lean` 路徑已被**別的** goal 擁有（`_resolve_slug_collisions` 漏掉的 cross-batch / re-decomposition 撞名）→ 結構性拒寫、防 clobber-then-orphan DB↔file drift | terminal exit（不 buffer 自身、未寫任何檔）| 走 generic `failed`/attempts++ | `direct_attempt` |
| `forward_no_new_goal` | Forward | 無 `new_<slug>.lean` / 檔不可讀 / elaborate 失敗 / metadata 缺（`Forward rationale:` 等）/ slug 撞 Manifest statement vocab；agent decline `library_sufficient` 另走 `agent_declined` terminal | buffer + retry（elaborate stderr 帶 `retry_context`、budget=FORWARD_RETRY_BUDGET=3） | Forward cascade：不動任何 goal、寫 inject decision outcome（infra 失敗則 re-enqueue 同 decision_id、`763179f`） | 不投影（target=Problem、goal_history 投影只看 Goal-target rows） |
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
- `agent_declined` 在 Builder 是 `needs_decomposition` directive；Forward（`library_sufficient`）與 Librarian 也用**同一 reason string** 走各自的 decline。Backward 沒有此 escape（decomposer 自己、無「需要拆解」一說；退出用 `unprovable` / `return_to_parent` / `shelve` 三條）。
- 詳細的 directive 詞彙設計（4 個 directive × 2 pipeline、何時用哪條、description 規範）見 `docs/archive/design/decline_directives.md`。
- `lake_build_error` 在 Builder 來自 patch 套上去 build 失敗；在 Backward 來自 strategy 組裝（sub-goal sorry stubs + scratch 一起 build batch）失敗。

**Strategist / Librarian failure_reasons（非 Goal-target、不進上面的 master table）**：

這兩個 pipeline 的 target 不是一般 Goal，cascade 與 event 投影都跟 Builder/Backward 不同：失敗**不**動 sub-goal、**不**投影到任何 Context.md（target≠Goal、`events.py` 只看 Goal-target rows）。

Strategist（`Tooling/pipeline/strategist.py`）：
- `strategist_schema_invalid` — `decision.json` 解析過但 `verify_decisions` / 提案包機械檢查不過；同 session resume 修訂,輪數上限 `strategist.verify_retry`(預設 4,與 Adversary 反駁共用計數)
- `strategist_noop` — Strategist 合法地決定 Noop（當下無事可做）；非錯誤、記錄用
- `strategist_proposal_rejected` — Adversary 於修訂輪用盡後仍反駁：提案+全部批評存 `programme_revisions`（status='rejected'）、session 拋棄、下一 wake 只帶一行被拒紀錄盲重推；target cooldown 節流連續拒絕循環；不 burn root.attempts
- 另含共用的 `agent_no_output`

Librarian（`Tooling/pipeline/librarian.py`，Phase 4）：失敗走 `dispatcher._advance_librarian_chain` 的 **per-unit fail-count**（`librarian_fail_counts`、跨 restart 持久）；連續 `LIBRARIAN_MAX_CHAIN_RETRIES`（=2）次 → 該 unit **STALL**（不再 refill、不動 goal、無 shelve）。`librarian_file_busy` 不計數（另一 worker 正持有該檔）。
- **migrate**：`librarian_migrate_not_mechanical`（需 LLM、非純機械 relabel）/ `librarian_migrate_hole_unfilled`（relabel 後仍有 sorry 洞）/ `librarian_migrate_build_failed`（搬出的檔 build 不過）
- **classify**：`librarian_not_classified`（前置 classify 未完成）/ `librarian_schema_invalid`（classify agent 輸出 schema 不合）/ `librarian_bad_work_kind`（dispatch 收到未知 work_kind）/ `librarian_missing_prompt`
- **cleanup**：`librarian_cleaned_build_failed`（精修後 build 不過）/ `librarian_warnings_remain`（build 過但有殘留 warning、Mathlib-PR 零-warning bar 未達；最常見卡點 = unused hypothesis binder + line-length，cleanup 須機械/agentic 清到零）/ `librarian_verify_failed` / `librarian_gate_failed`（per-file Mathlib-PR gate 未過）/ `librarian_axiom_violation`（**post-rewrite 公理閘**：cleanup 的 LLM 改寫段（simplify / near-dup bridge / audit 整檔重寫）是 migrate 公理閘之後唯一能改變 decl 公理集的階段，收尾對最終文本重跑 per-decl `#print axioms ⊆ whitelist`；`axiom` 宣告一律 hard-fail）
- **bridge**：`librarian_bridge_not_mechanical` / `librarian_no_root` / `librarian_axiom_violation`（deliverable 分支：cite_drop 之後對每個 harvested 檔跑 per-decl 公理閘——deliverable 題無 root 可重推、builds-only 蓋不到公理面；classic 題由 Gate B 的 root 閉包 probe 覆蓋）
- **跨檔 / upstream**：`librarian_file_busy`（不計數）/ `librarian_file_owned_by_other` / `librarian_integrity_error`（DB↔檔 drift）/ `librarian_needs_upstream_unresolvable` / `librarian_reopened_upstream`
- **共用**：`agent_error`（Librarian agent spawn rc≠0）/ `agent_no_output` / `agent_declined`（agent 自評該 unit 無法機械化）

**Scholar（paper v2, D11）**：`scholar_no_query`（FetchPaper decision row 無 query——commit 端 bug 或 decision 被手改）/ `paper_unfetchable`（解析成功但無白名單可抓副本；精確請求（DOI/URL）寫進 decision `outcome_detail`、人工通道接手）。兩者 target=Problem、不計 goal attempts、不投影。

`daemon_shutdown`（`_retry.py`）— daemon 收到關閉訊號時 in-flight retry 的收尾 reason；infra-class、不計 attempts、不投影。

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
- `agent_infeasible` / `parent_needs_fix` / `agent_shelved` — 三條 cascade-up decline 都改投成 `infeasible_sub`（到 parent context）、不在自己 goal 的 direct_attempts 重複出現
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

## 4. Crash-window 補償對照表（task #11、2026-07-04 盤點）

狀態傳播非交易性（每個 db helper 自帶 commit；§13 拒絕兩段式）。本表 = 「daemon 死在
commit 邊界之間會留下什麼 × 誰救」的窮舉結論；完整逐窗口證據見盤點記錄（session task #11）。
補償層：**R**=startup `recovery.recover_at_startup`、**T**=per-tick `reconcile_stuck_states`、
**B**=`db.reconcile_settled_inject_outcomes`、**S**=`consistency.consistency_sweep`
（`asterism drift-check` 第二層；`repair_unambiguous` 在 R 內自動修無歧義子集）、
**G**=root integrity gate + `proof_store.inventory`。

| 窗口類 | 半套狀態 | 處置 |
|---|---|---|
| A1/A4 verify promote 檔先行 | alias 檔寫了、strategy 未 succeeded / backup 未清 | R（backup 還原/清理）+ 重新 ready_for_verify ✅ |
| A2 succeeded↔proved 之間 | succeeded strategy + 未 proved goal | R 重開重解（dedupe 收斂）；**S 謂詞** `succeeded_strategy_unproved_goal` 使其可見 |
| A3/F3/F4 sibling sweep / cascade 半途 | terminal goal 下殘留 live strategy、殘活/殭屍子樹 | **R+S**：`repair_unambiguous` 補完 cascade 欠的那一步（proved→superseded、killed→dead、走 checked mutator）；`stalled` 無合法邊、report-only；殭屍樹由 `unreachable_alive_goal` 謂詞可見 |
| B1 revival 檔寫了未 flip | shelved goal 檔=alias 非 stub | **已根治**：`_revive_shelved_alias` 冪等化（只認自己筆跡：本 canonical 的 import+apply 委派）→ 續跑 build-verify+flip；S 謂詞 `revival_pending` 監測 |
| C1 rollback 半途 | 部分還原 | gate 重跑收斂；bisect 可能多殺一條上游良民（明文接受、代價=一次 re-Backward）|
| D1-D6 backward 放置各窗口 | 有檔無 row / 半 INSERT / 佔位 strategy | R（half-baked 清理+orphan sweep+redispatch）✅；D2 殭屍 row 由 S 可見；D6 bulk-dead 的 inject outcome 由 B 補 |
| E1-E5 forward 放置各窗口 | 有檔無 row / 未 detached / 無 backlink | R sweep+redispatch 收斂（可能重複鑄造、slug 撞則失敗回填）；E2 殭屍由 S `unreachable_alive_goal` 可見 |
| F1/F2 inject outcome/batch-wake 遺失 | terminal 但 decision NULL / wake 丟失 | B 補 outcome ✅；wake 由 routine interval 兜底 ♻️ |
| F5/F6 enqueue 遺失 | pending_review / Forward 重排無 queue row | T 每 tick 補 ✅（T 的設計目的）|
| G1-G3 收割/queue 窗口 | worker commit 完成未 cascade / queue row 丟 | R 全套；queue 內容全部可自 durable state 重導出（架構性保證）✅ |
| G2 attempts>dead_attempts | 帳面 drift | **明文接受**：attempts 是 threshold SoT 且該 LLM call 真發生過；dead_attempts 純 forensic |

維護規則：**新增傳播路徑（新的多 commit 序列）必須在本表加一行**、並三選一：指認既有救援層 /
新增 S 謂詞 / 明文接受＋理由。deferred：commit-fault-injection harness（對每條傳播入口掃
「第 N 次 commit 後 crash」、跑三層 reconcile 斷言 sweep 全綠）——等 S 上線觀察殘餘再決定。

---

## 5. 跨參考

- 動態 flow（pipeline 完整流程含失敗）：`docs/data-flow.md`
- goal_history v1 audience 規則 / 實作步驟設計史：`docs/archive/design/goal_history_unified.md`
- DB schema CHECK 與 column 定義：`Tooling/state/db.py`
- cascade 完整邏輯：`Tooling/core/dispatcher.py` `cascade_one`
- session / postmortem 機制：`Tooling/pipeline/builder.py` rc 處理、`pipeline/_drafts.py`
