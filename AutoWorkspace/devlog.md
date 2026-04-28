## 指令：

（無）

## Commit：

**C19 R1 — P3 spike batch (spike-008/009/010/011)**

Hash: `70d1c54`

### 改動摘要

- **spike-008 IH-trap similarity metric**：Python fixture `spike008_similarity.py` 實作 Token Jaccard + Identifier Overlap，12 個合成 case（6 IH-trap / 5 非 IH-trap / 1 boundary）。結果：Token Jaccard @ 0.85 → FPR=0.0 / FNR=0.667；Identifier Overlap FPR=0.333 不適用。決策 D-08-1：threshold 維持 0.85、採 Token Jaccard。
- **spike-009 isDefEq 性能**：best-effort 分析（無 lake env）。估算 batch dedupe 27s < 30s timeout；確認 import Lean only（不 import Mathlib）；iff_lite FP 代價可接受。決策 D-09-1：batch mode、timeout=30s、iff_lite 預設關閉。
- **spike-010 search_cache hit rate**：best-effort 分析（無 P2 real log）。Mathlib scope hit rate ~80-90%，local_goals ~50-60%，TTL 設定符合理論。決策 D-10-1：TTL 維持 phase doc 預設。
- **spike-011 SQLite json_patch atomicity**：實測（Python multiprocessing，N=100）。A 策略（Python rw）lost=100/100；WHERE filter 無效（A2 lost=100/100）；atomic SQL json_insert 0 lost（PASS）；app-level Lock 0 lost（PASS）。決策 D-11-1：採 atomic SQL json_insert，不需 app-level lock。
- **fixtures**: `Tooling/tests/fixtures/spikes/spike008_similarity.py` + `spike011_json_patch.py`

### Caveats

- spike-009/010 為 best-effort（caveat 在 docs/spikes.md 明確標註）；需 D:/Hadamard 真環境補 quantitative data
- 全套 420 pass + 2 skipped manual gate、0 regression

---

**C18 R3 — Fix R2 audit findings (silent fallback + naming + doc registration)**

Hash: `e2503a5` — P2 C18 R3: fix R2 audit findings.

### 改動摘要

- **HIGH-1 [silent-failure]**: `BACKWARD_MOCK` unknown 值 silently 落到真 LLM path → 改為 `success_leaf` only、其他值 raise `ValueError`。連續 C13–C17 silent-failure red-line discipline 維持。
- **HIGH-3 [naming convention]**: BACKWARD_MOCK / BACKWARD_FORCE 拆分 per test_hooks.md §規則「`*_MOCK=spec` replaces real behavior；`*_FORCE=value` forces specific outcome」。C18 ship `BACKWARD_MOCK=success_leaf`（取代行為）+ `BACKWARD_FORCE=exhausted|unproductive`（強制 outcome）。預先處理 P3 BACKWARD_FORCE collision、P3 再擴 `succeed` 值。
- **HIGH-2 [doc registration]**: docs/dev/test_hooks.md 註冊兩 hook、phase tag P2；既有 P3 `BACKWARD_FORCE` 行 promote 至 P2（C18 引入語意凍結）+ 留 P3 行記 `succeed` 擴值。boundary tension 解：task.md ## 唯讀檔案 寫 test_hooks.md「加新 hook 才動」= editable 條件、orchestrator approve。

### Skipped (documented)

- MED-4 AC#0 daemon-mode variant: AC#3 + AC#9 已分別覆蓋 daemon path、subprocess daemon test 有 hang/race 風險、auditor 標 optional。
- MED-5 AC#10 invalid-key edges: spec 不要求。
- MED-6 AC#9 CPU-idle clause: CI flake 風險、latency-cap proxy 保留 + docstring caveat。
- LOW-7 AC#7 fixture refactor: 手動 pipeline INSERT 功能等價、純 refactor 邊際值。
- LOW-8 test helper de-dup: 推遲到未來 test-infra cleanup cycle。

### Hybrid mode 第二 cycle 結論

R3 由 orchestrator (Opus 4.7) 直接做。**hybrid R1 仍 miss silent-fallback in BACKWARD_MOCK**（即使我 Opus、即便 prompt 有 silent-failure pattern 警告）— 證明 R2 Audit 獨立 review 不可省、即使 hybrid mode。Co-Authored-By: Claude Opus 4.7。

### Caveats

- 全套 420 pass + 2 skipped manual gate、0 regression。
- 無新 tests（unknown-value path 為 structural raise、code path 結構性可證）。

---



**C18 R1 — P2 demo + acceptance tests #0-#11**

Hash: `e587aa0` — P2 C18 R1: P2 demo + acceptance tests #0-#11.

### 改動摘要

- **CLI `goal add --spec`（P2 path）**：與既有 `--leaf-strategy`（P1 legacy）以 `add_mutually_exclusive_group(required=True)` 並存。`--spec STMT` 寫 `theorem <slug> : <stmt> := by sorry` 範本到 `Problems/<p>/Goals/<id>_<slug>/<slug>.lean` + INSERT goals row（`question = STMT`）+ enqueue Backward(target=goal_id)。`--leaf-strategy` 維持 P1 行為不動。
- **`Backward.run` 加 `BACKWARD_MOCK` env hook**（mutually exclusive：`success_leaf` / `exhausted` / `unproductive`）。`success_leaf` → `_mock_success_leaf` 跳過 agent、寫 leaf strategy `.lean` (`theorem ... := by sorry`) + INSERT strategy row + 回 success。Builder 接 LAKE_MOCK=proved 把 sorry 視為 proved → cascade → goal proved。
- **`_cascade_backward` 對 success+leaf 內聯 enqueue Builder**：sync mode (`run --once`) 不跑 `_run_structural_refill`（會踩 P1 acceptance 的單 task 場景無限重派），直接判 `result.outcome=='success' AND result.subgoal_ids 為空` → INSERT Builder queue row。有 sub-goals 的情況仍由 daemon mode BFS 處理。
- **`Tooling/tests/test_phase2_acceptance.py` 新增**（537 行、14 tests）：
  - **AC #0** TestAC0DemoSubprocess.test_demo_spec_to_proved（**single sanity gate**；subprocess full chain `init → goal add --spec → run --once → goal show G_root` 帶 LAKE_MOCK + BACKWARD_MOCK + PRINT_AXIOMS_MOCK + PYTHONIOENCODING=utf-8 對 Windows cp950 兜底；assert "proved" + "classical" 在 stdout）
  - **AC #1** TestAC1AgentScopeIsolation（chain.run None → Backward exhausted）
  - **AC #2a/#2b** TestAC2WallClock（skipped；warm/cold cache 真 lake env 為 manual gate）
  - **AC #3** TestAC3CascadeUpward（sub-Goal proved → `_run_structural_refill` enqueue Builder for parent strategy）
  - **AC #4** TestAC4MultiRowCommitTX（COMMIT_FAULT=after_step1 + recover_scan 對 begin_batch 的 strategies/sub-goals/junction 全清；patch validator + self_verify 跳過 Lean）
  - **AC #5** TestAC5ValidatorHypothesisCarry（patch validator return ValidatorError → Backward 達 max_retries → exhausted；assert chain.run.call_count == max_retries）
  - **AC #6** TestAC6TrustSetConstruction（PRINT_AXIOMS_MOCK + 寫 META.md axioms whitelist → cascade → trust_set JSON 含三 axiom name + kind=lean_axiom）
  - **AC #7** TestAC7AcceptRuleReject（META.md axioms 移除 Classical.choice + theorem 用之 → cascade reject → goal stays !proved + dead_attempts 寫入 + emit `("control_signal","pause")`；fixture 補 INSERT pipeline row 滿足 dead_attempts FK）
  - **AC #8** TestAC8DMaxBound（depth=12 vs depth=3 兩 goal → refill 把 depth=12 UPDATE shelved + 不 enqueue Backward；shallow 仍 enqueue）
  - **AC #9** TestAC9DaemonIdle.test_daemon_responds_to_shutdown_within_5s（CPU idle assertion 換成 latency cap：thread put shutdown 後 < 5s 退）
  - **AC #10** TestAC10ModelResolutionTwoLayer（META.md `models: { backward.agent: opus }` → ModelResolver(meta_models=meta.models) 回 opus；無 META → 框架 default sonnet/haiku）
  - **AC #11** TestAC11RetryStopGap（5 fail → BFS skip / 4 fail → 不 skip / fresh reactor → counter 重置 三 case）
- **Test infra fix**：`_args` helper 在 `test_cli.py` + `test_phase1_acceptance.py` 從 MagicMock 改 argparse.Namespace。MagicMock 對 unset attr 回 child MagicMock，破壞 `getattr(args, 'spec', None) is None` 檢查。

### Hybrid mode 第二 cycle

R1 由 orchestrator (Opus 4.7) 直接做、未 spawn Sonnet Executor。本 cycle 量大（5 file 改 + 537 行新 test file）但結構規律、無 silent-failure 設計題；hybrid 證明可承大型 cycle。Co-Authored-By: Claude Opus 4.7。

### Caveats

- 全套 420 pass（+14），0 regression。
- AC #2a/#2b 無法在 CI 跑（需真 lake env + Mathlib + claude CLI）→ skipped；對應 manual gate 為 P1→P2 transition demo verification（state.md ## P1 done note 已記錄類似步驟，P2→P3 同樣需 orchestrator 介入跑）。
- AC #9 daemon idle CPU 假設不直接驗（timing test 在 CI 易 flake）→ 改驗 latency cap < 5s（spec 字面 30s 可接受、5s 體現 `_event_queue.get(timeout=2)` 真實 wake）。
- AC #1 spec 字面要求「runtime 偵測 agent 寫 staging 之外」→ 真實機制在 Provider 內、本 cycle 用「chain returns None → Backward exhausted」覆蓋下游路徑而非真實 evil prompt 跑 provider，後者待 P5 multi-provider integration test 再加。
- BACKWARD_MOCK 是 test-only hook，已 docstring 標註；對齊 LAKE_MOCK / PRINT_AXIOMS_MOCK / COMMIT_FAULT 既有命名公約。

---



**C17 R3 — Fix R2 audit findings (silent-failure regression x3 + --daemon forward-compat)**

Hash: `340675c` — P2 C17 R3: fix R2 audit findings.

### 改動摘要

- **HIGH-1 [forward-compat]**：`--daemon` flag re-added 為 P1 legacy alias（no-op；P2 default 已是 daemon）。修復 phases.md line 72「舊 flag 仍可用」違反。`cli.py:p_run.add_argument`。
- **HIGH-2 [silent-failure]**：`_poll_db_control_signals` `sqlite3.Error` → emit `("fatal", ...)` 而非 silent return。沒這個 `asterism stop` 訊號可能 silently dropped、user 無從察覺 daemon fail to receive。
- **HIGH-3 [silent-failure]**：`_register_scheduler` INSERT fail → emit fatal + raise FatalError（fail-shut）。silent-swallow 會讓 daemon 跑成 zombie 而 `asterism stop` 撈不到。
- **MED-1 [silent-failure]**：`_unregister_scheduler` `except Exception:` 收窄至 `sqlite3.Error` + emit fatal best-effort（shutdown path 不 raise）。
- **MED-2 [test gap]**：+6 IPC path tests（TestDbControlSignalPoll x4 + TestSchedulerRegistration x2）+ 1 CLI test（test_run_daemon_flag_still_parses）。

### Hybrid mode 試點

本 R3 由 orchestrator (Opus 4.7) 直接做、未 spawn Sonnet Executor。原因：silent-failure pattern 在 C11/C12/C13/C15 R1 已 4 次 regression、即便 prompt 加 ⚠️ 警告 Sonnet 仍漏；改 Opus 直接做斬斷 regression loop、保留 R2 Auditor (Opus, fresh session) 獨立 review。Co-Authored-By: Claude Opus 4.7。

### Caveats

- 全套 406 pass（+7 vs 399），0 regression。
- schedulers liveness 仍最小版：register/unregister 改 fail-shut、但 heartbeat 缺失 + crash detection 留 P6（acceptance #11 範圍）。
- `--daemon` flag 加回為純 no-op（args.daemon=True 時也走 daemon 路徑）；既有 `cmd_run` 邏輯不變。

---



**C17 R1 — CLI daemon mode**

Hash: `40c978c` — P2 C17 R1: CLI daemon mode (run --daemon default + asterism stop)

### 改動摘要

- **`asterism run` 預設 daemon mode**：`cmd_run` 改為無 `--once` flag 時呼叫 `Reactor.run_daemon()`；`--once` 保留 P1 legacy。移除 `--daemon` flag（原 no-op，現 default 已是 daemon）。
- **`asterism stop` 新 subcommand**：`--signal <pause|resume|shutdown>`（default: shutdown）、`--all`（alias for shutdown）。無 scheduler row 時印 "no scheduler running" exit 0；有 scheduler 時 INSERT `events` row。
- **IPC 機制**：DB `events` table，`kind='control_signal'`，payload `{"action": "...", "source": "cli"}`。`source="cli"` 標記區分外部訊號與 daemon 內部 diagnostic events（避免 feedback loop）。
- **Reactor._poll_db_control_signals()**：每 ~2s 撈 `events WHERE id > _last_seen_ctrl_id`，過濾 `source=cli`，合法 action 放入 `_event_queue`。daemon 啟動時 snapshot 當前 max ctrl id 以忽略歷史 row。
- **run_daemon loop**：`queue.get(timeout=min(tick_interval - elapsed, 2.0))` 確保 <5s 控制訊號回應；structural refill 仍 30s 一次。
- **schedulers table 啟用**：daemon 啟動 INSERT，shutdown/finally DELETE。`cmd_stop` 先檢查 count。

### Caveats

- scheduler liveness 最小版：只有 register/unregister，無 heartbeat 更新（P6 接手）；crash 時 row 留在 table，`asterism stop` 誤判 scheduler 存活 → 仍 INSERT event（daemon 已無，event 留在 DB 但無副作用）。
- `--daemon` flag 從 parser 移除（原 P1 no-op）；`test_run_daemon_parses` 換成 `test_run_default_no_once_flag`。
- `test_cli.py` 45 pass；全套 399 pass，+9 vs C15 R3 baseline 390。

---



**C15 R3 — Fix R2 audit findings (silent-failure regression x3 + commit_state filter + accept reject)**

R2 抓 2 HIGH + 3 MEDIUM 必修 + 6 LOW（含建議）。重點 silent-failure 三紅線重犯（C13/C14 R3 已警示），R3 全修。**指令：無**。

---

**Fixable（HIGH + MED 必修）**：

- **#1 [HIGH-1]** `_run_pipeline_thread` 把 FatalError 與其他 Exception 都 silently 轉成 BuilderResult exhausted + DB-only fatal、不 emit `("fatal", ...)` 到 in-memory `_event_queue` → daemon 不 halt。R3 split：
  - `except FatalError` → emit `("fatal", error)` to `_event_queue` + return（不 emit pipeline_finished）
  - `except Exception` → emit fatal + 對 Backward task 用 `BackwardResult(outcome="exhausted")`、Builder 用 `BuilderResult(outcome="exhausted")`（之前一律 BuilderResult，型別錯）
  - +2 tests `TestThreadFatalRouting::test_thread_unknown_kind_emits_fatal_event_to_queue` / `test_thread_internal_exception_emits_fatal_and_pipeline_finished`

- **#2 [HIGH-2]** Accept rule reject 路徑只 emit cascade event、缺 `dead_attempts` INSERT + 缺 emit `("control_signal", "pause")`，違反 architecture.md line 480 + acceptance #7。R3：
  - 新增 `_record_accept_reject_dead_attempt(goal_id, strategy_id, rejected)`：lookup Builder pipeline_id（FK `dead_attempts.pipeline_id`）、INSERT row with `outcome='trust_set_rejected'` + summary `"trust_set rejected: <axioms>"`
  - reject branch 後 `self._event_queue.put(("control_signal", "pause"))`
  - 防 silent skip：pipeline_id lookup 失敗時 emit `accept_rule_rejected_no_pipeline_id` 警告 event（不靜默丟）
  - +1 test `TestAcceptRuleReject::test_accept_rule_reject_writes_dead_attempts_and_emits_pause`

- **#3 [MED-1]** `_cascade` print_axioms RuntimeError/OSError silently fallback `trust_set=None` + 仍 mark proved → accept rule bypass。R3 加 `strict_trust_set` 參數：
  - **P2 daemon path**（`_cascade_builder` → `_cascade(strict=True)`）→ fail-shut：emit `trust_set_construction_failed` event + pause control_signal、不 mark proved
  - **P1 sync path**（`_dispatch` → `_cascade(strict=False)` 默認）→ silent fallback 保 P1 acceptance 兼容（P1 無 accept rule contract、phase 1 demo 無 lake 安裝/配置）
  - 既有 `test_trust_set_null_when_lake_unavailable` 拆兩 test：`test_trust_set_construction_failure_strict_is_fail_shut`（strict path）+ `test_trust_set_construction_failure_lenient_silent_fallback`（P1 sync path）

- **#4 [MED-2]** BFS query 不過濾 `commit_state='live'`、mid-commit pending row 會被誤撈。R3 兩 SQL 加 `AND commit_state = 'live'`：
  - `_bfs_enqueue_backward` SELECT goals 加
  - `_bfs_enqueue_builder` SELECT strategies 加
  - +2 tests `TestBFSCommitStateFilter::test_bfs_skips_pending_commit_state_goal` / `test_bfs_skips_pending_commit_state_strategy`

- **#5 [MED-3 最小版]** `_cancel_running_for_goal` no-op + step1_stale_filter no-op = stale Backward 跑完 commit orphan rows。R3 不實作信號通道（thread pool 不能 SIGTERM）、改 docstring + `_handle_pipeline_finished` 後加 NOTE comment 標記此 P2 接受妥協、明點 P3 step1_stale_filter / P4 subprocess SIGTERM 接手

---

**LOW（順手做）**：

- **#6 [LOW-1]** `_handle_control_signal` else: emit `unknown_action` 警告 event
- **#7 [LOW-2]** `_dispatch_event` `task_checkpoint` 顯式 branch（spec'd 丟棄）+ unknown kind else: emit `unknown_event_kind` 警告 event

---

**LOW-3 反轉決策**：audit 建議 P1 sync `_dispatch` Builder branch 接 `_cascade_builder` 對齊 daemon 行為。R3 試做後發現破 phase 1 acceptance test `TestAC7SorryDetection::test_sorry_strategy_exhausted_with_dead_attempts`（該 test 要求 exhausted Strategy → goal 仍 'open'，但 `_cascade_builder` 會 mark dead → 全 dead → goal shelved）。R3 reverted、改在 `_dispatch` docstring 自陳「P1 sync 與 P2 daemon 行為的 intentional asymmetry」、對齊 audit R2 finding H 已 noted 該不一致。

**LOW-4 / LOW-5 / LOW-6** 暫不做（time-box）：
- LOW-4 paused-resume buffer test：邏輯已 cover by `_handle_control_signal` / `_try_spawn_from_queue` 既有 unit tests
- LOW-5 daemon cascade fatal end-to-end：threading 整合 test 較重，P3 隨 daemon CLI 接入再加
- LOW-6 daemon idle CPU≈0 explicit test：acceptance #9 留 C18 demo 驗

---

**Test 結算**：
- `pytest Tooling/tests/test_scheduler.py` → **60 passed**（R1 baseline 54 + R3 新 6 = 60）
- `pytest Tooling/tests/` → **390 passed**, 9.46s（R2 baseline 384 + R3 新 6 = 390、0 regression）
- `git diff --stat HEAD~1 HEAD` → 2 files: `scheduler.py` (+196) / `test_scheduler.py` (+225)
- commit：`d49ed5d P2 C15 R3: fix R2 audit findings (silent-failure regression x3 + commit_state filter + accept reject)`

**已知 caveat**：
- `strict_trust_set` 二態 P1 vs P2 兼容妥協：production daemon path 嚴檢、P1 `--once` sync path 容錯。實務上 P2 用戶該走 daemon mode（C17 CLI 接、C18 demo 驗）；`asterism run --once` 是過渡期工具
- `dead_attempts.pipeline_id` FK lookup 用「最新 Builder pipeline for strategy」啟發式：在 daemon 流程 OK（Builder 必先寫 pipelines row 才走到 cascade），但 race / restart 邊緣可能查無 → R3 emit 警告 event 顯式記錄、不靜默
- LOW-3 P1 sync `_dispatch` Builder branch 仍走 `_cascade` 不接 `_cascade_builder`、`--once` 模式 exhausted Strategy 不 mark dead；audit R2 finding H 已 noted、phase 1 acceptance compat 優先

---

**C14 R3 — Fix R2 audit findings（1 HIGH + 2 MEDIUM 必修 + 4 LOW 順手）**

R2 抓 1 HIGH + 2 MEDIUM + 4 LOW + 5 noted。**Audit 評估**：7 fixable 全合理，無不合理需暫停的點。**指令：無**、R3 全修。silent-failure pattern 本 cycle 字面避開維持 ✓。

---

**Fixable（全修）**：

- **#1 [HIGH 必修]** prompt template `by simp [...]` example 與 `_replace_proof_body` auto-prepend `by` 雙端衝突 → demo 燒 retry budget；agent literal 學壞 example 概率高。R3 雙保險：
  - **(A) `docs/prompts/builder_tactic_llm.md`**：example 統一無 `by`（`simp [...]` 取代 `by simp [...]`）+ 加明文 "**The framework prepends `by` automatically — DO NOT include a leading `by` in your tactic.**" + 補單 term-mode 提示「prefix with `exact`」
  - **(B) `Tooling/pipelines/builder.py:_replace_proof_body`**：`tactic.lstrip().startswith("by ")` → strip 兜底；docstring 自陳「Defensive strip ... avoids `:= by by simp ...` parse errors when agent imitates a stale example」
  - +1 test `TestLeadingByStrip::test_tactic_proof_with_leading_by_handled`（agent 回 `by simp [add_zero]` → staging 為 `:= by simp [add_zero]`、不是 `:= by by simp`、整合 self_verify proved 路徑）

- **#2 [MEDIUM 必修]** `_tactic_llm_loop` 失敗 path 不寫 `dead_attempts` → cross-run failure_replay 對 agent 路徑教訓 0 覆蓋、N_block_after_failures=5 retry 機制白費。R3 補三處寫入：
  - **chain exhausted**：response is None → `_record_dead_attempts([{tactic="<chain_exhausted>"}])`
  - **self_verify fail per-iter**：`_record_dead_attempts([{tactic=f"tactic_llm: {tactic_code[:80]}"}])`、retry 從 step 4
  - **max_retries 用盡**（parse 路徑或 self_verify 路徑）：迴圈外總結 `_record_dead_attempts([{tactic="<tactic_llm_max_retries>"}])`
  - parse fail 內仍純 retry（無 per-iter 寫入），但最終 max_retries 摘要會 cover
  - +3 tests：`TestTacticLlmDeadAttempts::test_chain_exhausted_writes_dead_attempt` / `test_self_verify_fail_writes_dead_attempts`（self_verify 連 max_retries 次 fail → N 條 tactic_llm: 行 + 1 條 max_retries 摘要）/ `test_max_retries_with_parse_fail_writes_summary`
  - +1 test `TestFailureReplayCrossRun::test_prior_run_tactic_llm_failures_visible`（Run 1 寫入 → Run 2 with k_digest=20 prompt 含 "exact zero_add"）

- **#3 [MEDIUM 必修]** `pipelines.session_id` 不寫 → phase2 §引入元件 §DB table line 156 字面 violation + 與 backward.py（C13 R3）parity break。R3：
  - `_insert_pipeline(p_uuid, session_id)` 改簽 + SQL 加 `session_id` 欄
  - `run()` 提前生 `session_id = str(uuid.uuid4())`、傳給 `_insert_pipeline` + `_run_all_stages`
  - `_run_all_stages` 簽加 session_id 參數、移除內部 `session_id = str(uuid.uuid4())`
  - tactic_try-only path（chain=None）也帶 session_id（informational、不 gate）
  - +2 tests：`TestPipelineSessionId::test_pipeline_row_has_session_id_on_proved` / `test_pipeline_row_has_session_id_on_chain_run`（驗 DB row session_id 與 chain.run 收到的 session_id 一致）

- **#4 [MEDIUM 建議修]** `_run_tactic_llm` `scope_dirs=[staging_dir]` 改 `[problem_dir, staging_dir]`、`problem_dir = base_dir/Problems/<problem>` → 對齊 phase2 §In line 16「Problem 目錄 + staging dir」字面、agent 能 read Defs.lean 知道用戶自定 def/import。+1 test `TestScopeDirs::test_scope_dirs_includes_problem_dir`

- **#5 [LOW 建議]** `_record_bad_goal` 兩 `with self.conn:` block 合單一 TX（sub-Goal + 父 Goal atomicity）；inline comment 自陳「process crash mid-write would otherwise leave half the cascade record」。既有 `test_bad_goal_writes_parent_dead_attempts` 仍 PASS、不另補 fault test

- **#6 [LOW 建議]** `_finish_pipeline` 加 inline comment 說明「needs_decomp/bad_goal 為 agent 早退、pipeline-level status 仍 failed、cascade 只 trigger 在 outcome=proved」。邏輯不變

- **#7 [LOW 依附 #2]** `_tactic_llm_loop` 每輪入口 `dead_attempts = self._failure_replay()` refresh、agent 能看到自家 self_verify 失敗教訓。配合 #2 寫入 + #7 refresh 形成完整 within-run learning loop。`_run_all_stages` 內舊 pre-loop `failure_replay()` 移除（dead code）+ session_id 移除（移到 run() 提前）

---

**Test 修正**：無 regression、既有 37 全保留 PASS（R1 baseline）

**驗證**：
- `pytest Tooling/tests/test_builder.py` → **45 passed**（R1 37 + R3 +8 = 45、0 regression）
- `pytest Tooling/tests/` → **350 passed**, 2.89s（R1 342 → R3 350、0 regression）
- `git diff --stat HEAD~1 HEAD` → 3 files: `builder.py` (+108 -30) / `test_builder.py` (+287) / `builder_tactic_llm.md` (+6 -3)
- commit：`7fe9ee9 P2 C14 R3: fix R2 audit findings (1 HIGH + 2 MEDIUM + 4 LOW)`

**Noted（不修）**：#8 跨 phase 規則對齊（已 ✓）/ #9 silent-failure 三紅線本 cycle 字面避開（已 ✓）/ #10 lake_timeout=600.0 保守 / #11 chain=None P1 fallback / #12 `_replace_proof_body` rfind P3 punt（#1B 兜底已部分緩解）

**已知 caveat**：
- K_DIGEST=5 與 tactic_try 5 條的視窗碰撞：跨 Builder run 時 Run 2 的 tactic_try 寫入會擠出 Run 1 的 tactic_llm 教訓。`test_prior_run_tactic_llm_failures_visible` 驗證需 k_digest=20 才能跨 run 撈回；P3 `goals.blocked_pipelines` 持久化 + 改 failure_replay 語意（filter agent rows）可解
- `_replace_proof_body` rfind(':=') P2+ 仍未改寫成 Lean parser；agent 寫含 nested `:=` 的 tactic body 仍可能 parse 錯，docstring 已自陳留 P3
- chain=None tactic_try-only path 也帶 session_id：欄位永遠非 NULL（與 backward.py 一致），但無實際 agent session 對應、純 informational

---

**C14 R1 — Builder agent 升級（failure_replay + tactic_llm + self_verify 抽出）**

### 交付物

1. **docs/prompts/builder_tactic_llm.md**：tactic_llm agent prompt template v1
   - 插槽：`{{GOAL_PROBLEM}}` / `{{GOAL_SLUG}}` / `{{GOAL_STATEMENT}}` / `{{DEAD_ATTEMPTS}}` / `{{CANDIDATE_LEMMAS}}`
   - 三選一輸出：`{"tactic_proof": "..."}` / `{"needs_decomposition": true}` / `{"bad_goal": "..."}`

2. **Tooling/pipelines/builder.py** 升級：
   - **stage sequence**：`tactic_try → failure_replay → find_lemmas → tactic_llm → self_verify → commit`
   - `_failure_replay()`：query `dead_attempts WHERE target_id=strategy_id AND target_kind='Strategy' ORDER BY ts DESC LIMIT K_digest`，k_digest=5
   - `_find_lemmas()`：stub，回 `[]`（P3 search subsystem 接）
   - `_run_tactic_llm()`：透過 `FallbackChain.run()` 呼叫，`model_tier = resolver.resolve("builder", "tactic_llm")` → 預設 haiku
   - `_parse_tactic_response()`：解析 JSON code block，無有效 key → None → retry
   - `_tactic_llm_loop()`：三出口 dispatch + self_verify + T_wall check
   - `_self_verify()`：獨立抽出，`run_lean` 結果必 `outcome == 'proved'` 才回 True（**silent-failure 防線**）
   - `_record_bad_goal()`：bad_goal 時寫 dead_attempts for goal + best-effort parent goal
   - **P1 backward-compat**：`chain=None` → 走 tactic_try only，行為與 P1 完全一致
   - `_run_all_stages()` 抽出、`run()` 統一呼 `_finish_pipeline` + `_emit_event`

3. **Tooling/tests/test_builder.py** +21 tests：
   - `TestFailureReplay` (4)：reads rows / k_digest limit / ignores other strategy / feeds into prompt
   - `TestTacticLlmDispatch` (8)：tactic_proof proved / pipeline row / needs_decomp / pipeline row / bad_goal outcome / dead_attempts / parent dead_attempts / chain exhausted
   - `TestSelfVerify` (5)：proved→True / exhausted→False / hasSorry→False / timeout→False / retry-on-fail
   - `TestSilentFailureGuard` (4)：non-proved→dead path / JSON parse fail→retry / missing keys→retry / tactic_try non-proved→not committed

### 驗證

- `pytest Tooling/tests/test_builder.py` → **37 passed** (+21 new, 16 P1 preserved, 0 regression)
- `pytest Tooling/tests/` → **342 passed**, 2.76s（321 → 342，0 regression）
- `git diff --stat HEAD~1` → 3 files: `builder.py` / `test_builder.py` / `builder_tactic_llm.md`
- commit：`809b111 P2 C14 R1: Builder agent upgrade`

### 已知 caveat

- `_find_lemmas` stub 回 `[]`：prompt 的 `{{CANDIDATE_LEMMAS}}` 顯示 "(none)"，P3 search subsystem 接手後補
- `tactic_llm` 路徑的 `_replace_proof_body` 使用 rfind(':=')，對 LLM 生成的複雜 proof body（含 nested `:=`）可能不正確；spec 注釋已標明 P2 simplification
- `_record_bad_goal` 的 parent goal 查找是 best-effort：root Goal 無 strategy_subgoals FK 時不寫 parent dead_attempts（正確）
- `chain=None` 走 P1 fallback：fully backward-compat，現有 16 P1 tests 全過

---

**C13 R3 — Fix R2 audit findings（2 HIGH + 1 MEDIUM 必修 + 4 順手修 + 1 可選補）**

R2 抓 2 HIGH + 1 MEDIUM + 5 LOW + 6 noted。**Audit 評估**：14 項全合理，無不合理需暫停的點。**指令：無**、R3 直接修。R3 必修 #1/#2/#3，順手修 #4/#5/#7/#8，補 #12（帶動 #6 自動解決）。

---

**Fixable（全修）**：

- **#1 [HIGH 必修，跨 cycle 擴 commit.py]** strategy_subgoals junction insert 拆出 begin_batch TX、phase2 line 30 + acceptance #4 字面違反；對 COMMIT_FAULT after_step2/3 必 FK crash。R3 全修：
  - **`Tooling/commit.py`**：加 `_TABLES_WITHOUT_COMMIT_STATE = frozenset({"strategy_subgoals"})`、`begin_batch` 加 `junction_ops_factory: Callable[[list[int]], list[dict]] | None` 參數 — junction ops 在同一 TX 內、main ops 後執行（讓 caller 用 main ops 的 auto-increment IDs 構 junction rows）；junction ops 強制 `op='insert'` + table ∈ junction set（misuse → ValueError）；main ops 不可指向 junction table（misuse → ValueError）
  - **`Tooling/commit.py`**：`recover_scan` INSERT-rollback path 對 `pending strategy DELETE` 先 `DELETE FROM strategy_subgoals WHERE strategy_id = ?`、對 `pending goal DELETE` 先 `DELETE FROM strategy_subgoals WHERE subgoal_id = ?`、再 DELETE 主 row（cascade cleanup 順序遵 FK 約束）
  - **`Tooling/pipelines/backward.py`**：`_commit` 重構，junction inserts 透過 `_make_junction_ops(ids)` factory 進同一 begin_batch TX；`created_by=pipeline_id` 也補上（pipelines row 由 `_insert_pipeline` 先寫、FK 不違反）
  - +5 tests in `test_commit.py` `TestBeginBatchJunction` + `TestRecoverCascade`：junction in-TX / main op cannot target junction / factory non-junction raises / factory non-insert raises / main fail rolls back junction / pending strategy cascade / partial files consistent
  - +3 tests in `test_backward.py` `TestCommitBatch`：`test_commit_fault_after_step1/2/3_consistent_recover`（after_step1 全 rollback、after_step2/3 一致 recover、無 orphan junction）
  - 既有 `test_commit_fault_propagates`（after_step1 path）保留 PASS

- **#2 [HIGH 必修]** `_self_verify` 不檢查 `lake_result.outcome` / `messages` → silent-PASS、pipelines.md §2 stage 7「[fail → retry from step 4]」字面違反、**silent-failure 模式第三次重複**（C11 R2 #3+#4 / C12 R2 #1 同類 pattern 已字面命名）。R3：
  - 改名 `_self_verify` → `_self_verify_per_file`、return type 改 `tuple[bool, list[dict]]`：`hasSorry` only message kind 視為 PASS（sorry stub 預期）；其他 message kind（`error` / `warning` / 任何 non-hasSorry）或 `timed_out=True` 視為 FAIL
  - `run()` 主迴圈拆出 `_run_loop`，對 `not all_pass` 走 `continue`（retry agent stage、達 max_retries → exhausted）
  - +4 tests `TestSelfVerifyRetry`：`test_lake_elab_error_triggers_retry` / `test_lake_timeout_triggers_retry` / `test_hassorry_only_passes` / `test_mixed_messages_with_non_sorry_fails`

- **#3 [MEDIUM 必修]** PROPOSAL JSON schema 驗證過鬆。R3 在 `_parse_proposal` 加：top-level 必 dict、`combinator ∈ {And, Or, Exists}`（新增 `_VALID_COMBINATORS` frozenset）、`subgoals` 必 list、每 sub-goal 必 dict 且 `slug` / `statement` 都是非空 str。schema 不對 → 回 None → caller retry agent。+6 tests：`test_invalid_combinator_returns_none` / `test_subgoals_not_list_returns_none` / `test_subgoal_missing_slug_returns_none` / `test_subgoal_missing_statement_returns_none` / `test_subgoal_empty_slug_returns_none` / `test_top_level_not_dict_returns_none`

- **#4 [MEDIUM 建議]** `_dedupe` 不對 proposal 內部 dedupe。R3 加 `seen_hashes: set[str]` 過濾同 proposal 內 statement_hash 重複。+1 test `test_intra_proposal_dedupe`

- **#5 [MEDIUM 建議]** `_self_verify` 「multi mode」名實不符。R3 改名 `_self_verify_per_file` + 加 docstring caveat（隨 #2 一併處理）；module docstring 加 P2→P3 升級點（`Tooling.lake.run_lean_multi(staging_dir, ...)` API future）

- **#7 [LOW 建議]** retry 跨輪 staging cleanup。R3 在 `_run_loop` 進迴圈頂端加 `shutil.rmtree(staging_dir, ignore_errors=True); Path(staging_dir).mkdir(parents=True, exist_ok=True)`。+1 test `TestRetryStaging::test_retry_clears_stale_staging`（驗第一輪殘留檔不殘留）

- **#8 [LOW 建議]** `_validate` `"id": sg.get("id", sg["slug"])` 改 `"id": sg["slug"]` + inline comment「pre-commit phase uses slug as identifier」

- **#12 [INFO 補]** parity with builder.py：加 `_insert_pipeline` / `_finish_pipeline`、`run()` 進入時 `_insert_pipeline(pipeline_id, goal_id, session_id)`（kind='Backward'、runtime='atomic'、target_kind='Goal'、status='running'、寫 session_id）、`run()` 結束時 `_finish_pipeline(pipeline_id, outcome)`（success → succeeded、其餘 → failed）；`strategy.created_by=pipeline_id` 補上（FK 不違反、因 pipelines row 已先寫）。+2 tests `TestPipelineRow`：success → status='succeeded'、exhausted → status='failed'

- **#6 [LOW]** dead code：因 #12 加了 `_insert_pipeline` 重新消費 `_now()`、`from datetime import datetime, timezone` 不再 dead，**自動解決**

---

**Test 修正**：無 regression、既有 297 全綠（C13 R1）→ 321 全綠（R3 +24 new）

**Noted（不修）**：#9 lean_timeout=600.0 保守 / #10 strategy file P2 為 stub C14 補 / #11 parent_subgoal_max_similarity P3 接手 / #13 BACKWARD_FORCE 標 P3 / #14 跨 phase 規則對齊

**驗證**：
- `pytest Tooling/tests/test_commit.py` → **26 passed**（19 → +7 junction/cascade tests）
- `pytest Tooling/tests/test_backward.py` → **46 passed**（29 → +17 audit-driven tests）
- `pytest Tooling/tests/` → **321 passed**, 2.56s（C13 R1 297 → R3 321、0 regression）
- `git diff --stat HEAD` → 4 files changed: `Tooling/commit.py` / `Tooling/pipelines/backward.py` / `Tooling/tests/test_commit.py` / `Tooling/tests/test_backward.py`

**已知 caveat**：
- recover_scan 對 partial step2/3 fault path 是 row-level recovery（each row finalize-or-delete 獨立），不保證 strategy + subgoals "全 finalize 或全 delete" 的完美對稱原子性；目前語意是「無 FK violation + 無 orphan junction」、與 spec 字面 atomicity 一致但非 transactional all-or-nothing
- self_verify P2 仍 per-file（沒 `lake build` dir 模式），P3 升級點已記在 backward.py module docstring

---

**C13 R1 — Backward pipeline runtime（backward.py + prompt template + tests）**

本輪完成 P2 C13 全部交付物：

**新增檔案（3 files）**：

1. `docs/prompts/backward.md`：Backward agent prompt template v1。
   - 含 `{{GOAL_PROBLEM}}` / `{{GOAL_SLUG}}` / `{{GOAL_STATEMENT}}` / `{{DEAD_ATTEMPTS}}` 四個替換槽位
   - 要求 agent 輸出一個 ```json code block（含 combinator + subgoals + leaf_claims）
   - 明確列出 hypothesis carry 規則與 slug 命名規範

2. `Tooling/pipelines/backward.py`：Backward class + 完整 8-stage 序列
   - **failure_replay** / **find_lemmas** / **find_subgoals**：P2 stub，回 empty
   - **agent**：透過 FallbackChain + ModelResolver（backward.agent → sonnet tier），從 `docs/prompts/backward.md` 載入 prompt template
   - **_parse_proposal**：從 agent output 擷取 ```json code block（無 combinator key → None）
   - **_dedupe (local)**：statement 正規化後 SHA256，對 `goals.statement_hash` 做 SQL WHERE 比對，已存在則過濾
   - **_write_staging_files**：每個 sub-goal 寫 sorry stub `.lean` 至 Staging/<session_id>/
   - **validator**：傳 staging_path 作 lean_path（檔案存在）→ 呼 `validate()` facade
   - **self_verify (multi mode)**：對每個 staging file 個別呼 `run_lean()`
   - **_commit**：`CommitWriter.begin_batch` 一次 TX INSERT strategy + N subgoal goals；strategy_subgoals junction 獨立 TX；stage_file 移動所有檔案；finalize 全部 commit_state → 'live'
   - **run(goal_id)**：max_retries 迴圈，validator 拒絕 → retry agent，chain exhausted → 直接 return；outcome: success / exhausted / unproductive

3. `Tooling/tests/test_backward.py`：29 unit tests
   - TestStubStages（3）、TestParseProposal（5）、TestNormalizeHash（3）、TestDedupe（4）
   - TestAgentStage（5）、TestValidatorRetry（2）
   - TestCommitBatch（3）：含 DB 欄位驗證、磁碟檔案驗證、CommitFault 傳播
   - TestOutcomeDispatch（4）：depth 傳遞、fields 形狀

**設計決策**：
- `goals.origin='backward'`（符合 schema CHECK）、`goals.kind='theorem'`、`goals.status='open'`
- strategy lean_path 用 `backward_<pipeline_uuid>.lean`（唯一 stub 檔）
- validator 傳 staging_path 而非最終 lean_path（檔案存在時才能 elaborate）
- `created_by` 省略（nullable FK，P2 不需 pipeline 記錄）

**驗證**：
- `pytest Tooling/tests/test_backward.py` → **29 passed**, 0.42s
- `pytest Tooling/tests/` → **297 passed**, 2.40s（268 → 297，0 regression）

**已知 caveat**：
- 未加 `_insert_pipeline`：strategy.created_by 為 NULL（nullable，P2 可接受）
- `_parse_proposal` 只接受 ```json code block，不 fallback bare JSON（prompt 明確要求 code block）
- self_verify sorry stubs 一律回 exhausted（正常，非 gate 條件）
- find_lemmas / find_subgoals stub 回傳值不傳入 agent prompt（P3 擴充點）

**C12 R3 — Fix R2 audit findings（silent-PASS 模式重複 + test hook 登記 + spec §5.0 字面對齊）**

R2 抓 1 HIGH + 1 MEDIUM + 2 LOW + 6 noted。HIGH 為架構模式重複違反（C11 R2 #3+#4 同類 silent-failure pattern 的復刻）、必修。R3 全修：

**Audit 評估**：4 fixable 全合理、無不合理需暫停的點。**指令：無**、R3 直接修。

**Fixable（全修）**：

- **#1 [HIGH] `print_axioms` returncode check**：`subprocess.run(check=False)` + 不讀 stderr → lake error / unknown identifier / toolchain missing 全 silently 變 `stdout=""` → `_parse_print_axioms_output` 無 bracket match → 回 `[]`；下游 `check_accept_rule([], allowed)` vacuously True → cascade 把 lake 失敗 Goal 誤 promote 為 `proved with empty trust_set`、acceptance #6/#7 false positive。**這是 C11 R2 #3+#4 已字面命名 + R3 修過的相同模式**（commit 7584071）。R3 加 `if result.returncode != 0: raise RuntimeError(f"... exit {rc}: stderr={...!r}")`、stderr 截 500 chars。+3 unit tests：`test_nonzero_returncode_raises` / `test_nonzero_returncode_includes_stderr` / `test_zero_returncode_no_brackets_returns_empty`（明確分離 lake 失敗 vs 真 trivial proof 兩條 path）

- **#2 [MEDIUM] `PRINT_AXIOMS_MOCK` 登記 `docs/dev/test_hooks.md`**：`test_hooks.md` line 3 字面要求「每加新 hook → 更新本檔」；R1 命名合規但漏登。R3 在 `## Hook 清單` 表加 P2 row：`| P2 | PRINT_AXIOMS_MOCK | none / <axiom>,<axiom>... | trust.print_axioms 跳過真實 lake env lean -e、直接返指定 axiom name list；給 unit test + CI 不需 lean toolchain 用 |`、語意凍結後續 phase 不得改

- **#3 [LOW] `parse_meta` 末尾呼 `validate_meta`**：spec §5.0 字面「未宣告 axioms → META.md 解析失敗」是單階段 gate；R1 拆成 parse_meta 永不 fail / validate_meta 才 raise（functional 等價但偏離字面）。R3 在 parse_meta 末尾呼 validate_meta(meta)、validate_meta 仍 export 作 standalone API。+2 tests：`test_parse_meta_raises_on_missing_axioms` / `test_parse_meta_raises_on_empty_axioms_list`

- **#4 [LOW] inline-list 顯式 raise**：`axioms: [propext, Quot.sound]` （inline list） → `_parse_yaml_simple` 視為 string scalar → `axioms = frozenset()` → validate_meta raise "axioms must declare..."（**錯誤訊息誤導 user 認為 axioms 沒寫**）。R3 在 parse_meta 對 `axioms_raw` 是非 list 且非空的 case 顯式 raise MetaError：「axioms field must be a YAML block list (one '- name' per line); inline lists / scalars are not supported: got ...」。+1 test：`test_parse_meta_raises_on_inline_list`

**Test 修正**：`test_subprocess_argv` 既有 case 用 `MagicMock()` 沒設 `returncode=0`、新加的 returncode check 觸發誤 raise → 補設 `fake_result.returncode = 0` + `fake_result.stderr = ""`

**Noted（不修）**：#5 `-e` flag 路徑未實機驗（spec §5.2 字面要求）、#6 `_BRACKET_RE` 對 subprocess output 非 Lean 源碼（不違反 §7.4）、#7 empty trust_set vacuously true 與 #1 修法連動已自然解決、#8 Windows encoding 風險（Mathlib axiom 全 ASCII）、#9 cli `_META_TEMPLATE` 設計合理、#10 跨 phase 規則對齊

**驗證**：
- `pytest Tooling/tests/test_meta.py Tooling/tests/test_trust.py` → **44 passed**, 0.31s
- `pytest Tooling/tests/` → **268 passed**, 2.27s（C12 R1 後 262 + 6 新 = 0 regression）
- `git diff --stat HEAD~1 HEAD` → 5 files / +96 / -6
- `grep "PRINT_AXIOMS_MOCK" docs/dev/test_hooks.md` → 1 hit ✓
- commit：`d668e87 P2 C12 R3: fix R2 audit findings`

**Caveat**：
- C12 R1 caveat 仍適用：`print_axioms` 真實 subprocess 路徑（無 PRINT_AXIOMS_MOCK）未實機驗、`-e` 路徑輸出格式依 spike-002 推導；C18 demo 會驗
- R3 不動 module 公開 API（`parse_meta` / `validate_meta` 仍同樣 callable、後者仍 export）—— C13 Backward pipeline 接 trust 時 import 字面不變
- inline list 顯式 raise 是「user 手寫 META.md」防誤導、cli `_META_TEMPLATE` 自動生成走 block-list 樣式不踩

---

**C12 R1 — META.md parser + Trust set 構造**

### 交付物

1. **Tooling/meta.py**
   - `parse_meta(problem_dir) → MetaConfig`：讀 META.md YAML frontmatter、提取 `axioms` (frozenset) + `problem_name` + `models` (dict)
   - `validate_meta(meta)`：axioms 欄位為空 → raise MetaError（無框架預設繼承）
   - 純 stdlib 實作（無 pyyaml 依賴）：`_extract_frontmatter` + `_parse_yaml_simple` 支援 top-level scalar / block list / flat nested map
   - `MetaError` exception class

2. **Tooling/trust.py**
   - `print_axioms(theorem_name, cwd) → list[str]`：呼 `lake env lean -e '#print axioms <thm>'`、parse `[axiom1, axiom2, ...]` bracket pattern、PRINT_AXIOMS_MOCK hook
   - `build_trust_set(axioms) → list[dict]`：包成 `{name, kind='lean_axiom', provenance='lean #print axioms'}` entry（confidence 省略、隱含 1.0）
   - `check_accept_rule(trust_set, allowed_axioms) → tuple[bool, list[str]]`：impl §5.3，kind='lean_axiom' AND name ∈ allowed_axioms、回傳 (accepted, rejected_names)

3. **Tooling/tests/test_meta.py**（15 tests）：valid cases（axioms-only / full / single / no-models / problem_name / models-partial / content-after-marker）+ error paths（missing file / no frontmatter / unclosed / empty）+ validate_meta（pass / empty raises）

4. **Tooling/tests/test_trust.py**（23 tests）：PRINT_AXIOMS_MOCK hook（5）+ subprocess argv + timeout + parse output（5）+ build_trust_set（4）+ check_accept_rule（7）

5. **Tooling/cli.py** `_META_TEMPLATE` 改成 YAML frontmatter 格式（`{problem_name}` 在 cmd_init 用 `.format()` 注入）

### 驗證

- `pytest Tooling/tests/test_meta.py Tooling/tests/test_trust.py` → **38 passed**, 0.35s
- `pytest Tooling/tests/` → **262 passed**, 2.31s（0 regression；原 224 + 38 新）
- commit: `e93551a P2 C12 R1: META.md parser + Trust set construction`

### 已知 caveat

- `print_axioms` subprocess 路徑（無 PRINT_AXIOMS_MOCK）未實機驗；`lake env lean -e '#print axioms ...'` 確切輸出格式依 spike-002 `[propext, ...]` bracket 樣式、如 Lean 版本升後格式變更需更新 `_BRACKET_RE`
- `_parse_yaml_simple` 不支援 inline list `axioms: [a, b]` 格式（只支援 block list `- item` 樣式）、不支援 quoted strings——對 spec 格式足夠、edge case 留 P3
- Accept rule 整合進 reactor cascade 留 C15（本 cycle 只實作 module + tests）

**C11 R3 — Fix R2 audit findings（architectural rule violation rework）**

R2 抓 2 HIGH + 2 MEDIUM + 1 LOW + 6 noted。HIGH 為架構硬規則違反、必修。R3 採 major rework（整體 +362 / -363、淨持平）而非 incremental patch；3 files 全重寫：

**Audit 評估**：5 fixable 全合理、無不合理需暫停的點。**指令：無**、R3 直接修。

**Fixable（全修）**：

- **#1 [HIGH] 移除 regex parse Lean 源碼**：architecture.md §7.4 + impl §4.1 字面禁「regex parse Lean 源碼、PR review 直接 reject」；C11 R1 的 `extract_theorem_type` / `_find_at_depth0` / `_find_define` 三函式 + `import re` 全違反。R3 把整套 type-shape 抽取邏輯搬回 `tools/validator.lean`、Python 端純 stdlib subprocess wrapper（無 `re`）。Audit #5（extract_theorem_type 6 test 漏 fragile case）此修同時自動 resolve

- **#2 [HIGH] CLI args 取代 env vars**：對齊 impl §4.2 字面 spec `validator hypothesis_carry --parent <file> --subgoals <files...>` + dedupe.lean pattern。R3 把 validator.lean 從 `elab_rules : command` + env var 改成 `def main : List String → IO UInt32`、Python 端 argv 變 `lake env lean --run tools/validator.lean -- hypothesis_carry --parent <p> --subgoals <s1> <s2>...`

- **#3 [MEDIUM] validator.lean explicit error 路徑**：原設計 parse/elab fail → silent `return #[]` → 全 sub-Goal 報 PASS（false negative for acceptance #5）。R3 改 `ValidatorOutput` JSON 加 `parent_error : Option String` + 每個 SubgoalResult 加 `error : Option String`、Lean 程式 parent fail 時 exit code 2、subgoal fail 時對應 entry 帶 error 字段

- **#4 [MEDIUM] Python check_hyp_carry 三條 fail path**：原設計 `_parse_lean_output` 找不到 JSON line silent 回 `[]`、不檢 returncode/stderr → 同 #3 silent-PASS 路徑的 Python 端體現。R3 加：(a) `_parse_validator_json` 找不到 → ValidatorError、(b) `parent_error` 非 null → ValidatorError、(c) returncode != 0（且無 parent_error）→ ValidatorError，三 path 都帶 stderr/rc context

- **#6 [LOW] 移除 ppExpr type string 收集**：P2 `type_mismatches` 永遠空、P3 isDefEq 走 `Expr` 不走 `String` → 收 type 字串無論 P2/P3 都 dead work。R3 把 `extractBinders` 改成純 `collectForallBinders : Expr → Array Name`（pure Expr walk、無 MetaM、無 ppExpr），同時 drop `TypeMismatch` struct（P2 永遠空、forward-compat 不需要）

**Noted（不修）**：#5 self-resolved；#7 name-based check 對 rename 非 robust 但對齊 spec、留 P3 isDefEq + prompt template；#8 SQL SELECT 而非 UNIQUE constraint 因 P2 不可動 schema；#9 facade 順序合理；#10 全 mock subprocess 對齊 P1 convention；#11 跨 phase 規則對齊

**新設計亮點**：

- **Lean.Elab.runFrontend 路徑**：`tools/validator.lean` 用 `runFrontend content {} path \`_AsterismValidator` elaborate 整個 .lean 檔（含其 `import Problems.<problem>.Defs` chain）、回 `(Environment × Bool)`；ok=false 即報 elab 失敗
- **User decl detection**：`env.getModuleIdxFor? name` 對 imported decl 回 `some idx`、對當前檔 decl 回 `none` → `findUserTheorem` 找第一個 `.thmInfo` 且 `isUserDecl` 為 true 的 declaration
- **Pure Expr walk for binder names**：`collectForallBinders : Expr → Array Name` 直接 pattern match `.forallE binderName _ body _` 遞迴、不需 MetaM/forallTelescope（後者引入 fresh fvars 是為了型別計算、但我們只要 binder names）→ 無 monad lifting 樣板、~10 行

**Test changes**：

- **Drop**（6）：`TestExtractTheoremType` 整 cluster 隨函式刪除自然消失
- **Add**（6）：`test_parent_error_short_circuits` / `test_subgoal_elab_error_reported` / `test_returncode_nonzero_no_parent_error` / `test_no_json_in_stdout` / `test_invalid_json_falls_through_to_no_json` / `TestSubprocessInvocation::test_cli_args_match_spec`（驗 argv 字面對齊 impl §4.2）
- **Keep**（17）：max_subgoals 4 + slug_unique 4 + hyp_carry pass/missing/multi/empty/noise/timeout 6 + facade 3 = 17 → 17 + 6 new = 23 total（同數）

**驗證**：
- `pytest Tooling/tests/test_validator.py` → **23 passed**, 0.28s
- `pytest Tooling/tests/` → **224 passed**, 2.15s（0 regression）
- `grep "import re|extract_theorem_type|_find_at_depth0|_find_define" Tooling/stages/validator.py Tooling/tests/test_validator.py` → 1 hit（test_validator.py docstring 的歷史紀錄、不是 code reference）
- `grep "ppExpr" tools/validator.lean` → 1 hit（comment 標 audit #6 修法）
- `git diff --stat HEAD~1 HEAD` → 3 files / +362 / -363（淨持平）
- commit：`7584071 P2 C11 R3: fix R2 audit findings (architectural rule violation)`

**Caveat**：
- `Lean.Elab.runFrontend` 對含 `import Mathlib.X.Y` 的 sub-Goal 檔會載入 Mathlib oleans（warm cache 估 ~5s/次、cold ~20s）；同 lean 程序內後續 runFrontend 共用 mmap'd olean cache、增量成本 ~0.5s/檔。8-subgoal demo 估 ~9s 量級。實際 perf 待 P2 acceptance #5 / C18 demo 驗（spike-006 已有並發數據可參）
- C11 R3 沒實機跑 `tools/validator.lean`（unit test 全 mock subprocess）→ Lean 端 syntax / API 正確性留 C13 Backward pipeline 接通 + acceptance #5 驗證；若 R3 lean 程式有 compile bug、C13 整合時 fail-fast 暴露
- `findUserTheorem` 假設 file 內第一個 `.thmInfo` 即是 target；多 theorem in single file 會選最前面那個——對齊 Backward pipeline 慣例（每 sub-Goal 檔一個 theorem）、無歧義
- CLI argv 用 `lake env lean --run <validator.lean> -- args`：`--` separator 確保 args 傳 main 而非被 lean parser 吃掉；test 字面驗 argv 結構

---

**C11 R1 — Validator（hypothesis carry + SQL UNIQUE + max_subgoals）**

4 new files / 704 insertions：

**tools/validator.lean**：
- Lean 4 elab command（`#run_validator`）使用 `Lean.Meta.forallTelescope` + `getLCtx` + `ppExpr` 抽 binder list（同 spike-005 API 組合）
- 讀 env var `VALIDATOR_PARENT_TYPE`（parent 型別字串）+ `VALIDATOR_SUBGOALS`（JSON array）
- 對每個 sub-Goal 跑 `extractBinders`：`Parser.runParserCategory env `term typeStr` → `Term.elabTerm` → `forallTelescope` → (name, type_string) pairs
- `checkCarry`：比較 parent binders vs sub binders by name，輸出 `missing_binders`；`type_mismatches` 留 P3（`Meta.isDefEq`）
- 輸出 JSON array 到 stdout（`IO.println (toString (toJson results))`）
- Lean core only（`import Lean`, `import Lean.Meta`, `import Lean.Elab.Command`）、無 Mathlib、~2.5s（spike-005 確認）

**Tooling/stages/__init__.py**：空 package marker

**Tooling/stages/validator.py**：
- `extract_theorem_type(lean_content)` 文字 parser：strip 行內 comment、定位 `theorem <name>`、找 depth-0 `:=` 截尾、找 depth-0 `:` 分 params/return type、重組為 `∀ <params>, <return_type>`
- `check_max_subgoals(subgoals)` → `ValidatorError` | None（len > 8 reject）
- `check_slug_unique(conn, problem, subgoals)` → SQL `SELECT id FROM goals WHERE problem=? AND slug=?` 找碰撞
- `check_hyp_carry(parent_lean_path, subgoals, lake_cwd)` → subprocess `lake env lean tools/validator.lean`（cwd=lake_cwd）帶 env vars；`_parse_lean_output` 找 stdout 中第一個以 `[` 開頭的行解析 JSON；timeout=30s
- `validate(conn, problem, parent_lean_path, subgoals, lake_cwd)` → max_subgoals 是 hard gate（fail 即 return）、slug + hyp_carry 並列收集

**Tooling/tests/test_validator.py**：
- 23 unit tests（全 mock subprocess + Path.read_text，無真實 Lean / 真實 fs）
- `TestExtractTheoremType`（6）：explicit params、no params、import prefix、inline comment、no theorem → ValueError、single binder
- `TestMaxSubgoals`（4）：exactly max OK、one over reject、zero OK、one OK
- `TestSlugUnique`（4）：no collision、collision detected、different problem OK、first collision stops
- `TestHypCarry`（6）：pass / missing binder / multi partial fail / empty list / Lean diagnostic noise before JSON / timeout
- `TestValidateFacade`（3）：max_subgoals hard stop、slug collision 上報、all clear

**驗證**：
- `pytest Tooling/tests/test_validator.py` → **23 passed**，0.26s
- `pytest Tooling/tests/` → **224 passed**（原 201 + 23），2.21s，0 regression

**Caveat**：
- `tools/validator.lean` 在 D:/Asterism 沒有 lakefile.lean 的情況下，需從有 lake 環境的 cwd 呼叫（目前設計為由 caller 提供 `lake_cwd`，P2 demo 用 D:/Hadamard）
- `type_mismatches` 在 P2 永遠回 `[]`；P3 spike-009 後接 `Meta.isDefEq` 實作
- `extract_theorem_type` 是 text-level parser，不是完整 Lean parser；對非標準 theorem 排版（多行 signature、`where` 子句、by-name implicit args）可能有 edge case；P2 Demo 範圍內的簡單 theorem 格式已驗

---

**C10 R3 — Fix R2 audit findings (kill dead code + safety guards)**

R2 找到 5 fixable LOW + 5 noted。5 fixable 全合理、全處理（2 files / +39 / -34）：

**Fixable（全修）**：

- **#1 [LOW] `_kill_tree` 孤島模組刪除**：claude.py 用 `subprocess.run(timeout=)` 而非 `Popen`、超時時 subprocess.run 已自動殺子程序，`_kill_tree` 在 C10 範圍內無 caller、違反 user CLAUDE.md「不寫孤島模組」。R3 整段刪除（claude.py:217-242, -19 lines）。理由：C15 daemon mode / C16 cancellation 真用到 Popen-based kill 時自然 add back，不前置；41 test 不蓋 dead branch 也對齊「無入口即不該存在」。

- **#2 [LOW] `_PORCELAIN_CHANGED` regex + dead imports 刪除**：claude.py:53 定義 regex 但 `check_scope` 用 `line[3:]` slicing parse 從未呼用、是 dead code。R3 (a) 刪 `_PORCELAIN_CHANGED` 定義；(b) 連同 `import re`/`import json`/`import os`/`import sys` 全成 unused 後一併刪（4 imports 全為 `_kill_tree` 與 `_PORCELAIN_CHANGED` 服務）。`subprocess` + `pathlib.Path` 為唯一保留 stdlib。

- **#3 [LOW] `check_scope` session_id docstring**：`check_scope(staging_dir, session_id=None)` 為配合 `FallbackChain._validate_scope(staging_dir, session_id)` callable signature 而收 session_id、ClaudeProvider 範圍內無 per-session git tracking 邏輯。R3 docstring 加 3 行註明「session_id 為 FallbackChain validate_scope callable 介面要求、本 provider 無 per-session git tracking 故 unused、P5 多 provider 共用此 hook 時可能用」，避免未來 reader 誤刪。

- **#4 [LOW] `gc_session` empty session_id guard + trailing `*` docstring**：原 pattern `f"{session_id}*.jsonl"` 對 empty session_id catastrophic（會展成 `*.jsonl` 刪光 `~/.claude/projects/**/` 下所有 jsonl）。R3 (a) 加 `if not session_id: raise ValueError("session_id must be non-empty")` guard 在 method 第一行；(b) docstring 加 4 行說明 trailing `*` 是 by-design（catch claude CLI fork / branched session 變體 jsonl，例 `<session_id>-fork.jsonl`）+ ValueError 條件。+1 unit test `test_gc_empty_session_id_raises` 守此 guard。

- **#5 [LOW] AgentResponse.extra cmd 含 prompt full text → redact**：原 `extra={"model_id": ..., "cmd": cmd}` 把 argv 全文（含 `-p <full prompt>`）落 response，後續 caller（P2.C13 commit batch / events row）若直接 dump JSON 進 DB 會把 prompt 全文重複序列化、disk footprint 膨脹。R3 改 `argv_redacted = ["<PROMPT>" if c is prompt else c for c in cmd]` + extra key 從 `cmd` 改 `argv` 明標已 redact。理由：full prompt 可從 session jsonl 還原（gc_session 也是這個假設），AgentResponse 不該重複承載。+1 unit test `test_extra_redacts_prompt` 驗 prompt 不在 argv、`<PROMPT>` 標記在、其他 args 未被誤刪。

**Noted（#6-#10 不修，全合理）**：

- **#6** Provider.invoke 多 keyword-only `cwd: str | None = None` kwarg：合理 forward-compat 擴展、不破壞 LSP（gemini/codex P5 加入時可 ignore）；對齊 spike-004 #2 caveat（cwd 設 staging dir 而非 D:/Asterism 消除 inference 依賴）；41 test 雙路覆蓋 `cwd default / cwd override`。
- **#7** test_provider.py 不走 `test_phase{N}_*` 命名：對齊 P1 既有 unit test convention（`test_lake.py` / `test_commit.py` 等均無 phase prefix），phase acceptance test 命名 `test_phase2_*.py` 留 C18，與 P1.C8 寫 `test_phase1_acceptance.py` 時點對齊。
- **#8** evil agent mock + scope isolation + retry 路徑留 C11 acceptance：對齊 spike-004 §對設計的影響 #4 deferral，C10 範圍是 plumbing、acceptance #1 走 C11+ end-to-end 場景。
- **#9** FallbackChain.run cwd kwarg 透傳對 Provider.invoke：介面內部一致、forward-compat hook，P5 gemini/codex 可選用或 ignore。
- **#10** CI 迴歸 gate / schema / fault hook / CLI forward-compat / commit message 跨 phase 規則全對齊。

**驗證**：
- `pytest Tooling/tests/` → **201 passed**，2.15s（199 + 2 new tests，0 regression）
- `git diff --stat HEAD~1 HEAD` → 2 files / +39 / -34：`Tooling/agent/providers/claude.py` +20/-34（`_kill_tree` -19 / `_PORCELAIN_CHANGED` -3 / 4 imports -4 / docstring +7 / empty guard +2 / argv redact +5 / 其他細節）；`Tooling/tests/test_provider.py` +21（2 new tests）
- `grep "_kill_tree\|_PORCELAIN_CHANGED" Tooling/agent/providers/claude.py` → 0 hit（dead code 全清）
- `grep "^import" Tooling/agent/providers/claude.py` → 2 行（`subprocess` + `pathlib.Path`）；無 dead import

**Caveat**：
- `_kill_tree` 在 C15/C16 真要 Popen-based process tree kill 時需 add back（task.md ## Cycle plan 線 144 C15 Reactor daemon、線 146 C16 cancellation 預期會引）
- AgentResponse.extra.argv 仍含 `--session-id <id>`、`--add-dir <path>` 等 metadata；caller 序列化前若需 sanitize 應自行篩。redaction 只覆蓋 prompt 字串本身

---

**C10 R1 — Provider abstraction + claude implementation**

5 new files / 893 insertions：

**Tooling/agent/provider.py**：
- `AgentResponse` dataclass（output / session_id / exit_code / extra）
- `Provider` ABC：`invoke(model_tier, prompt, scope_dirs, session_id) → AgentResponse`、`gc_session(session_id)`、`resolve_model_id(tier)`
- `FRAMEWORK_MODEL_DEFAULTS`：`builder.tactic_llm=haiku`、`backward.agent=sonnet`
- `ModelResolver`：兩層覆寫（META.md 優先 → 框架預設；Strategist 第三層留 P7）
- `FallbackChain`：P2 single-entry；`validate_scope` hook 讓 scope 違規重試；P5 延伸為多 provider

**Tooling/agent/providers/claude.py**：
- `ClaudeProvider`：`invoke()` 走 `claude -p --model <id> --add-dir <dir>... --permission-mode acceptEdits --session-id <id> < /dev/null 2>&1`
- CWD = 第一個 scope_dirs（staging dir），對齊 spike-004 caveat（不用 D:/Asterism 避免 CWD scope 洩漏）
- `CLAUDE_MODEL_MAP`：haiku/sonnet/opus → 具體 model id
- `check_scope(staging_dir)` git status backstop：parse git porcelain output，驗「除 staging_dir 外無檔案被改」；git 不可用 → fail safe (False)
- `gc_session(session_id)`：掃 ~/.claude/projects/**/<session_id>*.jsonl 刪除
- timeout → `ProviderError`（subprocess.run 已殺子程序，不需額外 kill）
- `_kill_tree` helper：psutil 優先、fallback taskkill/killpg

**Tooling/tests/test_provider.py**：
- 41 unit tests，全 subprocess mocked，無真呼 claude CLI
- 8 類：AgentResponse / resolve_model_id / ModelResolver / FallbackChain / _build_cmd / invoke / check_scope / gc_session

**CI**：`pytest Tooling/tests/test_phase1_acceptance.py Tooling/tests/test_provider.py` → **55 passed**（P1 14 + C10 41，0 regression）

**Caveat**：
- `_kill_tree` 的 `taskkill` / `killpg` path 在 test 中不覆蓋（psutil missing → fallback；psutil mock 非本次 scope）；spike-004 `test B` 只有單次觀察，evil agent mock 驗 scope isolation + retry 路徑留 C11 acceptance test #1

---

**C9 R3 — Fix R2 audit findings (caveats + extrapolation + docstrings)**

R2 找到 5 fixable + 5 noted。5 fixable 全合理、全處理（4 files / +65 / -26）：

**Fixable（全修）**：

- **#1 [MEDIUM] spike-006 測 `lake env lean` 不是 phase doc 字面 `lake build`、4-conc atomic pool 對 Backward self_verify (multi) 工作負載證據不足**：phase2_decomposition.md §依賴 線 139 字面是「同時跑 4 個 lake build」，spike-006 測的是 `lake env lean <file>`（單檔 elab、read-only Mathlib .olean）。R3 在 spike-006 §問題 後加 **Caveat 段** 明標測試範圍 vs 字面要求差異 + 推遲 P2.C15 Reactor 升級時連帶補測；§對設計的影響 #1 從「P=4 atomic pool 安全可行」**降級**為「P=4 atomic pool 對單檔 elab 並發安全；`lake build` staging 並發未驗、留 C15」+ 細分覆蓋場景 (a) Builder.tactic_try / (b) validator.lean / (c) Backward self_verify (multi)（最後一條未蓋）。`docs/spikes.md` spike-006 §問題 +12 / §對設計的影響 #1 +6/-2。

- **#2 [MEDIUM] spike-004 Test 0/1 為 model judgment 證據、Test B 為唯一 tool layer 直接證據；CWD 寫入 claim 為 by-design inference**：R3 在 spike-004 §結果 開頭加 **證據強度標註 段**（Test 0/1 = model judgment 層；Test B = tool layer 唯一直接證據；外層 fs 觀察 `outside_evil.exists() == False` 是 model-independent 真實證據）；各 Test 標題加層級註記（Test 0「model judgment 層證據」/ Test B「唯一 tool layer 直接隔離證據」+ 外層 fs 驗證 row）；CWD 默認 acceptEdits 範圍 claim 加 caveat（依據 Test B agent 自陳 stdout + claude CLI `--add-dir` 文件語意，**未直接 fs 驗** D:/Asterism 內寫入會被允許）；§對設計的影響 #2 強化 P2.C10 cwd 設計建議（**用 staging dir 而非 D:/Asterism**，消除 inference 依賴）；§對設計的影響 #4 加 caveat（P2 acceptance #1 evil agent 需用 mock Provider 跳過 model alignment、走 tool layer retry path）。`docs/spikes.md` spike-004 §結果 +18/-9 / §對設計的影響 #2 重寫 / #4 加 caveat。

- **#3 [LOW] spike-006 cold-cache 4-conc extrapolation 「~112s（formula 299s）」數字不一致**：原文 `cold cache 約 112s（估算：spike-001 cold 3x = 224s × 4/3 ≈ 299s / 2 cores）` formula 算出 299/2=149.5s（≠112s），112 數字無 formula 推得。R3 改寫為 **`~300s 上界估（spike-001 cold 3-conc=224s × 4/3 線性外推；實際受 IO+memory bound 影響，上限不易精準）`**——對齊 audit 建議 (a) 路。設計結論「P2 T_wall=30 min 內安全」對 cold-cache 4-conc 上界仍 robust（300s = 5 min < 30 min）。`docs/spikes.md` spike-006 §對設計的影響 #4 +1/-1。

- **#4 [LOW] spike-007 Variant 2/3 為純 manual estimate、未經 actual API call**：原文未明標 Variant 1 有 actual API cross-check 而 Variant 2/3 只跑 `len(text) // 4` heuristic。R3 (a) 結果列表加 `[actual API cross-check: ✓]` / `[pure manual estimate]` 標記；(b) 加獨立 **Caveat (manual estimate 嚴格性)** 段，明標 4 chars/token heuristic 對 Lean code-heavy 內容可能偏低 1.5-2x（識別字 / 符號密度高於英文）；(c) §對設計的影響 #2/#3 加「2x 上界估」雙路引用——K=50 manual ~3.5K / 2x 上界 ~7K 仍 < 4% context，conclusion robust 不變。`docs/spikes.md` spike-007 §結果 +6/-1 / §對設計的影響 #2/#3 +2/-2。

- **#5 [LOW] spike-004 三 runner（runner / runner2 / runner3）共存無 docstring 區分**：R3 三 runner 第一段 docstring 加狀態標記：(a) `runner.py` → **HISTORICAL — Test 0 only, model judgment evidence**（純 -p mode、發現 staging 寫入也被擋的起點）；(b) `runner2.py` → **HISTORICAL — Test 1 + path traversal**（仍 -p mode，發現 acceptEdits 必要性的 driver）；(c) `runner3.py` → **FINAL — Test A + Test B, tool-layer evidence**（acceptEdits + `--add-dir` 最終設計、P2.C10 Provider.invoke 應採用的參數組合）。三 docstring 互相 cross-reference 並指向 docs/spikes.md 對應 Test 段。`spike004_runner{,2,3}.py` 各 +12/+11/+19 line docstring。

**Noted（#6-#10 不修，全合理）**：

- **#6 spike-005 binder count gate 不蓋 alpha-equivalence**：phase doc 已將 `Meta.isDefEq` 排到 P3 spike-009、acceptable carry-forward
- **#7 spike-007 cache_read_tokens=96K 為 prior session 殘留**：文中已明確 caveat、conclusion 取 cleanest signal（haiku 1309 直觀數）
- **#8 CWD 設計留意（用 staging / problem dir 而非 D:/Asterism）**：spike actionable insight、不是 spike 缺陷（C10 executor 直接吃；本 R3 #2 修中也已強化此點到 §對設計的影響 #2）
- **#9 spike-005 ~2.5s vs Mathlib 20s+ 開銷比**：P2.C11 validator 設計 lean-fast-path 可行性、actionable insight
- **#10 `spike001_mathlib_d.lean` 沿用 spike001_* 命名 family**：cosmetic、acceptable trade-off

**驗證**：
- `pytest Tooling/tests/ --tb=short -q` → **158 passed**，2.09s（無 regression，與 C9 R1 同）
- `git diff --stat` → 4 files / +65 / -26：`docs/spikes.md` +49/-15 / `spike004_runner.py` +12/-1 / `spike004_runner2.py` +11/-1 / `spike004_runner3.py` +19/-9
- `grep "Caveat" docs/spikes.md` → 4 hit（spike-006 §問題 / spike-006 §對設計 #4 / spike-004 §證據強度標註 / spike-007 §Caveat (manual estimate 嚴格性)）

**邊界**：未動 architecture / phase doc / spike fixture 內容（只動 docstring）/ Tooling 主程式 / AutoDev / .github。未引入新依賴。

**Caveat（R3 留下的條件）**：
- spike-006 `lake build` 4-conc 真實壓測 deferred 到 P2.C15（Reactor 升級時做、phase doc §風險 R6「Subprocess pool on Windows」對齊場域）；R3 沒補做 optional 30-60 min 真實壓測，理由：(a) 工期換取的數據點對 P2.C10 / C11 / C13 開工不阻擋；(b) C15 cycle context 自然涵蓋 atomic pool wiring 本身、補測 scope 對齊更佳；(c) 本 R3 caveat 已明標 deferral，未來 reader / executor 不會誤讀為已驗
- spike-004 CWD 寫入 claim 為 by-design inference 仍未補正面 fs 驗證；R3 採 audit 建議（標 caveat）+ 主動將 P2.C10 Provider.invoke cwd 設計推到「用 staging 而非 D:/Asterism」消除 inference 依賴。實際正面 fs 驗在 P2.C10 Provider 抽象實作 + acceptance test 跑時自然涵蓋
- spike-007 Variant 2/3 仍未補真實 API call；R3 採 audit 建議 (caveat note)，理由 budget gap 大（200K vs 7K 上界估）conclusion robust；P2.C10 開工後若 prompt 設計接近 Variant 2 規模可隨時補測

---

**C9 R1 — spike-004 / 005 / 006 / 007 + results in docs/spikes.md**

spike 全部跑通，結果寫入 `docs/spikes.md`（spike-004 ~ spike-007 各 ## 結果段），CI gate 158 passed。

**spike-004 claude CLI `--add-dir` 行為**：
- 需組合 `--add-dir <staging> --permission-mode acceptEdits` 才能讓 agent 寫入 staging
- 純 `-p` 模式（無 acceptEdits）：staging 外 + staging 內寫入均被阻
- 加 acceptEdits + `--add-dir staging`：staging 內寫入 ✅、staging 外寫入 ✅ 被阻
- 雙層保護：(1) model judgment 拒絕 explicit evil prompt；(2) `--add-dir` tool 層擋非允許路徑
- **Caveat**：CWD（D:\Asterism）默認在 acceptEdits 範圍 → git status 兜底必要
- **設計影響**：P2 Provider.invoke 參數組合 = `claude -p --add-dir <staging> --add-dir <problem_dir> --permission-mode acceptEdits`；git status 兜底維持；fallback（git stash 路線）不需觸發

**spike-005 Lean.Elab 抽 binder list**：
- `Meta.forallTelescope + getLCtx + ppExpr` 三步驟可完整抽 binder list（name + type）
- `#count_binders` 正確計數：parent=3, subgoal_ok=3, subgoal_bad=2
- `#check_hyp_carry ... from ...`：PASS(3≥3) / FAIL(2<3) 正確
- **設計影響**：validator.lean 採 `elab_rules : command` 模式；Lean core only（無 Mathlib import，~2.5s）；hypothesis carry gate = binder count ≥ parent count

**spike-006 lake env lean 4-concurrent**：
- 4 concurrent，無 Mathlib：wall=2.75s，sequential=9.76s，speedup=3.55x（近線性）
- 4 concurrent，Mathlib warm cache：wall=29.02s，all rc=0，no stderr error
- vs spike-001（3 concurrent Mathlib warm）：21.86s → 4 workers 29.02s（+33%）
- **設計影響**：P=4 atomic pool 安全確認；warm-cache 4-concurrent 在 T_wall=30min 內可接受

**spike-007 claude CLI prompt token 上限**：
- Backward prompt template（K=5 dead_attempts）：~700 tokens user message（manual + haiku 1309 total 驗證）
- 佔 sonnet 200K context 0.65%；即使 K=50 仍 <2%
- **設計影響**：P2 不受 context limit 壓力；K_digest=5 是品質控制而非 token 節省

**新增 fixtures**：
- `spike004_evil_prompt.txt` / `spike004_legitimate_prompt.txt` / `spike004_traversal_prompt.txt`
- `spike004_runner.py` / `spike004_runner2.py` / `spike004_runner3.py`
- `spike005_binder_extract.lean`
- `spike006_concurrent4.py`
- `spike001_mathlib_d.lean`（spike-006 第 4 worker 用）
- `spike007_backward_prompt_template.md` / `spike007_token_runner.py`

**驗證**：
- `pytest Tooling/tests/` → **158 passed**，2.20s（無 regression）

**邊界**：未動 Tooling/ 主程式（lake.py / commit.py / scheduler.py / builder.py / cli.py / db/）、architecture / phase doc；未引入新依賴；只新增 spike fixtures + docs/spikes.md 更新

**Caveat**：
- spike-004 `--add-dir` 隔離已確認，但 CWD 在 acceptEdits 範圍：P2 Provider.invoke 實作需確認 agent subprocess 的 CWD 設定（建議用 staging dir 或 problem dir 作 CWD，避免 D:\Asterism 整體可寫）
- spike-005 只驗了 binder count gate；嚴格 type-level 比對（`Meta.isDefEq`）留 P3 spike-009
- spike-006 Part 2 只做 warm cache（不做 cold cache）：cold cache 4-concurrent 性能估算基於 spike-001 外推（~300s），實測留必要時補

---

**C8 R3 — Fix R2 audit findings (LAKE_MOCK rename + test_hooks.md + DRY + manual demo gate)**

R2 找到 6 fixable + 4 noted。6 fixable 全合理、全處理（commit `af668be`，4 files / +38 / -30）：

**Fixable（全修）**：

- **#1 [MEDIUM] LAKE_MOCK 未登錄 `docs/dev/test_hooks.md`**（跨 phase 規則違反、必修）：test_hooks.md §規則第 1 行明示「每加新 hook → 更新本檔」、task.md ## 唯讀檔案 線 52 列為「加新 hook 才動」例外條款。R3 在 `## Hook 清單` 加 1 row：`| P1 | LAKE_MOCK | proved / sorry | run_lean 入口跳過真實 lake env lean、直接返 LakeResult；給 AC#0 subprocess test + CI 不需 lean toolchain 用 |`。`docs/dev/test_hooks.md:19`（+1）。
- **#2 [MEDIUM] `LAKE_MOCK_<OUTCOME>=1` boolean-flag 命名違反 `*_MOCK=spec` 慣例**（強烈建議、零成本現修）：test_hooks.md 線 5 命名慣例「`*_MOCK=spec` 替換真實行為」、現有 `SEARCH_MOCK=record_calls|force_miss|force_hit` 走 mutually-exclusive spec。C8 R1 加的 boolean-flag `LAKE_MOCK_PROVED=1` / `LAKE_MOCK_SORRY=1` 風格不一致、未來疊新 outcome（typeerror / timeout）會堆 boolean env、且兩 env 同設的優先順序為隱式約定。R3 改 `LAKE_MOCK=proved|sorry`：`lake.py:69-77` 從兩個 `os.environ.get("LAKE_MOCK_PROVED|SORRY") == "1"` 改成 `_mock = os.environ.get("LAKE_MOCK")` + `if _mock == "proved" / "sorry"`。test 同步：AC#0 env 改 `{"LAKE_MOCK": "proved"}`。test_hooks.md 「語意凍結」一旦進 P2 就不能改、現在改零成本。
- **#3 [MEDIUM record] AC#0 用 mock 跳過真實 lake、字面 single sanity gate 未端到端驗**（必修 record level）：phase1_skeleton.md ## Acceptance #0 字面要 real lake 跑通；CI mock 是必要妥協（cold-cache 200s+ 無法塞 CI 預算）但 mock pass != real pass。**P1→P2 transition 必須做 manual real-lake demo verification**（user 在 D:\Hadamard Mathlib env 跑一次 demo bash 並比對 stdout）。本 R3 R3 採 audit option (b)：留 user 驗、devlog 顯式記為 P1 done 條件之一。
  - **Manual verification gate spec**（user / 後續 orchestrator 跑此驗證才算 P1 ✅ done）：
    1. 環境：D:\Hadamard 或其他有 Mathlib 的 lake env
    2. `pip install -e D:\Asterism`（驗 console script 安裝、C7 R3 #1 修的 build-backend 真跑）
    3. 在臨時 work dir 跑 phase1_skeleton.md ## Demo 線 51-77 完整 bash（init / cat strat.lean by simp / goal add / run --once / goal show G_root）
    4. 預期 final stdout 含 `status:    proved` + `answer_data:` + `type: classical` + `lean_path: ...`
    5. 預期非 0 dead_attempts（rfl 等先試、simp 命中前的失敗）OR 直接 simp 命中（要看 TACTICS list 順序）
    6. 觀察 cold-cache 真實時間（spike-001 數據預估 200s+，warm-cache <30s）—— 為 P3 cache subsystem 設計 baseline
- **#4 [LOW] `demo_add_zero_simple.lean` 為 orphan fixture、AC#0/#6/#9 inline 重複**：fixture 內容（`import Mathlib / theorem add_zero_simple ... := by simp`）與 3 處 inline write_text 完全重複、DRY 違反、改 demo 內容需 4 處同步。R3 加 `_DEMO_LEAN = _FIXTURES / "demo_add_zero_simple.lean"` constant、3 處 inline 換成 `_DEMO_LEAN.read_text(encoding="utf-8")`。fixture 註解同步更新（LAKE_MOCK_PROVED → LAKE_MOCK）。`test_phase1_acceptance.py:35-36, 161-164, 421-423, 583-584`、`fixtures/demo_add_zero_simple.lean:2-4`。
- **#5 [LOW] AC#0 subprocess 用 `python -m Tooling.cli` 而非 `asterism`**（同步驗 install path）：phase1_skeleton.md ## Demo 字面 `asterism ...`、C7 R3 已修 pyproject build-backend 應裝出 console script。R3 加 `_cli_cmd()` helper：`shutil.which("asterism")` 命中 → 用 console script、未命中 → fallback `[sys.executable, "-m", "Tooling.cli"]`。對 CI 環境同步 sanity check `pip install -e .` 整鏈條（C7 R3 #1 修的 critical bug）。`test_phase1_acceptance.py:130-138`（+9）。
- **#6 [LOW] AC#11 working dir 保留 字面未驗**：phase1_skeleton.md acceptance #11 線 93 字面「fatal event + scheduler halt + working dir 保留 + DB 現場保留」、R1 只驗 DB rows 保留、檔案系統未驗（P1 vacuously true 因為無 cleanup 路徑）。R3 加 2 行 assert：`strategy_lean.exists()` + `goal_lean.exists()`，同時 inline comment 標明 P1 vacuously true 但對 P2+ cleanup 路徑加入時為 regression guard。`test_phase1_acceptance.py:740-744`（+5）。

**Noted（#7-#10 不修，全合理）**：

- **#7 CI workflow 跑 `Tooling/tests/` superset 而非 `test_phase*.py` glob**：superset 含所有 phase test、cumulative gate 達成、精神對齊
- **#8 commit.py 表序 ("strategies", "goals") 對 P1 所有 path 安全**：R2 已驗 4 種 P1 場景（INSERT-only goals / INSERT-only strategies / UPDATE goals + INSERT strategies / 兩表 UPDATE）皆 OK
- **#9 builder._resolve_path 無副作用**：`is_absolute()` short-circuit、既有 16 個 builder unit tests 全 pass、新邏輯只在 relative path 觸發
- **#10 AC#5 hash check 字面未驗（C4 carryover）**：recover_scan 不存 staging_path 無法重做 hash compare、`shutil.move` atomic 蘊含 step 2 succeeded、direct finalize 達同 terminal state；P2+ 加 staging_path column 才能精確還原 spec 字面

**驗證**：
- `pytest Tooling/tests/test_phase1_acceptance.py -v` → **14 passed**，0.95s
- `pytest Tooling/tests/` → **158 passed**（無 regression），2.08s
- `git diff --stat HEAD~1 HEAD` → `Tooling/lake.py +6/-5` + `Tooling/tests/fixtures/demo_add_zero_simple.lean +2/-2` + `Tooling/tests/test_phase1_acceptance.py +29/-23` + `docs/dev/test_hooks.md +1/-0` = 4 files / +38 / -30
- `grep "LAKE_MOCK" docs/dev/test_hooks.md` → 1 row 命中（cross-phase rule satisfied）
- `grep "LAKE_MOCK_PROVED\|LAKE_MOCK_SORRY" Tooling/` → 空輸出（舊命名完全清除）

**邊界**：未動 architecture / phase doc / spike doc / Tooling/cli.py / Tooling/scheduler.py / Tooling/db/ / commit.py / builder.py / .github/ / AutoDev；未引入新依賴（純 stdlib + shutil.which）；test_hooks.md 動為「加新 hook 才動」例外條款下合法行為。

**Caveat**：
- C8 R1 既有 caveat 仍適用（mock != real lake；CI 純 Python 環境無 lake/Lean）
- AC#0 用 `shutil.which("asterism")` fallback 設計：CI workflow `pip install -e .` step 後、`asterism` 應在 PATH 命中、走真實 console script；本地開發未 install 時 fallback 到 `python -m Tooling.cli`，兩條路徑都 OK 但 console script 路徑等同 demo bash 字面對齊
- LAKE_MOCK 命名 P1 release 後語意凍結（test_hooks.md 規則）：P2+ 加新 outcome 直接擴 enum（`LAKE_MOCK=proved|sorry|typeerror|timeout`）、不另加 env var
- Manual real-lake demo 驗證為 P1→P2 transition gate；user 必須跑一次貼 stdout 才算 P1 ✅ done。本 R3 commit 後 P1.C8 functional ✅、但 phase progress 「P1 ✅ done」標記建議等 manual demo verification 跑通後 user 確認再升

---

**C8 R1 — Demo theorem + P1 acceptance tests #0–#11 + CI**

Commit `609f41c`，6 files changed / +778 / -3：

**新增**：
- `Tooling/tests/test_phase1_acceptance.py`（~530 行）：12 acceptance test，對齊 phase1_skeleton.md §Acceptance criteria #0–#11
  - **#0** `TestAC0DemoSubprocess`：subprocess 呼叫 `python -m Tooling.cli`（CWD=tmp_path, PYTHONPATH=repo-root, LAKE_MOCK_PROVED=1）完整走 init → goal add → run → goal show，assert "proved" + "classical" in stdout
  - **#1** `TestAC1SqlSchema`（3 sub-tests）：13 table 存在；6 table spot column 完整；nullable P2+ column 接受 NULL
  - **#2** `TestAC2RecoveryInsertStrategies`：pending INSERT strategies row（lean_path 不存在）→ recover_scan → deleted
  - **#3** `TestAC3RecoveryInsertGoals`：pending goals + strategies rows → recover_scan → 兩表都 deleted（驗 FK-safe 順序）
  - **#4** `TestAC4RecoveryUpdateStrategies`：pending UPDATE strategies（有 snapshot）→ recover_scan → status 還原
  - **#5** `TestAC5RecoveryMvAfterKill`：lean_path 存在（mv done）+ pending → recover_scan → finalize → commit_state=live
  - **#6** `TestAC6LakeIntegrationPass`：full Reactor path，mocked run_lean=proved → goal.status=proved
  - **#7** `TestAC7SorryDetection`：spike003_sorry_nolib.lean fixture，mocked run_lean=hasSorry → exhausted + dead_attempts 含 sorry reason
  - **#8** `TestAC8TWallTimeout`：mock time.monotonic=[0,3] + T_wall=2s → exhausted, timed_out=True, run_lean 0 呼叫
  - **#9** `TestAC9CliChain`：in-process CLI chain（init→goal add→run→goal show），redirect_stdout 驗 proved + classical
  - **#10** `TestAC10Idempotent`：第二次 run → queue empty → exit 0，Builder 0 次呼叫，events count 不變
  - **#11** `TestAC11CascadeFatalHalt`：patch _update_goal_proved raise IntegrityError → exit 1 + fatal event + goal/strategy rows 保留
- `Tooling/tests/fixtures/demo_add_zero_simple.lean`：demo theorem `import Mathlib / theorem add_zero_simple (n : Nat) : n + 0 = n := by simp`
- `.github/workflows/ci.yml`：ubuntu-latest + windows-latest matrix，pip install -e . + pytest Tooling/tests/

**修改**：
- `Tooling/lake.py`：加 `import os`；加 `LAKE_MOCK_PROVED=1` / `LAKE_MOCK_SORRY=1` env hook（run_lean 開頭提前 return，prod 不設 env 零 overhead）
- `Tooling/commit.py`：`recover_scan` 迴圈順序由 `("goals", "strategies")` 改為 `("strategies", "goals")`，確保 FK child rows 先刪（修正 AC#3 FK violation bug）
- `Tooling/pipelines/builder.py`：加 `_resolve_path(lean_path)` method，將相對 lean_path 相對 base_dir 解析為絕對路徑；`run()` 的 `read_text` 和 `_commit_success` 的 `stage_file` 都改走 `_resolve_path`（修正 in-process 測試 CWD≠base_dir 下 FileNotFoundError）

**驗證**：
- `pytest Tooling/tests/test_phase1_acceptance.py -v` → **14 passed**，1.02s
- `pytest Tooling/tests/ -v` → **158 passed**（144→158），1.99s，0 regression

**Caveat**：
- Demo bash (#0) 走 LAKE_MOCK_PROVED=1 mock 路徑，沒有跑真正的 Lean/Mathlib。真實 demo 需要 lake 環境（D:\Hadamard Mathlib path），cold cache 可能 5–15 分鐘。手動驗真實 demo 步驟：`pip install -e .` → 建 strat.lean 含 `import Mathlib / theorem add_zero_simple (n : Nat) : n + 0 = n := by simp` → `asterism init --problem example && asterism goal add ... && asterism run --once && asterism goal show G_root`，需在有 lake env 的 shell 跑
- CI yml 不含 lake/Lean 安裝步驟：所有 lake 呼叫在 pytest 中透過 mock hook 繞過，CI 可純 Python 環境通過。若未來 C9+ 需真實 lake CI，需在 workflow 加 elan/lake setup step
- `_resolve_path` 只在 `base_dir` 非空且 lean_path 為相對路徑時生效；現有 test_builder.py 用絕對 tmp_path 路徑，行為不變（is_absolute() 為 True 直接回傳）
- recover_scan 順序改動（strategies→goals）不影響任何既有測試：舊測試只測各 table 單獨 recovery 或 strategies 只，無 cross-table FK test。AC#3 是新增的唯一驗 FK-safe 順序的 test

**C7 R3 — Fix R2 audit findings (build-backend critical + G_root alias + conn.close + CommitFault catch + e2e)**

R2 找到 1 critical + 5 fixable + 4 noted。1 critical + 5 fixable 全合理、全處理（commit `ae6f87c`）：

**Critical（必修）**：

- **#1 pyproject.toml build-backend 拼錯**（真 critical、1 行修）：原寫 `"setuptools.backends.legacy:build"` 不是真實存在 backend——`setuptools` 沒有 `backends` 子 package、`pip install -e .` BackendUnavailable、`asterism` console script 無法安裝、phase1_skeleton.md ## Demo + acceptance #0/#9 字面 `asterism ...` 命令在 C8 demo bash 跑時會直接斷。R3 修為 `"setuptools.build_meta"`（標準 setuptools backend）。**驗證**：`python -c "import setuptools.build_meta"` OK；`pip install -e . --dry-run` → `Would install asterism-0.1.0` ✓。R1 自驗只跑 `python -m Tooling.cli --help`、未驗 `pip install`，疏漏明顯。

**Fixable（全修）**：

- **#2 goal show G_root 字面被拒**（demo 字面對齊、phase doc 唯讀無法改、選 audit (a) 加 alias）：phase1_skeleton.md ## Demo 線 76 字面 `asterism goal show G_root` 必須跑通、但 R1 `_parse_goal_id` 走 `int("root")` ValueError → exit 1。原 R1 自我辯護「demo 字面 G_root 視為說明文字」是執行者詮釋，task.md 線 55 規則下 phase doc bug 應暫停而非自行詮釋；audit 採最低摩擦解=加 alias。R3 加 `_resolve_goal_id(raw, conn)`：先試 `_parse_goal_id`（integer / G_N），失敗時若 raw 是 'root' / 'g_root' / 'G_root'（case-insensitive）→ SELECT WHERE origin='root' ORDER BY id；多 root → warning + 取最早；無 root → None → exit 1。`cmd_goal_show` 改用 `_resolve_goal_id`。原 `test_invalid_goal_id_format_exits_1` 鎖死 G_root → exit 1，R3 改用 'xyz' 為 invalid format。新增 2 tests：`test_root_alias_resolves_to_origin_root`（G_root + 'root' 都解析到 origin='root' goal）、`test_root_alias_with_no_root_goal_exits_1`。`cli.py:226-258`（+22）、`test_cli.py:354-378`（+25/-4）。

- **#3 META.md broken promise**（cosmetic、1 行 + 範本字串改）：原範本「(Populated automatically as goals are added via `asterism goal add`.)」但 `cmd_goal_add` 不對 META.md 做 append/update。R3 採 audit (a)：改範本字串為「(List goals manually here, or query `asterism goal show <id>` / `sqlite3 asterism.db` for live state. P1 does not auto-rewrite this file.)」。零功能損失、pytest test_meta_contains_axioms 三公理斷言仍 pass（axioms 段未動）。`cli.py:43-46`。

- **#4 cmd_goal_add / cmd_db_recover / cmd_goal_show 連線洩漏**（hygiene、3 函數加 try/finally）：P1 short-lived CLI process 0 功能影響、但 pytest 累積 36 conn 不關，未來改 file-based fixture 可能撞 sqlite3 too-many-connections。R3 三個 cmd_* 函數各加 `try: ... finally: conn.close()`，cmd_goal_show 整個 query block 縮進進 try。對齊 C4 R3 「fixture yield + close 低成本買保險」決策一致。`cli.py:117-185, 211-227, 286-329`。

- **#5 CommitFault traceback 噴 stderr**（user-friendly、4 行 fix）：原 `cmd_goal_add` 不 catch `CommitFault`，COMMIT_FAULT=after_step1 路徑下 user 看到 raw Python traceback。R3 加 `except CommitFault as exc: print(f"goal add: interrupted by COMMIT_FAULT ({exc}); run \`asterism db recover\` to clean up", file=sys.stderr); sys.exit(2)`。Pending row 故意保留（acceptance #3 recovery path 不變、CommitFault 在 step 1 commit 後才 raise，TX 已落 DB）。新增 `test_commit_fault_after_step1_exits_2_friendly`（test_cli.py:182-205）：monkeypatch.setenv COMMIT_FAULT、驗 SystemExit code=2 + stderr 含「COMMIT_FAULT」+「db recover」+ goals row commit_state='pending'（recovery-ready）。`cli.py:177-185`（+8）、`test_cli.py:182-205`（+24）。

- **#6 缺 init → goal add → run → goal show end-to-end test**（acceptance #9 信心、25 行 1 test）：R1 三層分散 unit test 拼湊覆蓋；R3 補 `TestEndToEnd::test_init_goal_add_run_show_proved`（test_cli.py:484-560, +77）：fresh tmp_path → cmd_init → cmd_goal_add（real CommitWriter path）→ verify queue 1 row → cmd_run（patch `Tooling.scheduler.Builder` factory，fake `run()` 直接 UPDATE strategies.status='succeeded' 並回 BuilderResult(outcome='proved')）→ verify SystemExit(0) + goals.status='proved' + answer_data.type='classical' + queue empty → cmd_goal_show 顯示 'proved' / 'classical' → 再驗 `goal show G_root` alias 也顯示 proved。對齊 C6 R3 `test_cascade_fatal_end_to_end` 的 e2e 覆蓋模式。

**Noted（#7-#10 不修，全合理）**：

- **#7 begin_batch API 不支援「上一 op id 流入下一 op」**：CommitWriter 設計局限、不是 bug；中間態 crash recover_scan 行為正確。
- **#8 `_parse_goal_id` 「G」開頭 strip 過寬鬆**：edge cases 都正確 fall to None；cosmetic robustness。
- **#9 `test_leaf_strategy_flag_in_help` 用 argparse private API**：當前能跑、phase doc 不要求特定驗法。
- **#10 db recover 對不存在 DB silent 建空**：phase doc 不要求 fail-fast、P1 cosmetic。

**驗證**：
- `pytest Tooling/tests/test_cli.py -v` → **36 passed**（32→36，+4 R3 tests），0.80s
- `pytest Tooling/tests/` → **144 passed**（140→144，零 regression），1.23s
- `pip install -e . --dry-run --no-deps` → `Would install asterism-0.1.0` ✓
- `python -m Tooling.cli init --problem ex` + `goal add` + `goal show G_root` smoke → G_root 解析到 G_1 並顯示 status ✓
- `COMMIT_FAULT=after_step1 python -m Tooling.cli goal add ...` smoke → friendly stderr「interrupted by COMMIT_FAULT (COMMIT_FAULT=after_step1); run \`asterism db recover\` to clean up」+ exit 2 ✓
- `git diff --stat HEAD~1 HEAD` → `Tooling/cli.py +155/-112` + `Tooling/tests/test_cli.py +138/-0` + `pyproject.toml +1/-1` + `.gitignore +4/-0` = 4 files / +298 / -113

**邊界**：未動 architecture / phase doc / spike doc / lake.py / commit.py / db/ / scheduler.py / builder.py / AutoDev；未引入新依賴（純 stdlib）。`.gitignore` 補 `*.egg-info/`（pip install -e build artifact）。

**Caveat**：
- C7 R1 既有 caveat 仍適用（兩個獨立 begin() 而非 begin_batch、placeholder lean_path UUID4 碰撞理論可能、`run --daemon` P1 等同 `--once`、pipelines orphan recovery 推遲 P2+）。
- `_resolve_goal_id` 'root' alias 的 P2+ 行為：multi-root（多 problem / Backward 自動產 root goal 等場景）會 emit warning 並取最早 id；P1 P=1 single-Problem 場景下總有唯一 root，acceptance #0 demo 無歧義。P2+ multi-root 場景時 user 應改用 integer ID 明確指定。
- `cmd_goal_add` `except CommitFault` 後 sys.exit(2) ≠ exit 1（exit 1 留給 user 錯誤如 missing leaf-strategy file）；fault injection 路徑用 exit 2 區隔。phase doc 不要求特定 exit code、選 (2) 為 convention（git status convention：1=user error, 2=internal/fault）。
- `pip install -e .` 仍為 dry-run 驗證；real install 在 C8 demo cycle 跑通整個 acceptance #0 bash 時實機驗。

---

**C7 R1 — CLI (Tooling/cli.py + tests + pyproject.toml)**

新增 3 個檔案，commit `ba7ed24`：

- **Tooling/cli.py**：5 subcommand CLI（~240 行）
  - `build_parser()`：argparse nested subparsers（init / goal{add,show} / run / db{recover}）
  - `cmd_init(args, base_dir)`：建 `Problems/<name>/{META.md, Defs.lean, Root.lean}`；META.md 含三公理範本（ASCII-only）；idempotent（不覆蓋既存檔）
  - `cmd_goal_add(args, db_path, base_dir)`：
    - CommitWriter.begin('goals', 'insert', placeholder lean_path) → goal_id
    - CommitWriter.begin('strategies', 'insert', placeholder lean_path) → strategy_id
    - 用 goal_id / strategy_id 計算 canonical `<id>_<slug>` 路徑
    - 建 goal lean file（空 placeholder）
    - CommitWriter.stage_file(leaf, canonical_strategy_lean) — mv leaf-strategy
    - CommitWriter.finalize goals（更新為 canonical lean_path）
    - CommitWriter.finalize strategies（更新為 canonical lean_path）
    - INSERT queue row（kind=Builder, target_id=strategy_id, priority=0）
  - `cmd_run(args, db_path, base_dir)`：Reactor(db, config).run() 包裝；--once / --daemon P1 行為等同（exit-after-empty-queue）
  - `cmd_db_recover(args, db_path)`：connect → init_schema → CommitWriter.recover_scan → human-readable report
  - `cmd_goal_show(args, db_path)`：`_parse_goal_id` 接受 1 / G_1 / G1 格式；查 goals + strategies → 顯示 status / kind / lean_path / depth / answer_data / strategies list
  - `--leaf-strategy` help text 明示 `[P1 testing-only; P2 removes this flag]`

- **Tooling/tests/test_cli.py**：32 unit tests（8 test class）
  - `TestParseGoalId`（5）：integer / G_N / GN / case-insensitive / invalid→None
  - `TestInit`（4）：建目錄結構；META.md 含三公理；idempotent；多 problem
  - `TestGoalAdd`（6）：goals row 對齊；strategies row 對齊；file mv；queue row；canonical id_slug path；missing file → exit 1
  - `TestRun`（2）：Reactor.run mock 呼叫；db_path 傳入驗
  - `TestDbRecover`（3）：recover_scan mock 呼叫；clean DB message；recovered rows 報告
  - `TestGoalShow`（5）：status 輸出；answer_data proved；strategies list；unknown → exit 1；invalid G_root → exit 1
  - `TestParser`（7）：各 subcommand argparse 解析 smoke；leaf-strategy help 含 P1/P2 note

- **pyproject.toml**：`asterism = "Tooling.cli:main"` entry point（setuptools）

**設計決策**：

- **CommitWriter 兩階段 INSERT 解決 lean_path 雞蛋問題**：goals.lean_path 需要 goal_id（auto-increment），但 goal_id 只有 INSERT 後才知。解法：begin('insert') 用 UUID placeholder lean_path 取得 real ID → finalize 更新為 canonical `<id>_<slug>` 路徑。Recovery 在 COMMIT_FAULT=after_step1 時正確 DELETE pending rows（C8 acceptance #3 可跑通）。
- **testability 設計**：所有 cmd_* 函數接受 `db_path` / `base_dir` 可注入參數（default None → 用標準路徑），不需 monkeypatch 或 subprocess。
- **`goal show` 接受 G_N / GN / integer**：`_parse_goal_id` 統一處理，`G_root` 之類無法 parse 為 integer 的格式 → exit 1（demo 字面 "G_root" 視為文件占位符，實際用 integer ID）。
- **`--leaf-strategy` P1 testing-only 標注**：help text 明示 `[P1 testing-only; P2 removes this flag - Backward will auto-generate leaf strategies]`；符合 CLI 介面凍結 D2 決策。

**驗證**：
- `pytest Tooling/tests/test_cli.py -v` → **32 passed**，0.71s
- `pytest Tooling/tests/` → **140 passed**（108→140、+32 cli tests；無 regression），1.14s
- `python -m Tooling.cli --help` → 正常顯示 4 個 subcommand
- `python -m Tooling.cli goal add --help` → 顯示 --leaf-strategy 含 P1 testing-only 標注

**邊界**：未動 architecture / phase doc / spike doc / lake.py / commit.py / db/ / builder.py / scheduler.py / AutoDev；未引入新依賴（純 stdlib）。

**Caveat**：
- `goal add` 使用 UUID placeholder lean_path 兩段 begin()：若 COMMIT_FAULT=after_step1 在第一個 begin() 後 raise，只有 goals row pending，strategies 未 INSERT。COMMIT_FAULT=after_step1 在第二個 begin() 後 raise，goals + strategies 都 pending，file 未移。兩種情境 recover_scan 都正確 DELETE——acceptance #3 C8 phase 可驗。
- `goal add` 的 placeholder lean_path（`Goals/_pending_<uuid>/<slug>.lean`）在極短時間內存在 DB（pending state），若系統同時有另一個 goal add 用相同 UUID（機率極低）會觸發 UNIQUE constraint。UUID4 碰撞率可忽略不計。
- `goal show G_root` 格式（非整數 suffix）→ exit 1（未 implement "G_root" 別名 lookup）；demo 字面 "G_root" 視為說明文字、實際用 `asterism goal show 1`。
- `run --daemon` P1 等同 `--once`（都 exit-after-empty-queue）；help 已明示「P2+ only」。
- pipelines orphan recovery 推遲 P2+（C6 R3 caveat 延續）：P1 P=1 無觸發點。

---

**C6 R3 — Fix R2 audit findings (cascade narrow except + dispatch fatal emit + e2e test + cosmetic)**

R2 找到 7 fixable + 3 noted。7 fixable 全合理、逐一處理（commit `0f5394f`）：

**Fixable（全修）**：

- **#1 cascade trigger 用 BuilderResult.outcome 而非 strategies.status='succeeded'**（phase doc 字面偏離、選 (a) 加 inline comment）：phase1_skeleton.md ## Scope ## In 線 27 字面是「strategies.status='succeeded' → goal proved」（DB-driven），實作走 BuilderResult.outcome=='proved'。P1 功能等價（Builder 是唯一 producer、`_commit_success` 走 finalize 寫 status='succeeded' 與 outcome 同 step）但 P2+ Backward 加進來後 strategies.status 可能由其他 pipeline 改變，trigger 應轉查 DB。R3 在 `_cascade` docstring 加 8 行 inline comment 標 P1 假設 + P2+ 重檢點。`scheduler.py:111-122`（+9）。
- **#2 `_cascade` `except Exception` 過寬**：phase doc 列「unique constraint / FK / json 格式錯」（前兩個 sqlite3.IntegrityError、後者本路徑無 json.loads 不適用）。原 `except Exception` 把 programming bug（TypeError / AttributeError / 未來 _emit_event 內 bug）也視為 fatal、debug 時資訊損失。R3 narrow 到 `except sqlite3.Error`、補 `import sqlite3`、加 4 行 inline comment 標「sqlite3.Error 涵蓋 unique/FK；programming bug 故意不 catch、propagate uncaught for fast debugging」。`scheduler.py:14, 138-145`（+5）。
- **#3 `_dispatch` unknown kind 缺 fatal event**（觀察一致性）：原本只 raise FatalError、不 emit fatal event；與 cascade SQL fail 路徑不對稱（後者寫 events.fatal 留 audit）。R3 加 `_emit_fatal(msg)` call，並 extend `test_dispatch_unknown_kind_raises_fatal` 驗 events.fatal row + payload 含「Backward」kind 名。`scheduler.py:107-110`（+3）、`test_scheduler.py:178-189`（+9）。
- **#4 缺 acceptance #11 真實 end-to-end test**：原 `TestFatalHalt` 三 tests 各驗單元（直 call `_cascade` patched / 直驗 raise / patch `_dispatch` raise → exit 1），無串「queue → real _pop_queue → real _dispatch (Builder mock proved) → real _cascade SQL fail → SystemExit(1) + fatal event + DB 現場保留」整條 path。R3 新增 `test_cascade_fatal_end_to_end`（test_scheduler.py:267-309, +43 行）：實際開 DB file → init_schema → 寫 goal/strategy/queue rows → close → `Reactor.startup()` → patch `Tooling.scheduler.Builder` 回 proved → patch `_update_goal_proved` raise IntegrityError → `_run_loop` → assert SystemExit(1) + events.fatal row + strategy/goal rows still queryable。對齊 phase1 acceptance #11 字面（「人為 inject 重複 lean_path 觸發 unique constraint → fatal event + halt + 保留現場」）。
- **#7 Test fixture `__new__` hack**（cosmetic）：原 `_make_reactor` 用 `Reactor.__new__(Reactor)` bypass `__init__`、屬 Python hack。`Reactor.__init__` 已將 self.conn 預設 None，可直接 `Reactor(db_path, config)` 後注入 `conn=db`。R3 改 `_make_reactor` 為 5 行 regular constructor + 後設 conn=db（test_scheduler.py:43-49, ±2 行 net）。Future-proof：`Reactor` 加新 field 時 `__init__` 會自動初始化、不會 silent skip。

**選 devlog 路（不擴 code 範圍）**：

- **#5 Pipelines orphan recovery 缺**（C5 R3 devlog 自記「C6 處理」未兌現）：phase1_skeleton.md acceptance #0–#11 沒明列 pipelines orphan scan 為要求；嚴格走 phase doc 字面，不是 C6 mandate。但 C5 R3 devlog 自寫「C6 reactor cycle 啟動時補上 pipelines.status='running' 的 orphan recovery scan」、形成內部不一致。R3 採 audit 建議的 (b) 路：**將該議題正式推遲到 P2+ scope**。理由：(1) phase1 doc 不要求；(2) P1 P=1 + 同步呼叫 + Builder commit raise 路徑由 CommitWriter recover_scan 已處理 strategies.commit_state='pending'，pipelines.status='running' orphan 不影響 acceptance #0-#11；(3) P2 daemon mode + atomic pool 才是 pipelines orphan 真實風險場域。P2 reactor 升級 cycle 補 orphan scan + 配套 test。**C5 R3 devlog 該條 caveat 視為已被本 C6 R3 條更新覆蓋**（不另回去改 C5 R3 devlog 條目，避免動已 commit history-attached 內容）。
- **#6 `_pop_queue` SELECT/DELETE 非單一 TX 原子**（P1 P=1 安全）：原實作 SELECT 走 autocommit read、DELETE 走獨立 `with self.conn:` BEGIN/COMMIT；理論上兩 worker 並發會 race。P1 P=1 單執行緒、單 process、無此 race 觸發點。P2+ daemon mode 多 worker（config P=2 atomic pool）下需轉 single-TX claim 模式（如 `UPDATE queue SET claimed_by=? WHERE id IN (SELECT ... LIMIT 1) RETURNING *`）或 advisory lock。**正式記入 P2+ scope**：P2 reactor 升級 cycle 補 single-TX claim + 並發 test（`pop` race 觀察）。

**Noted（不修）**：

- **#8 cascade event payload forward-compat**：當前 `{strategy_id, goal_id, rule}` 足夠 P1 audit；P6+ Library promotion 加新 cascade rule 時格式可一致延伸。
- **#9 `BuilderResult` import for type hint**：保留對 IDE / mypy 友善；無實質 overhead。
- **#10 `_cascade` strategies row missing 容忍**：spec 不要求；P1 enqueue 由 CLI 寫、跟 strategies INSERT 同 cycle、row missing 不該發生；silently return 是合理選擇。

**驗證**：
- `pytest Tooling/tests/test_scheduler.py -v` → **20 passed**（19→20、+1 end-to-end），0.40s
- `pytest Tooling/tests/` → **108 passed**（107→108、無 regression），0.71s
- `git diff --stat HEAD~1 HEAD` → `Tooling/scheduler.py +25/-3` + `Tooling/tests/test_scheduler.py +63/-3` = 2 files / +88 / -6

**邊界**：未動 architecture / phase doc / spike doc / `Tooling/lake.py` / `Tooling/commit.py` / `Tooling/db/` / `Tooling/pipelines/builder.py` / AutoDev；未引入新依賴（`sqlite3` 為 stdlib）。

**Caveat**：
- `_pop_queue` SELECT/DELETE 兩段非原子（#6 noted）：P1 P=1 安全；P2+ daemon multi-worker 需轉 single-TX claim 模式
- Pipelines orphan recovery 推遲 P2+（#5 noted、覆蓋 C5 R3 自記的 C6 承諾）：P1 acceptance #0-#11 不要求、P=1 同步路徑無觸發點
- `_cascade` 容忍 strategies row missing（#10 noted）：P1 enqueue 路徑保證該情境不發生；若硬要嚴 P2+ 補 warning event
- C6 R1 既有 caveat 仍適用：cascade trigger 走 BuilderResult.outcome（#1 inline comment 已標 P2+ 轉 DB read）；`_dispatch` 對 unknown kind 已 emit fatal + halt（#3 修後對齊觀察一致性）

---

**C6 R1 — Reactor skeleton (Tooling/scheduler.py + unit tests)**

新增 2 個檔案，commit `0fec0ea`：

- **Tooling/scheduler.py**：Reactor 雛型（~140 行）
  - `ReactorConfig(t_wall, lake_timeout, base_dir)`：config 注入；Builder 同一套 config 結構
  - `FatalError(Exception)`：cascade SQL 不可回復錯誤的內部訊號；`_run_loop` catch 後 `sys.exit(1)`
  - `Reactor(db_path, config).startup()`：`connect(db_path)` → `init_schema` (idempotent) → `CommitWriter.recover_scan()`
  - `Reactor.run()`：`startup()` + `_run_loop()`
  - `Reactor._run_loop()`：`while True: pop → dispatch`；pop None → `sys.exit(0)`；catch FatalError → `sys.exit(1)`
  - `Reactor._pop_queue()`：`SELECT ... ORDER BY priority DESC, id ASC LIMIT 1` + `DELETE`；回傳 `{id, kind, target_id, payload}` 或 None
  - `Reactor._dispatch(task)`：P1 只處理 kind='Builder'；其他 kind → `raise FatalError`；Builder 同步執行 `.run()` → `_cascade`
  - `Reactor._cascade(strategy_id, result)`：result.outcome!='proved' 直接 return；查 strategies.goal_id + lean_path → `answer_data={"type":"classical","lean_path":"..."}` → `_update_goal_proved` → emit cascade event；Exception → `_emit_fatal` + `raise FatalError`
  - `Reactor._update_goal_proved(goal_id, answer_data)`：`UPDATE goals SET status='proved', answer_data=?`（抽離為獨立方法供測試 patch）
  - `Reactor._emit_event(kind, payload)`：INSERT events row
  - `Reactor._emit_fatal(error)`：best-effort fatal event emission（swallow 自身 exception，保留原始錯誤傳播路徑）

- **Tooling/tests/test_scheduler.py**：19 unit tests（7 test class）
  - `TestStartup`（2）：`recover_scan` mock assert_called_once；DB 檔建立 + schema tables 驗
  - `TestQueuePop`（5）：pop 回 task dict；pop 刪 row；empty → None；priority desc；FIFO within same priority
  - `TestDispatch`（2）：Builder(strategy_id, conn, ANY) 呼叫 + `.run()` 呼叫；unknown kind → FatalError
  - `TestCascadeProved`（3）：goal.status='proved'；answer_data json 含 type+lean_path；cascade event emitted
  - `TestCascadeExhausted`（2）：goal.status 不變；events 0 row
  - `TestFatalHalt`（3）：cascade SQL error → fatal event written + payload 含 error msg；FatalError 確實 raise；`_run_loop` with patched `_dispatch` FatalError → SystemExit(1)
  - `TestQueueEmptyExit`（2）：`_run_loop` empty queue → SystemExit(0)；`run()` integration test（fresh DB → startup → empty queue → exit 0）

**設計決策**：
- `_run_loop` 與 `startup` 分離：方便測試單獨呼叫 `_run_loop`（注入 conn 跳過 startup）
- `_update_goal_proved` 抽離：讓 fatal 單元測試可 `patch.object(reactor, '_update_goal_proved', side_effect=IntegrityError(...))`，不需要繞 sqlite3.Connection.execute 的 C-extension patch 困難
- `_emit_fatal` best-effort：fatal 時 DB 可能不穩，swallow 自身 exception 確保原始 FatalError 正常傳播
- `sys.exit(0/1)` 在 `_run_loop` 而非 `run()`：測試可直接測 `_run_loop` 拿到 SystemExit；`pytest.raises(SystemExit)` 標準 pattern

**驗證**：
- `pytest Tooling/tests/test_scheduler.py -v` → **19 passed**，0.34s
- `pytest Tooling/tests/ -v` → **107 passed**（88→107、+19 scheduler tests；無 regression），0.70s
- `git diff --stat HEAD~1 HEAD` → `Tooling/scheduler.py +140/-0` + `Tooling/tests/test_scheduler.py +296/-0` = 2 files / +536 / -0

**邊界**：未動 architecture / phase doc / spike doc / lake.py / commit.py / db/; 未引入新依賴（純 stdlib）。

**Caveat**：
- P1 `_dispatch` 對 unknown kind 直接 raise FatalError（halt）；P2+ 補多種 pipeline kind 時需在此加 dispatch entry，不是 if-else 擴展（per phase1_skeleton.md ## Scope ## In cascade dispatch table 設計）
- Cascade rule 只讀 `strategies.lean_path`（不重查 DB strategies.status）；假設 Builder 已正確 UPDATE strategies.status='succeeded' 且 lean_path 存在——C8 end-to-end test 驗完整路徑
- `_update_goal_proved` 只 UPDATE goals.status + answer_data，不寫 goals.status_changed_at（nullable P2+ 欄位）；accept criteria #11 的 fatal trigger 由測試 patch `_update_goal_proved` raise IntegrityError 覆蓋

---

**C5 R3 — Fix R2 audit findings (T_wall per-call clamp + comment + hygiene)**

R2 找到 4 fixable + 6 noted。4 fixable 全合理、逐一處理（commit `f5a0091`）：

**Fixable（全修）**：

- **#1/#5 T_wall 不約束單個 lake 呼叫**（真議題、phase1 acceptance #8 字面要求、5-7 行 fix + 2 tests）：原 impl 每次 `run_lean` 都拿完整 `lake_timeout=600s`，慢 lake build 場景下 wall-clock 可能 30s+ 才返回，違反「2s 後 pipeline 直接 outcome=exhausted」字面要求。R3 在 tactic loop 內計算 `elapsed = time.monotonic() - self._start` 後保留 `remaining = t_wall - elapsed`，傳 `min(lake_timeout, remaining)` 給 `run_lean(timeout=...)`——lake 本身已支援 timeout + `_kill_tree`（C2 既有基礎建設），單個慢 tactic 也會被 T_wall 強制中斷。`builder.py:99-110`（+9/-3）。
- **#5 TestTWall 缺 mid-loop break test**（連動 #1）：原 `TestTWall` 兩 tests 都是「進場前已超」degenerate case（`mono_seq=[0.0, 10.0]`），run_lean 0 呼叫；沒驗 acceptance #8 真實情境。新增兩 tests（test_builder.py:294-352, +58 行）：
  - `test_twall_breaks_mid_loop`：`mono_seq=[0.0, 0.5, 1.5, 3.0]` + t_wall=2s → rfl + simp 進入（`run_lean` exhausted）後 decide entry 觸發 break；assert `mock_lake.call_count == 2`、`dead_attempts` 2 row、`timed_out=True`
  - `test_twall_clamps_per_call_timeout`：`mono_seq=[0.0, 1.5]` + t_wall=2.0 + lake_timeout=600.0 → 進入 rfl 時 remaining=0.5；用 fake_run capture timeout 參數，assert `captured == [0.5]`
- **#3 `_replace_proof_body` 加 inline comment**（cosmetic、5 行 docstring）：原 docstring 只說「替換最後 `:=` 之後」、沒說明 P1 假設。R3 加 5 行 docstring 標註「P1 demo theorem（無 `let x :=` / 無 `arg : T := default`）安全；P2+ tactic_llm 可能產生 `by exact (let x := 5; x)` 或 `have : Q := q1; ...` 形式 proof body、屆時需嚴格 Lean parser 或 staging template 標記 proof body 起始位置」。`builder.py:38-50`（+7/-1）。
- **#6 移除 unused `dataclasses.field` import**（cosmetic、1 char）：原 `from dataclasses import dataclass, field` 中 `field` 未使用（兩個 dataclass 都只用 default 值、無 `default_factory`）。R3 改 `from dataclasses import dataclass`。`builder.py:11`（-1 char）。

**Noted（自行判斷不修）**：

- **#2 dead_attempts 直接 INSERT 不走 CommitWriter**：devlog C5 R1 caveat 已標、CommitWriter API 沒設計 dead_attempts 路徑、append-only audit log 無 .lean stage_file 需求；P2+ failure_archive stage 接管。
- **#4 pipelines.status 'running' 殘留**（`_commit_success` raise 後 `_finish_pipeline` 不執行）：recover_scan 只掃 goals + strategies 兩表（spec §1.3 / phase1 doc ## Scope ## In 線 18），不掃 pipelines；P1 acceptance #2-#5 不要求 pipelines 同步恢復；C6 reactor cycle 才是處理 pipelines 殘留 running 的場域（reactor recover_scan 啟動時掃 status='running' 找孤兒）。
- **#7 BuilderResult.tactic 在 exhausted 時都 None、caller 無法區分試了多少**：P1 cascade rule 不消費 BuilderResult.tactic（只看 outcome），P2+ failure_replay 走 dead_attempts 表查更乾淨。
- **#8 Staging 殘留檔**（exhausted 留 5 個 attempt_*.lean、proved 留 4 個）：phase1 acceptance 不顯式要求；`<p_uuid>` namespace 無覆蓋衝突；P3+ GC 自然處理。
- **#9 `_replace_proof_body` content 不含 `:=` 的 fail-soft**：P1 leaf strategy file 必有 theorem `:= by ...` 形式（acceptance #6 範例），fail-soft 安全；不會誤判 proved 因為 lake 對純定義無 theorem 的 .lean 不 emit hasSorry / error 但也不會 prove anything（無 sorry detection 觸發點、但本來就不該進這個分支）。
- **#10 status/outcome 雙重映射**（proved → succeeded、exhausted → failed）：spec architecture v3 §9.1 沒明定此映射；架 §6 cascade rule（pipeline_finished + outcome=proved → cascade target）只看 outcome 不看 status，pipelines.status 只是 enum {running, succeeded, failed}，現映射合理。

**驗證**：
- `pytest Tooling/tests/test_builder.py -v` → **16 passed**（14→16、+2 T_wall mid-loop / per-call clamp tests），0.38s
- `pytest Tooling/tests/` → **88 passed**（86→88、無 regression），0.56s
- `git diff --stat HEAD~1 HEAD` → `Tooling/pipelines/builder.py +21/-4` + `Tooling/tests/test_builder.py +58/-0` = 2 files / +79 / -4

**邊界**：未動 architecture / phase doc / spike doc / `Tooling/lake.py` / `Tooling/commit.py` / `Tooling/db/` / AutoDev；未引入新依賴（純 stdlib）。

**Caveat**：
- T_wall per-call clamp 後仍有理論上 race：lake 接受 `timeout=remaining` 後在 lake 內部從 `time.time()` 起算，加上 Python ↔ subprocess.Popen 啟動延遲（~50ms），實際 wall-clock 觸發點略晚於 `t_wall`。P1 acceptance #8 用 t_wall=2s + 慢 lake build 場景下，誤差級別 << 2s，無實質影響。
- `_commit_success` raise 後 `_finish_pipeline` 不執行的議題（#4 noted）：C6 reactor cycle 啟動時補上 pipelines.status='running' 的 orphan recovery scan。
- C5 R1 既有 caveat 仍適用：dead_attempts 直接 INSERT（P2+ failure_archive stage 接管）；proved case 的前置失敗 tactics 不寫 dead_attempts。

---

**C5 R1 — Builder runtime simplified (Tooling/pipelines/builder.py + unit tests)**

新增 3 個檔案，commit `a7e439f`：

- **Tooling/pipelines/__init__.py**：空 package marker
- **Tooling/pipelines/builder.py**：Builder 完整實作（~150 行）
  - `BuilderConfig(t_wall, lake_timeout, base_dir)`：config 注入，pytest 用 T_wall=2s
  - `BuilderResult(outcome, tactic, timed_out)`：pipeline 執行結果
  - `Builder(strategy_id, conn, config).run() → BuilderResult`：
    - INSERT pipelines row (status='running')
    - 讀 strategy.lean_path 原始內容 → `_replace_proof_body` 替換最後 `:=` 以後為 `by TACTIC`
    - tactic_try loop `[rfl, simp, decide, norm_num, ring]`：每試前檢查 T_wall；寫 staging .lean；呼叫 `run_lean`；proved 即停
    - proved → CommitWriter UPDATE（begin/stage_file/finalize），strategies.status='succeeded'
    - exhausted → INSERT dead_attempts（每個失敗 tactic 一 row，reason_summary 含 kind_hint 如 hasSorry）
    - UPDATE pipelines status/outcome/finished_at
    - INSERT events pipeline_finished
  - `_replace_proof_body(content, tactic)`：`str.rfind(":=")` 找最後 `:=`，替換後綴為 `by TACTIC`，處理 term/tactic proof body 都正確
  - dead_attempts 暫用直接 INSERT（P1 無 CommitWriter dead_attempts stage；P2+ 接 failure_archive stage）

- **Tooling/tests/test_builder.py**：14 unit tests
  - `TestTacticHit`（3 tests）：第 1 tactic pass / 第 2 tactic pass / staging 檔案內容驗 `:= by rfl`
  - `TestTacticExhausted`（3 tests）：5 tactics 全 fail → 5 dead_attempts rows；strategies.status 不變；pipelines.outcome=exhausted
  - `TestSorryDetection`（2 tests）：LakeResult(hasSorry) → exhausted；reason_summary 含 "hasSorry"
  - `TestTWall`（2 tests）：mock monotonic=[0.0, 10.0] 配 t_wall=2s → 強制 exhausted、no run_lean 呼叫；dead_attempts=0
  - `TestCommitSuccess`（4 tests）：strategies.status=succeeded + commit_state=live + snapshot=NULL；stage_file mv 驗 lean_path 內容為 `:= by rfl`；pipeline.outcome=proved；events pipeline_finished 寫入
  - lake/commit 全 mock（patch Tooling.pipelines.builder.run_lean）；file ops 走 tmp_path 真實執行

**設計決策**：
- proved case 的前置失敗 tactics 不寫 dead_attempts（dead_attempts 是 failure_replay source，僅全 exhausted 時才有意義）
- T_wall 在 tactic loop entry 前檢查（T_wall 到了但 staging file 還沒寫的 tactic 不算 dead）
- `_replace_proof_body` 用 `rfind(":=")` 而非 regex，處理 term-mode / tactic-block / 單行 proof 都正確；P1 demo file 格式安全

**驗證**：
- `pytest Tooling/tests/test_builder.py -v` → **14 passed**，0.35s
- `pytest Tooling/tests/ -v` → **86 passed**（72→86、+14 builder tests），0.53s，全 CI 迴歸 gate pass

**邊界**：未動 architecture / phase doc / lake.py / commit.py / schema_v1.sql / AutoDev；未引入新依賴（純 stdlib）。

**Caveat**：
- `dead_attempts` 直接 INSERT（CommitWriter dead_attempts path 未定；P2+ 接 failure_archive stage 時補）
- proved case 的前置失敗 tactics 不寫 dead_attempts——若 P2+ failure_replay 需要分析「pass 前試了什麼」，需擴此行為
- T_wall 只在每個 tactic loop entry 前做一次 wall-clock 檢查；run_lean 內部 timeout 靠 lake_timeout param 管——兩者分層獨立

---

**C4 R3 — Fix R2 audit findings (snapshot-restore test + tx style unify + design comment)**

R2 找到 5 fixable + 3 noted。5 fixable 全合理、逐一處理（commit `1268e93`）：

**Fixable（全修）**：

- **#1 UPDATE snapshot-restore branch 0 test 覆蓋**（真議題、phase1 acceptance #4 該守的）：原 `test_update_after_step1_restores_row` 的 fixture 寫了 strat_lean.write_text(...)，導致 lean_path 在 disk 上存在；recover_scan 走 `lean_exists → finalize` branch（不是 restore branch）。assert status==original 通過是因為 step 1 沒改 status + finalize 不帶 final_fields，**不是 restore 真跑了**。新增 `test_update_after_step1_restores_from_snapshot`（test_commit.py:233-280, ~50 行）：手動 INSERT live strategy → lean_path 指向 disk 上**不存在**的檔 → 直接 SQL 寫 commit_state='pending' + status='in_progress' + prior_state_snapshot json（含舊 status='proposed'）→ recover_scan → assert 走 restore branch（status 還原 'proposed'、commit_state='live'、snapshot=NULL）。
- **#2 docstring 與行為不符**（連動 #1）：原 test 改名 `test_update_after_step1_finalizes_via_lean_exists`，docstring 明示「step 1 crash 但 lean_path 已存在於 disk，recover 走 lean_exists branch（不是 restore-from-snapshot）；status 不變因 step 1 沒改 + finalize 帶空 final_fields」，避免讀者誤以為 snapshot-restore 已驗證。
- **#3 recover_scan lean_exists branch 不重跑 stage_file 的 design tradeoff**（加 inline comment）：spec §1.3 rule 1 字面寫「重跑 mv（idempotent）」但 schema 沒記 staging_path；recover 無從找原 src 來 hash compare。`Tooling/commit.py:240-249` 加 6 行 inline comment 解釋——`shutil.move`/`os.replace` 本身 atomic，dst-exists 蘊含 step 2 succeeded、直接 finalize 達同 terminal state；P2+ 若要嚴格 spec 字面 rerun mv 需擴 schema 加 staging_path 欄位。
- **#4 stage_file overwrite branch 0 test 覆蓋**（cosmetic）：新增 `test_overwrites_when_dst_exists_diff_hash`（test_commit.py:386-396, ~10 行）：src/dst 都存在但 hash 不同 → assert dst 被 src 內容覆蓋、src 被消耗。Windows `shutil.move` 走 `os.replace` atomic overwrite。
- **#5 begin vs begin_batch tx 風格不一致**（hygiene refactor）：原 `begin('insert')` / `begin('update')` 用 raw `self.conn.execute(...) + self.conn.commit()`、`begin_batch` 用 `with self.conn:`、`finalize` / `recover_scan` 也用 raw commit——三套風格混雜易誤導 P2+ 維護者。R3 全 4 個 entry point + recover_scan 三 branch 統一改用 `with self.conn:` context manager（commit.py:74-110, 199-211, 254-279）。fault hook 仍在 `with` block 之外 fire（保證 TX 已 commit 才 raise）。

**Noted（自行判斷不修）**：

- **#6 `_now()` 跨 step monotonicity**：begin / finalize 各 call 一次 _now()，系統時間倒退時 timestamp 會非單調。spec / DB schema / phase1 acceptance 都沒要求單調；P1 不修。
- **#7 finalize lean_exists branch 不重套 final_fields**：對齊 spec §1.3 rule 1（純設 live + 清 snapshot），devlog C4 R1 caveat 已標。impl 行為正確、無需修改。
- **#8 recover_scan 不掃 P5+ 表**：phase1 doc `## Scope ## In` 線 18 明列「掃 goals + strategies 兩表」，impl 對齊預期；continuous_tasks 走 lifecycle_state 不走 commit_state，是另一回事。

**驗證**：
- `pytest Tooling/tests/test_commit.py -v` → **19 passed**（17→19、+1 restore-branch + 1 overwrite），0.42s
- `pytest Tooling/tests/` → **72 passed**（70→72、無 regression），0.41s
- `git diff --stat HEAD~1 HEAD` → `Tooling/commit.py +31/-27` + `Tooling/tests/test_commit.py +75/-0` = 2 files / +106 / -27

**邊界**：未動 architecture / phase doc / spike doc / `Tooling/lake.py` / `Tooling/db/schema_v1.sql` / AutoDev；未引入新依賴（純 stdlib）。

**Caveat**：
- C4 R1 已標的 caveat 仍適用：recover_scan 從 step2 crash 恢復後不重套 pipeline-supplied final_fields（spec §1.3 一致）；UPDATE case 的 status 停在 begin 前原值，pipeline 重 dispatch 後才補全。
- Fault hook 在 `with` block 結束後才 fire（保證 TX 已 commit），與 R1 行為一致；測試 `test_fault_after_step1` 等 4 個 fault tests 全 pass 確認此語義。
- `with self.conn:` 在 sqlite3 default isolation_level 下 implicit BEGIN/COMMIT，P1 single-threaded 無問題；P3+ 多 thread 接 connection 時若需 explicit BEGIN 可再 refactor。

---

**C4 R1 — CommitWriter (Tooling/commit.py + unit tests)**

新增 2 個檔案，commit `6b33241`：

- **Tooling/commit.py**：CommitWriter 完整實作（impl §1）
  - `begin(table, op='insert'|'update', data, row_id)` — Step 1：INSERT 含 `commit_state='pending'` / UPDATE 現有 row 並 snapshot 進 `prior_state_snapshot`；TX commit 後 raise CommitFault（若 env 設定）
  - `stage_file(src, dst)` — Step 2：mv staging .lean → lean_path；idempotent（dst 存在且 src 不存在，或 hash 相同則 skip）
  - `finalize(table, row_id, final_fields)` — Step 3：UPDATE `commit_state='live'`、套用 final_fields、清 `prior_state_snapshot=NULL`
  - `begin_batch(ops)` — multi-row Step 1：多筆 INSERT/UPDATE 包在同一個 `with conn:` TX；COMMIT_FAULT 在整個 batch TX commit 後才 raise
  - `recover_scan()` — 掃 goals + strategies 兩表 `commit_state='pending'` row；lean_path 在 → finalize；lean_path 不在 + snapshot=NULL → DELETE；lean_path 不在 + snapshot 非 NULL → 從 snapshot 還原
  - `COMMIT_FAULT` env hook：`after_step1 | after_step2 | after_step3`，每個 step 之後 `_check_fault()` raise CommitFault；prod 不設 env var，零 overhead
  - `_TABLES_WITH_UPDATED_AT`：只有 goals 有 updated_at；strategies 無此欄位，動態構造 SET 子句時過濾

- **Tooling/tests/test_commit.py**：17 unit tests
  - **6 recovery 子 case**（INSERT × {after_step1, after_step2, after_step3} + UPDATE × 同）：
    - INSERT after_step1 → recover DELETE row
    - INSERT after_step2 → recover finalize (row=live, file stays)
    - INSERT after_step3 → recover no-op (row already live)
    - UPDATE after_step1 → recover restore from snapshot (status/commit_state 還原)
    - UPDATE after_step2 → recover finalize (row=live)
    - UPDATE after_step3 → recover no-op
  - **COMMIT_FAULT hook** 3 mode + 1 no-fault smoke
  - **begin_batch** 4 tests：兩 INSERT single TX、INSERT+UPDATE 混批、rollback on invalid id、COMMIT_FAULT after_step1
  - **stage_file** 3 tests：idempotent same content、move absent dst、skip when src gone

**驗證**：`pytest Tooling/tests/` → **70 passed**（53→70、+17 commit tests），0.41s，全 CI 迴歸 gate pass。

**Caveat**：
- recover_scan 當 lean_path 存在（step2 done）時，呼叫 `finalize(table, row_id, {})` 僅設 commit_state='live'、清 snapshot，不重新套用原始 final_fields（因 DB 未存 final_fields）。UPDATE 從 step2 crash 恢復後 status 停在 begin 前原值（e.g. 'in_progress' 不自動升 'succeeded'），pipeline 重跑才補全。此為 spec §1.3 定義行為（"UPDATE row 為 live、清 snapshot"）。
- begin_batch 使用 `with self.conn:` Python sqlite3 context manager（implicit BEGIN/COMMIT）；若外部呼叫方已在 transaction 中需確認隔離。P1 single-threaded 無影響。

---

**C3 R3 — Fix R2 audit findings (NOT NULL + UNIQUE + smoke + hygiene)**

R2 列 4 條 fixable + 4 條 noted。8 條全合理，逐一處理（commit `2563e61`）：

**Fixable（全修）**：

- **#1 `dead_attempts.pipeline_id` NOT NULL**（真 spec 偏離、1 行）：spec §9.1 dead_attempts.pipeline_id 無 nullable 標記；每筆 dead_attempt 都來自某個 pipeline run、NULL 是真 schema bug、非 P5+ 預留欄位。schema 改 `pipeline_id TEXT NOT NULL REFERENCES pipelines(id)`、加 `test_dead_attempts_pipeline_id_required` 反向斷言。
- **#2 `strategy_subgoals UNIQUE(strategy_id, position)`**（語義漏洞、1 行）：position 是 ordered AND-group，原 composite PK `(strategy_id, subgoal_id)` 不擋兩個不同 subgoal 都用 position=0。schema 加 `UNIQUE(strategy_id, position)`、加 `test_strategy_subgoals_position_unique_per_strategy` violation test。
- **#3 P5+/P6+ INSERT smoke**（測試覆蓋一次到位、3 個 test）：column count test 不 catch 欄位名拼錯漂移。加 `test_insert_continuous_task` / `test_insert_construction_attempt` / `test_insert_library_index` 三個 smoke test 確保未來 phase 啟用時欄位名正確。
- **#6 清 silent no-op PRAGMA**（hygiene、刪 2 行）：`executescript()` 內 `PRAGMA foreign_keys / journal_mode` 為 no-op、實際 FK / WAL 由 connect.py 每連線設。schema 開頭兩行 dead PRAGMA 刪除、改 SQL comment 說明 PRAGMA 的歸屬。

**Noted（自行判斷）**：

- **#4 events.kind 開放性**（建議 schema 註解）：採 R2 (a) 路。schema 在 events table 上加 SQL comment 明確「未來新 kind 需 schema_v2.sql」承擔代價、避免未來決策被遺忘。
- **#7 indexes 預建**（建議補或註解明示 deferred）：採註解路線。phase1 doc 沒明列 index 需求、SQLite 小表 table-scan 也快、且 P3 是 cache/query subsystem cycle、自然是補 index 的時機。schema 開頭 comment 標 `Indexes are deferred to P3 (cache/query subsystem cycle)`。
- **#5 `library_index.source_root_id` nullable**：採納 R2 evaluation 為 defensible（P6+ 才消費、可有非 root-derived entry），不修。
- **#8 fixture yield + close**（cosmetic、1 行）：修。`db()` fixture 改 `yield conn; conn.close()`。:memory: 當前無 leak、但未來改 file-based fixture 會洩 connection、低成本買保險。

**驗證**：`pytest Tooling/tests/` → **53 passed**（48→53、+5：1 NOT NULL + 1 UNIQUE position + 3 P5+/P6+ smoke），0.33s。

**邊界**：未動 architecture / phase doc / `Tooling/lake.py`；未引入新依賴；commit `2563e61` diff 集中在 `Tooling/db/schema_v1.sql` (+10/-3) + `Tooling/tests/test_schema.py` (+78/-1)。

**Caveat**：無已知未解決問題。schema_v1.sql 的 dead PRAGMA 已清；FK / WAL 由 connect.py 為每連線顯式設定。indexes 留 P3 補（schema comment 已明示 deferred）。events.kind 未來新增 kind 需 schema_v2.sql（schema comment 已明示代價）。

---

**C3 R1 — DB schema migration v1 (Tooling/db/)**

新增 4 個檔案，commit `1ef1035`：

- **Tooling/db/schema_v1.sql**：architecture v3 §9.1 全 13 table，一次建完。
  - SQLite enum 用 CHECK constraint 模擬（goals.origin/kind/status/commit_state、strategies.status/commit_state、pipelines.kind/runtime/target_kind/status、dead_attempts.target_kind/pipeline_kind、queue.kind、events.kind、continuous_tasks.lifecycle_state、library_index.layer）
  - 未用欄位全 nullable（全欄位策略：後續 phase 直接消費，無 ALTER TABLE migration）
  - P1 runtime 消費的 8 table（goals/strategies/strategy_subgoals/pipelines/dead_attempts/queue/events/schedulers）schema 完整；P5+ table（continuous_tasks/construction_attempts）、P6+ table（library_index）、P3+ table（search_cache）、P7+ table（strategist_decisions）schema 預建不消費
  - timestamp 統一 TEXT ISO8601、json 欄位統一 TEXT
  - strategy_subgoals / library_index 走 composite PK
  - pipelines.id 為 TEXT（UUID）；其餘 PK 為 INTEGER AUTOINCREMENT
- **Tooling/db/__init__.py**：空 package marker
- **Tooling/db/connect.py**：`connect(db_path) → conn`（WAL + FK ON）+ `init_schema(conn)`（讀 schema_v1.sql 並 executescript）
- **Tooling/tests/test_schema.py**：39 tests
  - 1 個：所有 13 table 存在
  - 13 個（parametrize）：各 table 欄位數對齊 spec（goals=21、strategies=9、strategy_subgoals=3、pipelines=10、dead_attempts=8、queue=6、events=4、schedulers=5、continuous_tasks=8、construction_attempts=7、library_index=5、search_cache=5、strategist_decisions=3）
  - 6 個：NOT NULL 守住（goals.problem/lean_path/status/commit_state、strategies.goal_id/lean_path）
  - 2 個：UNIQUE 守住（goals.lean_path、strategies.lean_path）
  - 2 個：composite PK 守住（strategy_subgoals、library_index）
  - 7 個：CHECK enum 拒絕非法值（goals.origin/kind/status/commit_state、pipelines.kind、events.kind、queue.kind）
  - 8 個：合法完整 row INSERT smoke（goals/pipelines/dead_attempts/queue/events/search_cache/strategist_decisions/schedulers）

**驗證**：`pytest Tooling/tests/` → 48 passed（39 新 + 9 既有 lake tests），0.31s。

**Caveat**：
- `executescript()` 在 `connect()` 之外執行，schema 的 PRAGMA 行（`PRAGMA foreign_keys = ON` 等）會被 executescript 跑但 executescript 預設 autocommit；`connect()` 已獨立再 execute PRAGMA，實際行為正確。
- SQLite 預設 FK 不強制；`connect()` 每次連線都執行 `PRAGMA foreign_keys = ON`，測試 DB fixture 已正確啟用。
- `strategies.created_by` FK 指 `pipelines(id)`（TEXT UUID），SQLite 宣告但不強制（未 PRAGMA FK）時可寫入不存在的 id；P1 runtime 自行保證順序（先 INSERT pipeline 再 INSERT strategy）。

---

**C2 R3 — Fix R2 audit findings (POSIX self-kill + cosmetic)**

R2 5 條意見全合理，逐一處理：

- **#1 POSIX self-kill bug**（真 bug、必修）：`subprocess.Popen` 缺 `start_new_session=True` → child 繼承 parent (Python interpreter) 的 pgid → POSIX timeout path 走 `os.killpg(getpgid(child), SIGKILL)` 會殺掉 Python interpreter 自己。R3 加 `start_new_session=True` 1 行修，並加 `test_popen_isolates_session` mock 斷言 Popen kwargs（即使 Windows-only 環境也驗）。lake.py:67。
- **#4 test fixture 命名與意圖不符**（cosmetic）：`test_simp_pass` 路徑改用 `spike003_sorry_nolib.lean`（subprocess 全 mock、路徑只是字串、純讀者觀感）。test_lake.py:65。
- **#2 POSIX 嚴格 tree-kill**（noted）：`os.killpg` 不真殺 grandchildren 若它們自己 setsid。在 `_kill_tree` docstring 加一行標註「P3+ 加 psutil 依賴時補嚴格 descendant kill」。當前 Windows-only 環境零影響。
- **#3 timeout buffered stdout 丟棄**（noted）：dead_attempts 寫 partial Lean 訊息留 P3+。不現修。
- **#5 real lake integration smoke test**（noted）：phase doc 沒要求、C8 demo 間接驗。不現修。

**驗證**：`pytest Tooling/tests/test_lake.py` → 9 passed (8 → 9 with new POSIX safety test), 0.23s。

Commit: `c33c00f`

**Caveat**：POSIX 嚴格 descendant tree-kill 弱於 Windows（已 docstring 標註、留 P3+ psutil 依賴時補）；timeout path 現仍丟 buffered stdout（dead_attempts 寫 diagnostic 時留 P3+ 補）。當前 Windows-only / P1 acceptance #8 範圍均不受影響。

---

**C2 R1 — Lake harness (Tooling/lake.py + unit tests)**

新增檔案：
- `Tooling/__init__.py`：空 init，讓 Tooling 成為 Python package
- `Tooling/lake.py`：lake harness 實作
  - `run_lean(lean_file, cwd, timeout=600.0) → LakeResult`
  - 呼叫 `lake env lean --json <file>`，用 `subprocess.Popen + communicate(timeout=...)`
  - stdout 解析 newline-delimited JSON（stderr 永遠空，spike-003）
  - 決策樹對齊 spike-003 D4：TimeoutExpired→exhausted、rc!=0→exhausted、kind=hasSorry→exhausted、else→proved
  - Windows process-tree kill：`taskkill /F /T /PID <pid>`（非 Windows 走 os.killpg）
- `Tooling/tests/test_lake.py`：8 unit tests（4 parse helper + 4 run_lean case）
  - `test_simp_pass`、`test_type_error`、`test_sorry_detected`、`test_timeout_kills_process_tree`
  - subprocess 全 mock，fixture .lean 路徑作 lean_file 參數但不實際 I/O
  - `pytest Tooling/tests/test_lake.py` → 8 passed, 0.34s
- `conftest.py`（project root）：`sys.path.insert(0, project_root)` 讓 pytest import `from Tooling.lake import ...` 正常

Commit: `6f4ab44`

**Caveat**：無已知問題。BUILD_LOCK 依 spike-001 確認不需要（P1 P=1 安全），未加。tests/ 無 `__init__.py` 以避免 pytest package import 衝突。

---

**C1 R3 — Fix R2 audit findings + merge 92bf533 precise data**

R2 audit 全 6 點意見合理，逐一修復（base = 9f6dc38；先前 R1 commit d04728f 已被 reset）：

- **#1 spike-001 cache invalidation 漏驗**：phase1_skeleton.md ## 風險 第 4 條明寫 spike-001 須順帶驗，原 R1 漏跑。R3 補做 1 檔 3 round 測試（PASS `1+1=2 by decide` → FAIL `1+1=3 by decide` → PASS），實測 rc1=0 / rc2=1 / rc3=0，確認 lake 依檔案內容重 elab。Builder `tactic_try` 同 staging 路徑反覆改寫策略安全，phase1_skeleton.md ## 風險 第 4 條解除。
- **#5 spike_temp/ 處置**：移至 `Tooling/tests/fixtures/spikes/`（24 個檔，含 .lean fixture + .py runner），runner 內 `SPIKE_DIR` 改 `os.path.dirname(os.path.abspath(__file__))` 可重定位，並 commit。Mathlib 升版後可直接重跑驗 axiom / error format 漂移。原 R1 寫「P1 結束後清除」破壞重現性。
- **同步 merge 92bf533 精確 spike 數據**（abandoned subprocess 跑出更精準結果）：
  - **spike-001 Mathlib 並發數據糾正**：cold-cache 跑法 concurrent **224.14s** vs sequential 63.24s = **3.54x 慢**（不是原 R1 寫的 2.81x faster）。原因：每 lean 程序載入全量 .olean → IO/記憶體競爭。warm-cache 跑法仍接近 sequential（21.86s）。**contingency 仍不觸發**（lake 並發無 lock 衝突 / 無資料損壞，非「無法並發」），但 P3+ Mathlib-importing 並發限 P=1–2。
  - **spike-002 trust set 路徑補驗**：新增 Classical.em / Finset.sum_comm / Multiset.card_add / Real.sqrt_nonneg → 確認 `[propext, Classical.choice, Quot.sound]` 三公理 whitelist 實務有效（原 R1 只跑 Nat/List/Int 沒驗 Classical 路徑）。
  - **spike-003 stdout 糾正**：所有 lean 輸出走 **stdout**、stderr 永遠空（原 R1 寫成 stderr 是錯的）。parser 只讀 stdout。
- **#2 D1 依據邏輯接錯**：依據改為 codex review #12 (a) 路的 ALTER TABLE migration CI gate 理由（spike 結果與 schema 設計無因果，原寫法錯接）。
- **#3 spike-002 trust set 描述過度延伸**：原稿「驗證」三公理設計 → 改為「Classical/Finset/Real 路徑實測落在三公理子集，whitelist 設計實務有效」（搭配 audit #5 補的 Classical 數據）。
- **#4 spike-003 Windows process-tree kill 備忘**：spike-003 §對設計的影響 + D4 加註「Windows `subprocess.run(timeout=...)` 預設只殺直接 child，孫程序 lean.exe 殘留 → C2 harness timeout path 必走 `taskkill /F /T` 或 `psutil` process-tree kill」。phase1_skeleton.md ## 風險 第 2 條對齊。
- **#6 解析決策樹文字微調**：明示「rc!=0 → exhausted」是 pipeline 層級判定，`tactic_try` 內部 loop 拿到 rc!=0 是「換下一 tactic」，避免 C5 實作時誤讀。

**Caveat**：無已知未解決問題。spike fixtures 已落 `Tooling/tests/fixtures/spikes/`，可重現性保留；C2 起 `Tooling/` 下加實作檔不衝突。

## 指令：無
