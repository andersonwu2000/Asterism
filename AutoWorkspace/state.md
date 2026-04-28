## Resume hint
你是 Asterism Orchestrator。auto-compact 後讀本檔 + `D:/Asterism/AutoWorkspace/task.md` → 從 ## Step 對應 round 繼續執行 `D:/Asterism/AutoDev/checklist.md`。**先讀下方 ## Orchestrator notes 取得實踐 lessons**。

## Orchestrator notes

跨 cycle 累積的 orchestrator-only lessons（不寫進 framework / phase doc，自我約束用）：

### Subprocess spawn 慣例
- **`claude -p ... < /dev/null 2>&1`**：必加 stdin redirect 跳過「Warning: no stdin data received in 3s」、必加 `2>&1` 確保 stderr 落 .output
- **model id 嚴格 sanity check**：用 task.md ## 模型 表的 id（claude-sonnet-4-6 / claude-opus-4-7）、不靠記憶
- **不能 abandon background bash subprocess**：必須 TaskStop 確認 process 真死、否則可能 25 min 後突然 commit 衝突
- **fresh session 不加 `--resume`**：`--session-id` + `--resume` 同用會 conflict；R3 resume 才用 `--resume <id>`、R1 fresh spawn 只用 `--session-id`
- **prompt 含 `<...>` `[...]` `$()` 等 Bash special char 必走 heredoc**：`PROMPT=$(cat <<'EOF' ... EOF) && claude -p "$PROMPT" ...`、避免 angle bracket 被 bash 當 redirect / `$()` 被 command substitution

### Monitor 設計
- **不靠 `ps aux` grep args 判存活**：Windows Git Bash 不顯示 process args、永遠 0 hit、誤判 EXECUTOR-PROCESS-EXITED
- **改用 file size 變動 / commit 變動 / output 變動判定**：可靠
- **OUTPUT-WRITTEN 過小（<500 bytes）≠ subprocess fail**：可能 silent success（work landed 但 stdout 沒 JSON）。先 `git log` + `git status` 比對、不要急著 retry

### Atomic transition
- **R4 cycle 終點 → R0 → R1 spawn 必須一次到位**：不能停在「口頭結束」、必須當場 spawn R1 subprocess 才算 cycle 推進完成
- **狀態更新與 spawn 同 turn 完成**：state.md update + claude -p spawn 應該連續執行、避免 user 干擾後忘記 spawn

### 32k single-turn output limit
- **大型 source file 寫入要 multi-turn 拆**：prompt 加註「拆 multi-turn、每 turn message text < 5k、source file 改動分批寫」
- **>600 行 Python file 是高風險 single-turn limit**

### Resume session
- **`--resume <session-id>`** 接 prompt 後 model 看到的是「累積 context + new prompt」：可在 prompt 加增量 context 即可、不需重述全範圍

### Git mess 處理（C1 範例）
- abandoned subprocess 25min 後 commit 衝突 → 用 `git reset --hard <good>` + `git checkout <bad-commit> -- <files>` recover untracked + 獨立 commit
- 整個 Asterism repo 是 fresh repo（C1 前無 commit）—— framework + spec 該獨立 commit、不混進 phase commit

## Step
**P6 ✅ done + P6.x patch series 24 patches** (latest `459525a`). Real runtime演習 round 1 (reverse_length) + round 2 (non_denumerable) drove patches 1-23 + 22-fix.

**P6.x patch series**（演習-driven、bug-first 修復、所有 patches inline orchestrator）：

| # | commit | 內容 |
|---|---|---|
| 1 | `38ae844` | cp950 stdout print fix + lakefile + lean-toolchain |
| 2 | `fe3ce4f` | subprocess utf-8 encoding (cp950 host) |
| - | `b2cb3a3` | gitignore演習 transient state + lake-manifest |
| 8/9/10 | `5097566` | dedupe.lean + validator.lean v4.30 toolchain drift + Backward observability |
| 7+11+14+15 | `d3de889` | check_scope baseline / fresh session_id / drop `--` separator / enableInitializersExecution |
| 3+5+17 | `4ca2fe3` | Backward Path A leaf-bypass / proved.lean format / per-Problem idempotency |
| 19 | `8f12f4d` | Builder verify-as-is for non-sorry source |
| 4+6+18 | `f26017a` | lake auto-build init / trust_set wiring / proved.lean imports |
| 21+22 | `994317b` | forbidden_lemmas blacklist + separate strategy file |
| 23+23-fix | `9fe1cc3` | two-phase commit goal file + skip lake build pre-step |
| 21.1 | `8b39732` | forbidden_lemmas glob `Cardinal.*` 支援 |
| ripple | `595a6f4` | tests update for new semantics |
| 22-fix | `459525a` | print_axioms theorem_name = goal.slug (not file stem) |
| docs | `279f84a` + `e155f96` | architecture_pipelines + impl §5.3.x + phase6_library forbidden_lemmas / two-phase commit |

CI: 905 pass / 35 skip / 1 xfailed / 0 regression（P6 closure baseline 維持）。

演習結果：
- **Round 1 reverse_length proved 全鏈** ✓ (real claude + real lake)
- **Round 2 non_denumerable proved 全鏈** ✓（無 forbidden_lemmas 時用 Cardinal 秒殺）
- **Round 3 non_denumerable + forbidden_lemmas blacklist** — 進行中（驗 forbidden 真擋下 Cardinal 秒殺）

**P7 預備留尚未測**（P7 不會自動解決、P7 上面是空中樓閣）：
- 非 leaf 拆分鏈完整端到端（Backward Path B → 真 subgoals → 各自 prove → 父合成）
- subgoal staging .lean Mathlib import 整合
- find_lemmas / 跨 goal 引用 proved sibling

**Paused per user request after C44 R3** (commit `74884cc`).

P5 progress: ✅ done (C34-C38, 5/5 cycles, 9 commits)

**P6 progress (8/9 cycles done; C47 N/A)**:
- C39 ✅ (`7c0d3cc` + `ab3a085`) spike-021/022/023/024
- C40 ✅ (`2aa36ec` + `2ccacfd`) Tooling/locks.py + schedulers liveness
- C41 ✅ (`001e262` + `8180a22` + `fb73a9a`) Library promotion + scheduler hook + R3 (3 HIGH + 4 MED 全修)
- C42 ✅ (`2ba93eb`) META.md scan_all_problems + Tooling/library/check_deps.py + tools/check_axiom_coverage.lean stub  **— R2 audit 未跑**
- C43 ✅ (`79e09cf`) cache invalidation library scope hook  **— R2 audit 未跑**
- C44 ✅ R1 (`b3e3c10`) CLI cluster + per-Problem pause daemon hook + R3 (`74884cc`) (3 HIGH + 4 MED — bypass semantics 反向實作 fix 為 no-op、audit stub exit 1、cmd_problem_list bare except narrow、HEARTBEAT_TTL_SEC=60→90 順帶修 C40 R3 silent regression)
- C45 ✅ R1 (`ad8df1a`) LIBRARY_BUILD_FAULT env hook (precedence 改 supersedes lake_verify) + Tooling/library/reindex.py + cli reindex 從 stub 升 real binding **— R2 audit 未跑**
- C46 ✅ R1 (`40085d7`) phase6 acceptance roll-up: AC#0a/0b/0c manual gates + AC#1-#11 in-process tests (multi-Problem BFS + library promotion + axiom coverage + revert via LIBRARY_BUILD_FAULT + reindex + whitelist filter + scheduler liveness + force-clear)
- C47 N/A (P5 Milestone A 延後使 `--statement` deprecated alias 從未引入；P6 收尾任務全併入 C46)

**P6 closure note**：C42/C43/C45/C46 R2 audit 缺漏（共 4 cycle）— R1 質量檢驗待 user 決議是否 retroactive。C44 R2 fresh Opus 跑完抓 3 HIGH + 4 MED + 3 LOW、R3 inline 修齊（其中 HIGH-1 是 acceptance 完全相反 semantics 新型違反）。

CI: P3 baseline 569 → **905 pass (+336) / 35 skipped / 1 xfailed / 0 regression**.

silent-failure 紅線連 24 cycle 監控（含 C44 抓 2 個變種：HIGH-2 audit stub silent-success + HIGH-3 cmd_problem_list bare except）。10 個 R1 變種（C20/C21/C24/C25/C29/C32/C36/C40/C44 R1×2）已被 R2 audit 抓到 R3 全修。

**C41 R2 + C44 R2 雙峰**（3 HIGH + 4 MED 兩 cycle 重複）— hybrid Opus R1 對大型 cycle (~870 net 行) 變種率高、orchestrator note candidate 「fresh Opus R3」第二次驗證、未升級 framework rule（C44 R3 hybrid inline 也成功）。

**Next on resume = P7 C48 (spike-025/026/027/028/029)**.

orchestrator note candidates（5 條待 user 決議）：
1. 「Executor R1 引 spec line/section 必 grep 驗」— C39/C40/C41/C44 連 4 cycle 重發、應升級 framework rule
2. 「commit 前 git show --stat HEAD 自驗 staged file」— C44 R1 守住、紅線連 24 cycle
3. 「hybrid Opus R1 對大型 cycle 變種率高、考慮 fresh Sonnet R3」— C41 + C44 雙峰驗證
4. 「auditor background subprocess 同 workdir 會 git stash my in-progress 改動」— C45 R1 半路被攔 → 教訓：parallel cycle R1 改動先 commit 再 spawn auditor、或用 worktree 隔離
5. 「test 鎖死 R1 錯誤行為」（test_bypass_clears_existing_rows pattern）— 寫 test 必先用 spec 字面驗 expected behavior、不可從 code 倒推 test

## P4 progress
**P4 6 cycles ✅ 全完成** — C28-C33、11 commits、CI 569→675 pass (+106) / 7→16 skipped (+9 manual + Counterexample-deferred) / 1 xfailed 維持、零 regression。

**P5 5 cycles ✅ 全完成** — C34-C38、9 commits、CI 675→768 pass (+93) / 16→30 skipped (+14 Milestone A deferred + manual gates) / 0 regression。Multi-provider Milestone B 完整：spike-019/020 + gemini provider + codex provider + multi-provider FallbackChain wire + PROVIDER_MOCK env hook + Milestone B acceptance test。Milestone A (ConstructionSearch / continuous runtime) 整段延後。

**P6 5/9 cycles ✅** — C39-C43。CI 768→834 pass (+66) / 30 skipped / 1 xfailed。
- C39 spike-021/022/023/024 (Library subdir build / Windows fcntl / cross-Problem import / theorem name resolution)
- C40 Tooling/locks.py SQLite advisory lock + schedulers liveness with HEARTBEAT_TTL_SEC=90 + heartbeat best-effort _emit_fatal
- C41 Library promotion (LIBRARY_WHITELIST framework-global + _resolve_lake_verify safety + first-write-wins file-no-append + per-Problem proved.lean + library_index INSERT + numeric-prefix warning)
- C42 META.md scan_all_problems + Tooling/library/check_deps.py + tools/check_axiom_coverage.lean stub
- C43 invalidate_for_library_write hook + scheduler hook calls into promotion

C44-C47 待 resume。

## Sessions
Auditor：94a43665-56c4-4b84-a925-a58c64b1ec6c (C44 R2 fresh Opus — running, audit_c44.md target)
Executor：（由 orchestrator 直接做、hybrid mode）

## P3 progress
P3.C19：✅ done（R1 commit 70d1c54 + 25882f0 = spike-008/009/010/011 results + fixtures：spike-008 IH-trap similarity 12 case fixture + Token Jaccard threshold=0.85 D-08-1；spike-009 isDefEq perf best-effort 估算 D-09-1 batch+timeout=30s；spike-010 search_cache hit rate best-effort 分析 D-10-1 TTL 確認；spike-011 SQLite json_patch atomicity 真跑 multiprocessing test D-11-1 不需 app-lock；R3 commit 3302cf4 = R2 audit MED-1/MED-2/LOW-3/LOW-4 4 項全修：spike-011 SQL guard bug 移除 / spike-009 placeholder URL 移除 / spike-008 case count 對齊 / spike-009+010 補 C27 補測時機；CI 420 pass + 2 skipped；**hybrid R1 spawn Sonnet（spike batch pattern）+ R3 由 Opus 直接做**）
P3.C20：✅ done（R1 commit 3b789dc + 91cf5af = dedupe.lean + search.lean + Tooling/subsystems/{dedupe,search}.py +1397 行：dedupe.lean Lean.Meta.isDefEq strict mode + iff_lite C20 stub / search.lean P3 stub 兩 scope 回 empty / Python wrapper 含 search_cache 整合 + DEDUPE_MOCK / SEARCH_MOCK env hook + silent-failure red lines 嚴格守 / 新 Tooling/subsystems package；R3 commit 72258af = R2 audit 2 HIGH 必修 + MED-3/MED-4/LOW-5/LOW-6 4 項全修：HIGH-1 dedupe.lean elab fail → NOVEL 對齊 §7.1 / HIGH-2 cache row mode='dedupe' 對齊 §2.3 C21 mutation hook 篩 / MED-3 search.py problem_scope 參數加入 hash key（schema column 缺為 P1 spec gap、orchestrator 決定 hash-only 防碰撞、P6 視需要 migration）/ MED-4 dedupe TTL 3600→1 年 對齊 §2.1 「不靠 TTL」/ LOW-5 +2 tests TestMockBypassesCache / LOW-6 timeout 不對稱 docstring；CI 420→456 pass + 3 skipped；**R1+R3 全由 orchestrator Opus inline 完成、hybrid mode formalized in commit 779091d；R2 R1 即清白首次（C11 後 6 cycle 全有 silent-failure regression、C20 R1 第一次無第七犯）**）

**MED-3 spec gap caveat (defer)**: search_cache schema column `problem_scope` 缺。orchestrator 決定走 (C) 接受 forward-compat 限定（C20 hash key 含 problem_scope、SQL 不 filter 直到 P6 真 multi-Problem）。3 選項：(A) amend schema_v1 違反「schema 一次到位」；(B) P6 補 migration；(C) 接受 forward-compat 限定 [當前]。User 之後可推翻。

P3.C21：✅ done（R1 commit 44e77dd = Cache mutation invalidation hooks +331 行：cache.py invalidate_for_goals_write + commit.py finalize hook + scheduler.py 3 site UPDATE hook + 10 tests；R3 commit 6b26e74 = R2 audit HIGH-1 必修 silent-failure 第 7 cycle regression（D_max try/except pass 內含 invalidate）+ HIGH-2 docstring TX accuracy + MED-1/MED-2/LOW-1 doc + import 整理 + propagation test；CI 456→467 pass 0 regression；**hybrid R1 Opus 仍漏 silent-failure 但 R2 Audit 抓到、第 7 cycle 證明 R2 獨立 review 不可省**）

## P3 done note

P3 9/9 cycles 全 ✅ 完成（19 commits、+149 tests over P2 baseline 420 → 569、+7 skipped manual gates、+1 xfailed P6 schema gap）：

- **C19 spike batch** (70d1c54 + 25882f0 + 3302cf4): spike-008 IH-trap similarity Token Jaccard threshold=0.85 D-08-1 / spike-009 isDefEq perf D-09-1 batch+timeout=30s / spike-010 search_cache hit rate D-10-1 TTL / spike-011 SQLite json_patch atomicity D-11-1 atomic SQL only
- **C20 cache subsystem** (3b789dc + 91cf5af + 72258af): tools/dedupe.lean (Lean.Meta.isDefEq) + tools/search.lean stubs + Tooling/subsystems/{dedupe,search}.py + DEDUPE_MOCK / SEARCH_MOCK + spec §7.1 NOVEL on elab fail
- **C21 cache invalidation** (44e77dd + 6b26e74): cache.py invalidate_for_goals_write + CommitWriter.finalize hook + scheduler 3 site UPDATE hook + propagation discipline
- **C22 stage接實** (ab5f0c1 + c7057b6): Tooling/stages/failure_replay + find_lemmas + find_subgoals + Backward/Builder delegation
- **C23 dedupe + IH-trap** (aaaa8fe + 4a63d1f): Backward._dedupe → dedupe.lean isDefEq via Tooling.subsystems.dedupe + Tooling/subsystems/similarity.py Token Jaccard + parent_subgoal_max_similarity 寫入 strategies row + cross-Problem entries filter
- **C24 blocked_pipelines** (f7baa73 + bba8f48): Tooling/subsystems/blocked_pipelines.py atomic SQL json_insert (per spike-011 D-11-1) + Tooling/stages/failure_archive.py archive_check + archive_ih_trap + scheduler BFS filter + cascade hooks
- **C25 in-memory cap removed + cascade.py + step1 liveness** (29958d3 + 248b588): _failure_count dict + helpers deleted / Tooling/cascade.py DISPATCH_TABLE wired into scheduler._run_step3_cascade / step1_stale_filter actually drops stale events (status check, not commit_state)
- **C26 CLI extensions** (488581a + 43e38d7): asterism goal unblock + goal add --spec-file + BACKWARD_FORCE=succeed
- **C27 P3 acceptance** (e98cd7f + b7b1dcf): test_phase3_acceptance.py 13 pass + 4 skipped manual gates covering AC #0a-#10

**P3 acceptance #0 sanity gate ✅** — test_phase3_acceptance.py 13 in-process AC tests pass; CI 569 pass / 7 skipped (manual gates) / 1 xfailed (P6 schema gap).

**Manual real-lake demo verification (P3→P4 transition gate)** — D1 (dedupe shared sub-Goal) + D2 (IH-trap auto-block) need real lake env + Mathlib + claude CLI. Status: pending. orchestrator 後續介入跑、結果回填本段。

**Hybrid mode 整體**: P3 全 9 cycles R1+R3 由 orchestrator (Opus 4.7) inline 完成；R2 every cycle spawn fresh Opus auditor。整體 silent-failure pattern 連 11 cycle 紅線觀察：5/9 cycles 在 R1 階段 R2 抓到 silent-failure 變種（C20 R1 elab_failed 偏 spec / C21 R1 D_max try/except pass / C24 R1 read-modify-write Python / C25 R1 step1 emit-no-action + commit_state 用錯欄位）；R3 全修。再次證明 R2 獨立 review 不可省、即便 R1 也是 Opus。

**Lessons → orchestrator notes (cumulative P1+P2+P3)**：
- silent-failure pattern 連 11 cycle 紅線觀察 — 即便 hybrid mode + Opus R1，R2 audit 獨立角度仍會抓到
- spec literal 字面對齊 critical — auditor 多次抓到「字面違反」（spec §7.1 elab_failed / §2.3 mode='dedupe' / §1 commit protocol commit_state 過濾 / spec #11 cascade dispatch 表「重構」）
- island module 警示 — C25 R1 cascade.py 0 production caller、user CLAUDE.md「不寫孤島模組」字面違反、R3 wire to step3_cascade 才修
- 大型 cycle 拆 R1+R3 + R2 audit 模式有效；hybrid mode 證明可承大型 cycle (C18 + C20 + C25 各 ~600+ LOC)

## P2 done note

P2 10/10 cycle 全 ✅ 完成（含 C16 folded into C15、共 19 commits）：

- C9 (spike-004/005/006/007 + a09d977) / C10 (provider 5923cee + e37921a) / C11 (validator 7b401ca + 7584071) / C12 (META + trust e93551a + d668e87) / C13 (Backward 8-stage a88a079 + f132d6e) / C14 (Builder agent 809b111 + 7fe9ee9) / C15 (Reactor daemon + cancellation 61b7dc7 + d49ed5d) / C17 (CLI daemon + asterism stop 40c978c + 340675c) / C18 (P2 demo + acceptance #0-#11 e587aa0 + e2503a5)

**P2 acceptance #0 sanity gate ✅** — `Tooling/tests/test_phase2_acceptance.py::TestAC0DemoSubprocess::test_demo_spec_to_proved` passes 端到端：`init → goal add --spec "∀ m n : Nat, m + n = n + m" → run --once → goal show G_root` 出 status=proved + classical answer_data。LAKE_MOCK + BACKWARD_MOCK + PRINT_AXIOMS_MOCK 走完 Backward → Builder → cascade → trust set 全鏈。

**Manual real-lake demo verification (P2→P3 transition gate)** — 對齊 P1 done note pattern：CI test 走 mock；真 lake env + real claude CLI 端到端為 orchestrator 介入跑、結果記到本段。**Status：未跑（pending P3 cycle 推進間插入；如 user 要求現在跑可優先處理）**。

**Hybrid mode**: C17 R3 + C18 R1+R3 全由 orchestrator Opus 4.7 直接做、未 spawn Sonnet Executor。Lessons: (1) Opus R1 品質高於 Sonnet 但仍會踩 silent-failure pattern (BACKWARD_MOCK fallback in C18 R1)；R2 Audit 獨立 review 不可省；(2) hybrid 可承 877/-58 大型 cycle (C18) — 規模不是限制；(3) sub-agent (Explore) 可保留 main context、適合 codebase 搜尋。

**Lessons → orchestrator notes** (cumulative across P1+P2): silent-failure pattern 5 cycle regression (C11/C12/C13/C15/C17 R1 + 即使 hybrid C18 R1 一處)；hybrid mode 推薦給 R1+R3 / spawn Sonnet 給超大 cycle (>1500 LOC) 或範圍規律機械作業；R2 Audit 永遠獨立 spawn Opus 不可省。

## P1 done note
P1 8/8 cycle 全 ✅ 完成（16 commits）+ **manual real-lake demo verification ✅ PASS**（orchestrator 趁 C9 跑時介入跑、cwd=D:/Hadamard 用真 lake env + Mathlib）：

```
$ cd D:/Hadamard && PYTHONPATH=/d/Asterism python -m Tooling.cli init --problem asterism_demo_p1
Initialized problem 'asterism_demo_p1'
  Problems\asterism_demo_p1\META.md / Defs.lean / Root.lean

$ python -m Tooling.cli goal add --problem asterism_demo_p1 --slug add_zero_simple --kind theorem --leaf-strategy /tmp/asterism_p1_demo_strat.lean
goal add: goal_id=1 slug='add_zero_simple' strategy_id=1
  queued Builder task for strategy 1

$ python -m Tooling.cli run --once
(silent run; reactor → Builder → tactic_try → simp pass → CommitWriter UPDATE)

$ python -m Tooling.cli goal show G_root
goal 1 (add_zero_simple)
  status:    proved          ← AC#0 sanity gate
  answer_data:
    type: classical          ← AC#0 字面要求
    lean_path: ...add_zero_simple.lean
  strategies (1):
    [1] status=succeeded commit_state=live
```

**P1 → P2 transition gate ✅ 齊備**。Demo artifacts (asterism.db / Problems/asterism_demo_p1/) 已清乾淨（D:/Hadamard 無污染）。caveat：trust_set 顯示 placeholder（P1 不跑 #print axioms、留 P2 trust 構造）。

## Phase progress
P1.C1：✅ done（spike + 首日決策 + 6 audit fixes；commits: d04728f / 9f6dc38 / 5d6749a）
P1.C2：✅ done（Lake harness + POSIX self-kill bug fix；commits: 6f4ab44 / c33c00f）
P1.C3：✅ done（DB schema v1 全 13 table + 4 audit fixes；commits: 1ef1035 / 2563e61）
P1.C4：✅ done（CommitWriter + recover_scan + 5 audit fixes；commits: 6b33241 / 1268e93）
P1.C5：✅ done（Builder runtime + tactic_try + T_wall per-call clamp；commits: a7e439f / f5a0091）
P1.C6：✅ done（Reactor 雛型 + 7 audit fixes；commits: 0fec0ea / 0f5394f）
P1.C7：✅ done（CLI 5 subcommand + critical pyproject build-backend fix + G_root alias；commits: ba7ed24 / ae6f87c）
P1.C8：✅ done（acceptance #0–#11 + CI + LAKE_MOCK hook + bugfixes + 6 R3 audit fixes；commits: 609f41c / af668be）
P2.C9：✅ done（spike-004/005/006/007 + docs/spikes.md；commits: 7d15da9 / a09d977）
P2.C10：✅ done（Provider 抽象 + claude 實作 + ModelResolver + FallbackChain；commits: 5923cee / e37921a）
P2.C11：✅ done（Validator hypothesis carry + SQL UNIQUE + max_subgoals；commits: 7b401ca / 7584071；R3 major rework 移除 regex parse Lean）
P2.C12：✅ done（META.md parser + Trust set 構造 + #print axioms wrapper；commits: e93551a / d668e87）
P2.C13：✅ done（Backward pipeline runtime 8-stage + junction TX 修正；commits: a88a079 / f132d6e）
P2.C14：✅ done（R1 commit 809b111 = Builder agent 升級 failure_replay+tactic_llm+self_verify extract；R3 commit 7fe9ee9 = R2 audit 7 fixable 全修：HIGH #1 prompt by collision dual-fix、MEDIUM #2 dead_attempts 三 path 補寫、MEDIUM #3 pipelines.session_id parity、MEDIUM #4 scope_dirs 含 problem_dir、LOW #5 _record_bad_goal TX 合併、LOW #6 inline 註解、LOW #7 dead_attempts per-iter refresh；+8 tests / 350 passed; auto-compact 中斷後 fresh session 接手完成）
P2.C15：✅ done（R1 commit 61b7dc7 = Reactor 升級 daemon + 4-event dispatch + atomic pool + BFS refill +1196/-47；R3 commit d49ed5d = R2 audit 5 必修 + 5 建議全修：HIGH-1 thread fatal silent / HIGH-2 accept reject silent / MED-1 print_axioms silent fallback —— 三條 silent-failure regression 全嚴格修；MED-2 BFS commit_state='live' filter；MED-3 docstring；LOW-1/2 unknown event 診斷；CI 384→390 pass 0 regression）
P2.C16：✅ folded into C15（task.md C16 = Cancellation 簡化 + In-memory retry cap stop-gap；C15 R1 absorbed：_cancel_running_for_goal scheduler.py:546 + _failure_count dict scheduler.py:74-75 + N_block_after_failures=5；P2 thread pool 不能 SIGTERM 為 documented MED-3 compromise，P3 step1_stale_filter 真實接手）
P2.C17：✅ done（R1 commit 40c978c = CLI daemon mode +305/-26：`asterism run` 預設 daemon + `asterism stop` via DB events table IPC + schedulers table register/unregister + 5s response cap + source='cli' filter；R3 commit 340675c = R2 audit 5 必修全修：HIGH-1 --daemon forward-compat alias 加回 / HIGH-2 _poll_db_control_signals 改 emit fatal / HIGH-3 _register_scheduler 改 fail-shut / MED-1 _unregister_scheduler 收窄 except / MED-2 +7 tests；CI 399→406 pass；**R3 由 orchestrator Opus 直接做、hybrid mode 試點啟用**）
P2.C18：✅ done（R1 commit e587aa0 = P2 demo + 12 acceptance tests +877/-58；R3 commit e2503a5 = R2 audit 3 HIGH 全修：HIGH-1 BACKWARD_MOCK silent fallback 改 raise ValueError / HIGH-2 docs/dev/test_hooks.md 註冊 BACKWARD_MOCK + BACKWARD_FORCE / HIGH-3 BACKWARD_MOCK + BACKWARD_FORCE 拆分依 naming convention；MED-4/5/6 + LOW-7/8 文檔化 skip；CI 420 pass + 2 manual gate skipped；**R1+R3 由 orchestrator Opus 直接做、hybrid mode 第二 cycle 證明可承大型 cycle 但 R2 audit 獨立 review 仍不可省（hybrid R1 仍 miss silent-fallback）**）

## Blockers
無

## Summary

**C1 — spike-001/002/003 + 首日決策 + 6 audit fixes**（3 commits）

Round 軌跡：
- R1 Executor (3 attempts、最終 commit `d04728f`): 跑通 spike-001/002/003、寫 docs/spikes.md + 首日決策 D1-D4。第 1 次 model id 拼錯 / 第 2 次 silent exit 被 abandon 但實際在後台跑 25min（造成後續 git mess）
- R2 Auditor (`9674a3b5`、opus 4.7): 找出 6 issues——spike-001 漏驗 cache invalidation、D1 依據邏輯不接、spike-002 過度延伸、spike-003 stdout 寫成 stderr / Windows process-tree kill 漏寫、spike_temp 應移 fixtures 不該刪、決策樹文字微調
- **Git mess** (orchestrator 介入): abandoned subprocess 25 min 後 commit `92bf533`（含 framework + spec 4426 行 + spike-001 更精準的 IO 競爭數據）、跟 d04728f 衝突。User 授權 `git reset --hard d04728f` + `git checkout 92bf533 -- AutoDev/ docs/architecture/ docs/dev/ .gitignore` + 獨立 commit `9f6dc38` (framework + spec import)。92bf533 留 reflog HEAD@{2}
- R3 Executor (resume `d623d80e`、commit `5d6749a`): 修 6 audit issues、補做 spike-001 cache invalidation 測試（PASS-FAIL-PASS 3 round 確認 lake re-elab）、合併 92bf533 IO 競爭數據（concurrent Mathlib cold-cache 224s vs sequential 63s = 3.54x 慢、warm-cache OK）、spike-002 補 Classical/Finset/Real 路徑、spike-003 stdout 糾正 + Windows process-tree kill 備忘、spike_temp/ 移 Tooling/tests/fixtures/spikes/ 並 commit

**Orchestration lessons**（已修進 framework / 自我約束）：
1. Background bash subprocess 不能用 `ps aux` grep args 判存活（Windows Git Bash 不顯示 args）→ Monitor 改用 file size / commit / output 變動判定
2. Background subprocess 必須 `2>&1` 確保 stderr 落 .output
3. Monitor timeout / file 0 bytes ≠ subprocess 死亡——必須 TaskStop 確認
4. Spawn subprocess 後不能 abandon——若 Monitor 誤判 exit、必須先 TaskStop 才能棄用 session
5. Model id 嚴格 sanity check（用 task.md ## 模型 表的 id、不靠記憶）

**P1 進度**：1/8 cycle done。下個 C2 = Lake harness（依 spike-003 走 `--json` mode + Windows process-tree kill；P1 P=1 不需 BUILD_LOCK）。
