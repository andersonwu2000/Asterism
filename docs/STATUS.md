# Asterism v2 — Current Status

更新於 2026-05-06（Phase 7 pipeline/session unification 完成）、HEAD `<post-7-E>`、
**602 unit tests green**（8 pre-existing llm_provider 失敗與 Phase 7 無關）。

## 下個 session 接手要做的事

Phase 7 全套已落地、retry 模型整理完畢。下一個架構設計 phase 候選：

**BRIEF.md + LESSONS.md（`docs/dev/agent_brief_lessons.md`）**：
Phase 7 的 reflection trigger 點（pipeline terminal = session terminal）已 by-
definition 對齊。可以開始實作 BRIEF.md（framework auto-render stable invariants）+
LESSONS.md（agent self-managed cross-spawn experience via Edit tool at successful
pipeline terminal）。

**item 12 — Bridge lemma layer**（`docs/dev/bridge_lemma_layer.md` 是起點）。
substrate（命名 + 註解 + retry 模型）已備、Strategist / Forward / Generalize 等
上層 pipeline 可以開始討論。doc 6 個開放決策點仍待 user 拍板。

兩個 phase 都不是嚴格 blocker；user 可選任一切入。

## 近期落地（給 next session 的 context）

**Phase 7 — Pipeline/Session unification**（`4b0d193..<7-E>`，2026-05-06）：
retry 邏輯從 cross-pipeline scheduler-driven 改成 in-pipeline-bounded helper-driven。
心智模型對齊「pipeline 呼叫 = 一個 claude session 把該 goal 處理完」。
- **7-A**（`ad42ea3`）：新建 `Tooling/pipeline/_retry.py`、`run_with_session_retries` helper（dynamic budget、cold/warm sid lifecycle、stale_session in-place re-mint、timeout 強制 exhaust + postmortem）
- **7-B**（`3e9e46b`）：builder.py 接 helper、發現並修 FK ordering bug（helper buffer pending_failures、dispatcher flush 在 pipelines INSERT 之後）、cascade 加 'moot' / 'exhausted' branches
- **7-C**（`61ed022`）：backward.py 對稱接 helper、F53/A retry-reuse 退役（每 pipeline fresh strategy_id）、parse_and_commit 抽出
- **7-C.1**（`4d765ea`）：review fixes — C1 builder wrapper moot 漏處理 / C2 helper threshold 拆 budget+shelve / C3 rc=126/127 早返不耗 budget / L1 dispatcher flush 跳過 moot / L2 agent_declined 改用 entry_kind 路由 / L3 agent_infeasible attempts++ 一次保 1:1。新增 `tests/test_pipeline_retry_helper.py` 20 個 unit test
- **7-D**（`a236fb3`）：drop `goals.builder_session_id` / `backward_session_id` columns（idempotent ALTER TABLE DROP COLUMN migration）+ 移除 4 個 db helper + 清 10 處 vestigial cascade calls + F33/F53 註解全清
- **7-E**：docs sync（本次）

**1:1 invariant**：attempts ↔ dead_attempts 嚴格一致；helper buffer-then-flush 給
all-or-nothing crash 語意（daemon kill 中段、attempts 不動、無孤兒 dead_attempts）。

**新 outcome**：`exhausted`（budget 用盡）/ `moot`（goal 已終態）；五種 outcome
（含 proved/success/failed）涵蓋所有 pipeline 終態。

**新 failure_reason**：`quota_exhausted` (rc=126) / `missing_dep` (rc=127) — 兩者
跟 spawn_fast_fail 一樣不耗 budget、設 cooldown、不寫 dead_attempt；只 spawn_fast_fail
進 CONSEC daemon-exit 計數。

**setting 不變**：BUILDER_THRESHOLD=3 / SHELVE_THRESHOLD=8、總 LLM call 上限不變。

完整設計：`docs/archive/pipeline_session_unification.md`。

---

`205bd4a..43c3a30`（goal_naming + annotation Phase 1-4，2026-05-06）：
- **Phase 1**（`cab25cc` + `948f557`）：Backward sub-goal slug 從 `s<sid>_sub_<N>`
  改成 LLM 自選 descriptive name (`cross_sq_add_inner_sq` 等)、charset/length lint、
  collision framework auto-suffix（`_resolve_slug_collisions` helper）
- **Phase 2**（`cc934ff`）：Builder + Verify 強制 annotation。每個 proved goal 的
  `.lean` 檔頂帶 `-- <slug>: <summary>` line-comment block。空 PROPOSAL.md
  → `agent_no_annotation` failure。`promote_to_alias` 加 annotation kwarg。
- **Phase 3**（`5be9a33`）：F22 playbook 機制完全砍（-790 LOC、刪 `Tooling/playbook.py` +
  兩個 prompt + cli reset 清理 + Context.md section + verify hook）。
  `43c3a30` 順便清掉 6 個 problem 殘留的 stale `playbook.md` 檔。
- **Phase 4**（`dee781c`）：Context.md 新增 `## Proved goals on this problem (grep
  entrypoint)` section、count + path 入口指針、不 push candidate list、agent 用
  grep + Read 自食其力（同 mathlib pattern）。
- **PN root proved e2e**：Sonnet、~48 min 總 wall-clock（30 min budget hit + resume 15 min）、
  depth 8、21 goals。對照 pre-Phase-1-4 同模型 ~30 min depth 2 — annotation 強制
  讓 agent 拆解更深、wall-clock 上升、但機制全 work（無 `agent_no_annotation` 觸發、
  Verify propagate 8 strategies 鏈式 root-proved）。

`27f0f7c..6783e05`（前一輪、goal_history_unified v1）：
- **goal_history_unified v1 完成**（7 commits、見 item 8 詳述）
- **PN Sonnet e2e smoke 通過**：g142-class 修復實證、umbrella render 確認
- **Asterism.yaml default 切 Sonnet**（builder + backward 都 claude-sonnet-4-6）

## 本 session（2026-05-04 ~ 05-05）改動鏈

按 commit 順序：

1. `c6a2117` — **Backward prompt 5 個 skeleton**（exists+property / adapter+main / case dispatch / linear pipeline / induction+step）+ postmortem 加 alternative direction
2. `75f9deb` — **Sub-goal Defs auto-import** — `_ensure_imports_subgoal` 自動加 `import Problems/<p>/Defs`
3. `e9cbdd7` — **Infeasibility escape channel** + TACTIC_TRY 補 `assumption/tauto/exact?` + 刪 `difficulty>=4` hard gate
4. `c63e149` — **entry_kind directive** — Backward 為每個 sub-goal 標 Builder/Backward
5. `234de10` — **刪數字 difficulty** — Manifest `## Entry kind: Builder|Backward`，schema drop 欄位
6. `30392d2` — Backward prompt Rules 合併 stay-abstract directive
7. `9c7fc68` then `b117620` — **two-phase commit-phase 加了又回退**（實證 0% 救活，Sonnet thinking 一旦開始無法中斷）
8. `b117620` — `_safe_glob` 防 Windows reserved-char filename（agent 寫 `won_exact?.lean` 案例）
9. `ab03522` — Manifest `## Tactical` / `## Mathlib hints` → 統一 `## Lemma hints`
10. `8f0d2b3` — **thinking budget cap 1K tokens/min**（核心修復！env `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` + `MAX_THINKING_TOKENS`）

關鍵實證：
- thinking dive 統計（148 個 spawn）：dive median 9K tokens, successful median 3.7K — 10K cap 是邊界
- two-phase commit-phase 失敗：session jsonl 顯示 commit prompt 後 agent 完全沒回應 → Sonnet thinking block 是 atomic
- entry_kind directive：之前 g422/g423 被無條件先 Builder 浪費，新機制讓 Backward 預判跳過 Builder
- infeasibility escape：g363 實證一次 spawn 內構造反例 + escape，省 SHELVE_THRESHOLD-1 次 timeout

## 最近批次（2026-05-04）

按時間倒序，三批改動：

**F55 redesign + F56**（commit `27d46bb`）— 改框架對失敗 spawn 的處理：
- F55 棄「邊寫邊存 PROPOSAL.md」改用「timeout 後 postmortem spawn 寫 _progress.md」。主任務不再要 agent 維護 deliverable，partial 從 deliverable 解耦成獨立側通道。
- F56 砍 worker_kind="Verify"。strategy 驗證改成 dispatcher tick 末端的 housekeeping 步驟（純框架、無 LLM、不佔 worker pool）。F41 LLM 修復同步取消（26 verify 0 觸發）。
- 兩件事一起做，因為 timeout 處理 + verify 收尾都是「失敗/收尾路徑的清理」性質的工作。

**M3**（commit `d045e15`）— `--add-dir <packages>` 修復 mathlib Grep 被拒問題。M1 加寬 allowlist 但仍有 75 次 Grep 拒絕，根因是 F44 narrowing cwd 後，claude permission 把 cwd subtree ∪ --add-dir 當隱式信任邊界，allowlist 被忽略。加 packages 進 add-dir 修。

**docs**（commit `919b1a8`）— `docs/data-flow.md` 新檔（概念敘事、agent 與框架資料流）；`architecture.md` v2.5 → v2.6 反映 F55+F56。

## Proved problems

| Problem | Prover | Wall-clock | Axioms |
|---|---|---|---|
| compactness | Opus | ~25 min | propext, Classical.choice, Quot.sound |
| compactness | Sonnet | ~60 min | 同上 |
| gen_generates | Sonnet | ~30 min | propext, Quot.sound |
| inner_zero_iff_smul | Sonnet | ~21 min | std 3 |
| proj_nonexpansive | Sonnet | ~58 min | std 3 |
| **cantor_xi_measure** | Sonnet | **~4 hr**（含 90min budget exit + 重啟）| std 3 |

cantor 是當前最大 sample（50 goals、depth 4、18 verify）。F55+F56 改動後尚未跑過完整題目 — SG 是首次驗證。

## 信號監控（每次 run 後檢查）

| 信號 | 期望 | 觸發來源 |
|---|---|---|
| `naming_violation` | 0 | F52 + Phase 1 sub-goal naming |
| `patch_signature_mismatch` | 0 | F52 |
| Mathlib Grep denied | 0 | M1 + M3 |
| Cross-Problem read | 0 | F44 sandbox |
| `spawn_fast_fail` | 0（除非 quota）| F46 |
| `quota_exhausted` / `missing_dep` | 0（provider quota / CLI 故障才觸發） | Phase 7-C.1 |
| `pending_failures` flush 數 == `attempts` 增量 | 1:1 不漂移 | Phase 7 helper |
| 新訊號：postmortem `_progress.md` 寫入 | timeout 時寫一次、success 時清掉 | F55 |
| 新訊號：verify housekeeping promote | 每 strategy 一次、可鏈式 | F56 |

## 砍掉但留參考的舊機制

- **F40** Two-phase Builder（commit `2b6ff1a` revert at `232a3e0`）— Phase A 寫 PROPOSAL、Phase B 寫 patch。Haiku 實證證明瓶頸在 patch 品質不在 deliverable miss。除非新 model 失敗模式換成 deliverable miss，不重做。
- **F31** `if "haiku" in model:` substring tier — Asterism.yaml 化後退役，weak-tier 改顯式寫 `(builder.threshold, dispatch.shelve_threshold) = (5, 10)`。
- **F41** Verify-time LLM patch retry — 26 verify 0 觸發，F56 一起取消。實證 Step 1 開始失敗才回頭加。
- **F55 邊寫邊存版**（commit `cdb03b5`，被 `27d46bb` 取代）— 讓 agent 邊寫 PROPOSAL.md 邊 save。實作出來但用戶指出污染主任務注意力，改成 postmortem spawn 設計。

## 待辦（按優先序）

1. **(已做) entry_kind 直接 directive，刪掉 difficulty** — Backward 在每個 `new_<slug>.lean` 標 `-- entry_kind: Builder | Backward`；framework parse 進 `goals.entry_kind`；`next_worker_kind` 第一次 honor directive，attempts ≥ BUILDER_THRESHOLD 強制升 Backward 兜底。Root entry_kind 由 cli init 直接從 Manifest `## Entry kind` 段讀取。Manifest 改為直接寫 binary directive，數字 `## Difficulty` 整個從 schema / 程式 / 測試 / 文件移除（87 個 reference 全清）。

2. **(已做) TACTIC_TRY_LIST 補 `assumption` / `tauto` / `exact?`** — `A → B → A`-shaped 廢題型 Phase 1 直接收工。`linear_combination`（需係數）/ `polyrith`（需 Sage）暫不做。
3. **(已做) Infeasibility escape channel** — `decline_reason: parent_type_infeasible` PROPOSAL.md frontmatter；Builder + Backward 都可 escape；cascade 直接 shelve goal + propagate 上層重拆，不燒 attempts。SG 實證 g363 一次 spawn 內構造反例 + escape 成功。

3a. **(已做後回退) Two-phase commit-phase** — body 8min + commit 2min 嘗試打斷 thinking-dive。實證 0% 救活：Sonnet thinking block 一旦開始無法中斷，commit phase 收到 `--resume` 後再次進 thinking、120s 內 thinking 都沒生成完就被砍。session jsonl 顯示 commit prompt 後 agent 完全沒回應。回退到 body 10min + F55 postmortem 3min 單路徑。

3c. **(已做) Thinking budget cap** — env `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` + `MAX_THINKING_TOKENS=(timeout_sec//60)*1000` 注入每次 claude spawn。1K tokens/min 對應 wall-clock 預算（body 600s→10K, postmortem 180s→3K）。Per-turn cap，agent 觸頂後強制進 output 模式但 partial thinking 保留在 session memory，下個 tool round-trip 又能 think。對症 SG 數據：dive median 9K tokens、successful median 3.7K，10K cap 切掉大半 dive、successful 損失 < 25%。在 claude_cli.py spawn 設 env、不影響其他 provider。

3b. **(已做) `_safe_glob` 防 Windows reserved-char 檔名** — agent 偶爾寫 `won_exact?.lean`（把 Lean tactic `exact?` 當識別字），Windows path API 對 `?` `<>:"|*` 拋 OSError，使 `Path.glob` 整個 dir 掃描失敗。helper 改用 `os.scandir` + `fnmatch`，跳過 path resolve 階段；單一 fix 涵蓋所有 reserved chars。
4. **SG with new framework**（已跑驗證部分機制）— F55 postmortem alternative-direction 確認有效；entry_kind 修補後 root 直接 Backward；尚未跑出完整 root proved。
4. **F38 Gemini live smoke** — quota 恢復後跑
5. **Backward placement 沒驗證 sub-goal body** — `backward.md` 約定 `new_<sub_slug>.lean` 為 `:= by sorry`，但 agent 偶爾 inline 整段 valid proof（SG s75_sub_4 實例：agent 用 `by_contra + ring + nlinarith` 多行收掉），framework 直接吞下、placement 為 `L_<slug>.lean`。**漏洞 (a)**：placement 階段 lint 缺。
6. **Dispatcher 不檢查 file 是否已 sorry-free 就 dispatch** — 承上，即使 `L_<slug>.lean` 已是 valid proof，只要 `entry_kind: Backward` 仍 spawn Backward worker 重證一次，最終 `promote_to_alias` 把 working proof 蓋掉。**漏洞 (b)**：dispatch 前應 quick lake build placeholder file，sorry-free + axioms 在白名單就直接 mark proved 跳過。SG s75_sub_4 → s76 case 實證 redundant work（重花 ~5 min spawn 一個等價 strategy）。
7. **TREE.md 在 root proved 後不更新** — `dispatcher.py:620` 的 "all roots proved" exit 分支只跑 reconcile/prune/library_promote 就 return 0，**沒呼叫 `tree.write_for_target`**。最後 `verify_housekeeping` 把 root cascade-proved 的那輪不觸發 per-cascade tree write，TREE.md 凍結在 root=attempting 的前一刻；prune 又砍 orphan 檔，TREE 內的死分支引用全失效。SG run 2026-05-05 21:10:00 root proved 後實證。**漏洞**：exit 分支應在 reconcile 後重 render 一次 TREE.md。

8. **(v1 完成) Context.md `## Goal history` umbrella + events.py 投影層** — 舊版 4 個失敗 section 散亂 + kind-asymmetric gating + event 邏輯 hard-code 在 renderer。重構：
   - **C1 (commit 3ef9c55)**：新檔 `Tooling/pipeline/events.py` 提供投影函數 + `Event` dataclass + `_NON_AGENT_REASONS` 統一 filter set。`compile_context` 改用 events.\*；agent 看到的 Context.md 外貌 0 變化、純 internal refactor。
   - **C2 (commit 16fd369)**：合 3 個獨立 `##` section 成 `## Goal history` umbrella + 4 sub-section（含新 `### Sub-goals reported infeasible`、cross-goal 投影 sub 的 `agent_infeasible` 到 parent）。companion file rename：`PAST_ATTEMPTS.md` → `PAST_DIRECT_ATTEMPTS.md`、`PAST_BACKWARD.md` → `PAST_VERIFY_FAILURES.md`。Empty bucket 整段省略。
   - **Audit fixes (commit 8712ce5)**：external code review 抓 4 個 bug：(1) agent_declined 兩 section 重複 render (2) infeasible_subs JOIN 多 parent dup row (3) dead_strategies LIMIT-then-exclude 邊界 starve (4) rename comment direction reversed。各修 + 加 regression test。
   - **C3 (commit 403141a)**：砍 `## Why Builder declined this goal` 獨立 section、`agent_declined` 進 `### Direct attempts on this goal`。順手砍 `### Direct attempts` 的 `show_attempts` kind-gate（**SG g142 case 修復**：Backward retry 看到自己 prior `lake_build_error` 歷史）。
   - **C4 e2e validation**（PN Sonnet smoke、~30 min wall-clock）：跑 `proj_nonexpansive` 從零開始驗 v1 機制。Tree depth 2、6 leaf goals + 2 strategies、4 個 lake_build_error warm retry 都接續成功。**g142-class 修復實證**：Goal=2 (root) 第一次 Backward 寫 sub-goal 用 `⟪⟫_ℝ` notation 缺 `open scoped` → expected token error；第二次 Backward Context.md 真實看到自己 prior `lake_build_error` row 進 `### Direct attempts on this goal` sub-section、**第二次 PROPOSAL 明確寫「Fix from previous attempt: ... Added that directive」**、agent 看到並修正、success。Audit fix 4 (`spawn_fast_fail` 不寫 dead_attempts) 確認：4 個 dead row 全 lake_build_error、無 infra noise。仍未自然 trigger：cross-goal `infeasible_sub`（PN 無 type-infeasible）、`dead_strategy` 投影（PN 無 cascade-shelve）— 留將來深題自然實證或 fixture-based unit test。

9. **(已做) Phase 1 `tactic_try` 改用 Mathlib `hint` + 寫回精確 winner** — 演進：N 個 tactic 各跑獨立 lake build → `by first | t1 | t2 | …` 單一 build → 現在 `by hint` 兩階段 build。新流程：(1) probe 寫 `:= by hint`、lake build、parse stdout 的 `info: ... Try these: [apply] 🎉️ <tac>`、(2) confirm 把 sorry body 重寫成 `by <winner>` 再 build 一次。代價：成功時付 2 次 build（confirm 走 warm cache、便宜）。收益：搜尋集合接 mathlib `register_hint` curated set（24+ tactic、自動跟 mathlib 同步、framework 不再維護 TACTIC_TRY_LIST）；artifact 留具名 winning tactic（`won_hint.lean` 內 body 是 `:= by <具體 tac>`、不是 opaque `first | ...` 區塊）。Coverage gap：mathlib 預設 register_hint 不含 `rfl` / `assumption` / `norm_cast` / `push_cast` / `simp` / `ring_nf` / `nlinarith`，靠這幾個才能 close 的 goal 會 fall through Phase 2。實作：`Tooling/pipeline/__init__.py:_HINT_WINNER_RE + _parse_hint_winner` + `pipeline/builder.py` Phase 1 兩階段。

10. **Lake build 耗時占比沒儀表** — 目前 dispatcher log 行只記事件名（`[dispatch] ...`、`[cascade] ...`），**沒帶 timestamp**；agent jsonl 只記 agent CLI 在 session 內的時間，框架層的 `_lake_build` / `_lake_build_batch` / verify Step 1+3 都在 agent 退出後 dispatcher Python 進程內呼叫，**完全不在 jsonl**，也沒 stdout 紀錄。導致無法回答「lake build 占 spawn wall-clock 幾%」這種基本性能問題（user 問過、我先前回 50-75% 是目測印象不是測量）。**最小 instrumentation**：(a) `pipeline/_lake.py` 的 3 個 lake invocation function 加 `time.perf_counter()` 包裝，把 elapsed 寫進回傳值或 print 一行 `[lake] <target> Ns` 摘要；(b) dispatcher log lines 加 ISO timestamp prefix（一次性 logger format 改動）。完成後可以做：每 spawn 算 spawn-wall-clock vs agent-jsonl-active vs framework-lake-elapsed 三者比例，量化 (item 9) 的 `first|...` 改進實際省了多少。前置：item 9 也應該等這個 instrumentation 做完 → 可以 before/after 比較（不然只能信估算）。

11. **(已做) Dedupe `_eligible_ancestors` 過嚴，漏抓 cross-branch 等價 sub-goal** — `dedupe.py:295` 的 candidate 候選池只含 (a) candidate parent_goal_id 的**嚴格祖先鏈**上的 goals + (b) F42 同 parent 的 orphan proved sub。實證：Opus SG run 跑到 75 個 goal 時掃 statement 字串，**有 2 對 cross-branch type-identical 重複 case**：g166 (s95_sub_1, proved at depth 8) ↔ g187 (s106_sub_1, open at depth 10, 37min 後出現)；g172 (s102_sub_1, proved at depth 8) ↔ g200 (s113_sub_3, open at depth 9, 27min 後)。兩對都共一個祖先（g156 / g159）但不在彼此祖先鏈上，所以 ancestor 過濾跳過，dedup 漏。**改進**：candidate 池放寬到「同 problem 內任何 status='proved' 的 goal」（不限祖先鏈、不限同 parent）。安全性：proved goal 已是 leaf proof 沒下游依賴，alias-to-proved 永遠不形成 import cycle；只有 alias-to-open/attempting 才需 anti-cycle 檢查（沿用現行設計）。效能：candidates pool 從 ~10 升到 ~50-100，但 `_batch_isdefeq` 早就是 batched 模式，cost 線性。SG run 預估省 5-15min（每對 dedup hit 省 1-2 個 spawn × Opus 2-5min/spawn）。**不要做**：把 candidate 池無上限放寬到「any goal regardless of status」— 會引入 cycle risk，且 attempting 的 type 可能尚未穩定。

12. **(設計中) Bridge lemma layer — 對齊 parcadei SG 1000 LOC 實作的 root cause** — Asterism SG / cantor 級題目重複展開 cross-product polynomial 是主因（vs parcadei 集中在 12 個 bridge lemma）。問題不是 generalization 也不是 Mathlib API、是 **abstraction**（把代數工作集中在 bridge layer、上層邏輯不再重複展開）。三個方向 (a) Manifest 新增 `## Bridge lemmas` section / (b) 強化 Backward prompt 引導早期寫 `Lemmas.lean` / (c) 接 item 11 dedup 擴大讓 bridge 自動跨 strategy 重用。長期 hook 是 v3 archive 的 Generalizer pipeline。完整設計、開放決策點、不要做清單見 `docs/dev/bridge_lemma_layer.md`。
5. **第三方 deep problem** — cantor 是當前最深，再要更深場景才知道 dedupe / cascade 邊界
6. **Strategist** — 拆 Backward 為 Plan + Decompose；只有 SG 在 entry_kind directive 後仍卡住才真的需要

## 重要參考

- `docs/data-flow.md` — agent 與框架資料流（F55 + F56 概念入口）
- `docs/architecture.md` — DB schema、cascade rules、pipeline 細節
- `docs/OPERATOR.md` — CLI subcommands、env vars、recurring traps

## 用戶 preferences

操作者全域 memory 在 `C:\Users\ander\.claude\projects\D--Hadamard\memory\`，本檔不重複。
