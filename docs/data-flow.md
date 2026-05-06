# Asterism — 資料流向

寫於 2026-05-06。靜態形狀（角色、規則、不變量）見 `docs/architecture.md`；本檔講動態：dispatcher 一輪 tick 內外資料怎麼跑、各 pipeline 完整流程含失敗模式、跨 pipeline 共用的機制。

---

## 1. 三層儲存

| 層 | 位置 | 壽命 | 用途 |
|---|---|---|---|
| **暫存** | `.attempts/<pipeline_id>/` | 一次 spawn | agent 當下讀寫的工作目錄；spawn 結束 unconditional rmtree |
| **跨 spawn** | `Problems/<p>/.drafts/<kind>_g<gid>.md` | 該 goal 證完前 | 上次 timeout 後 agent 留下的進度筆記 |
| **永久** | DB + `Problems/<p>/proofs/L_*.lean` + `_strategy_s*.lean` + `Root.lean` | 與 problem 同壽 | 真實狀態的單一來源 |

設計理由：暫存隨 spawn 拋掉、保證每次乾淨起手；跨 spawn 層只放需要傳給下次的東西；永久層就是 DB + Lean 檔。

agent 寫進 `.attempts/<pid>/` 的所有東西（成敗與否）在 dir 被 rmtree 之前先打包進 `dead_attempts.artifacts` JSON，DB 永遠是 SoT。

---

## 2. 一輪 dispatcher tick

主迴圈每輪做五件事，順序固定。每個 stage 短說明資料怎麼動、深入的展開連結到後章。

```
1. cascade            — 收割上一輪完成的 worker outcome、更新 goal/strategy 狀態
2. verify housekeeping — 撈所有 sub-goal 全 proved 的 strategy 組裝、寫 alias 進 parent
3. root_proved? exit  — 若 root proved → reconcile + prune + library promote、退出
4. bfs_refill         — 把 open goal 排進 queue
5. spawn              — 有空格就從 queue 拉、spawn pipeline
```

**Stage 1 — cascade**：worker thread 完成後 INSERT 一個 finished pipeline row，主執行緒讀 outcome、套狀態轉移（Builder proved → goal proved；Backward success → goal attempting；任一失敗 → attempts++ → 到 SHELVE_THRESHOLD 就 shelved 並上拋）。完整規則在 architecture.md §7。**worker thread 絕不直接改 goal/strategy 狀態**，這條紀律消除整類 OR-race。

**Stage 2 — verify housekeeping**：純框架、無 LLM、單執行緒、可能遞迴連帶多層。詳解 §4。

**Stage 3 — root proved exit**：root goal 進入 proved 後跑三件事 — `prune.reconcile_proved_goals`（修 OR-race 留下的 file/DB drift）→ `prune.prune_problem`（GC orphan 檔）→ `library.maybe_promote`（axiom-gated 的話 promote 進 `Library/<Topic>/`），然後 dispatcher 退出。

**Stage 4 — bfs_refill**：對 open goal 走 recursive CTE 過濾掉 dead/superseded 分支下的 orphan、剩下的依 `entry_kind`（Manifest 寫的或 Backward agent 標的、attempts ≥ BUILDER_THRESHOLD 強制升 Backward）排進 queue。每個 (target_id, kind) 同時最多一條 in-flight（passive OR cap=1）。

**Stage 5 — spawn**：從 queue 拉一個、用 `ThreadPoolExecutor.submit` 派一條 pipeline 進 worker thread。pipeline 內部 flow 是 §3 主題。

---

## 3. Pipeline flows

### 3.0 共同骨架

每條 pipeline spawn 都經歷同樣三段：

```
框架側準備：
  - 從 DB 編 Context.md、放進 .attempts/<pid>/
  - 預寫框架要鎖的檔（Backward 預寫 patch.lean skeleton；Builder 不需要）
  - 若 .drafts/ 有上次 timeout 留的進度筆記 → 併入 Context.md
  ↓
Spawn agent：
  - 第一次 dispatch：mint UUID 當 session_id、claude --session-id <uuid>
  - 之後的 dispatch（warm retry）：claude --resume <同個 sid> + 短 prompt 帶上次 lake error
  - cwd = Problems/<p>/（F44 sandbox）
  ↓
框架側收尾：
  - 驗 agent 寫的東西（forbidden lemma、檔名規範、簽名鎖）
  - 把檔案搬進永久路徑（Problems/<p>/proofs/）
  - lake build 確認組裝合法
  - INSERT DB rows
  - 刪 .attempts/<pid>/、清 .drafts/（成功的話）
```

成功 / 普通失敗 / timeout / spawn fast-fail 四種終結，框架對每種有不同的 session 與 .drafts 處理（§6）。

### 3.1 Builder

對 fresh sorry-stub goal 嘗試直接 closure。兩個 phase。

**Phase 1 — `tactic_try` via Mathlib `hint`（無 agent、純 script）**

觸發條件：`goal.attempts == 0` AND parent lean 檔結尾是 `:= by sorry`（regex `_is_sorry_stub`、保護結構化 patch 不被誤觸）。

兩階段流程：
- (1) **Probe**：把 sorry body 替換成 `by hint`、跑 lake build。Lean elaborator 跑所有 mathlib `register_hint` 過的 tactic（24+ 條，含 trivial / decide / norm_num / omega / linarith / aesop / exact? / ring / positivity / ...，priority desc 排序），對每個閉合 goal 的 tactic emit `info: ... Try these: [apply] 🎉️ <tac>`、用第一個作 proof。全失敗 → `error: No suggestions available`、ok=False。
- (2) **Confirm**：parse `🎉️` 標記抓出 winner、把 sorry body 重寫成 `by <winner>`、再跑一次 lake build。`hint` 跑在 shared mctx、isolated 重 elaborate 理論上可能 diverge（實際罕見）；第二次 build 確認精確 tactic 真的 work、且 patch 檔內留下具名 tactic 而非 opaque `hint` 區塊（forensic + source clarity）。

過 → patch 檔內是 `:= by <winner>`、outcome `proved`、artifact 留 `won_hint.lean` snapshot。
不過 → 還原 sorry stub、進 Phase 2。

歷史補充：早期實作對每個 tactic 跑獨立 lake build（13 次 × 5-15s startup）；中期改 `by first | ...` 單一 build；現在 `by hint` + 寫回精確 winner — 把 mathlib curated 的 `register_hint` 集合直接接過來、不再維護 framework 自己的 tactic list。

**Phase 2 — `tactic_llm`（spawn agent）**

```
1. 編 Context.md（kind='builder'）
2. spawn claude（cwd=Problems/<p>/、--session-id <uuid>）
3. agent 寫 PROPOSAL.md + patch.lean（body 改寫 sorry）
4. forbidden_lemmas grep
5. backup parent.lean → 套 patch → lake build
6. 過：留 patch、outcome 'proved'
   不過：還原 backup、record dead_attempt(reason='lake_build_error')、outcome 'failed'
```

**Builder 失敗模式**：Phase 1 hint 失敗（全 register_hint 沒 winner / winner confirm rebuild 不過）**fall-through Phase 2 LLM 同次 dispatch 跑完**、不獨立成 outcome。Phase 2 視 rc / agent 行為走 `lake_build_error` / `forbidden_lemma` / `agent_declined` (F48) / `agent_infeasible` / `agent_no_output` (rc=0 但無 patch) / `agent_rc_nonzero` / `agent_timeout` (rc=124、額外跑 F55 postmortem) / `spawn_fast_fail` (rc≠0 wall<10s)。

cascade 對 Builder 的狀態轉移：proved → goal proved；failed → attempts++、過 SHELVE_THRESHOLD 就 shelved 並 `_propagate_shelve` 上拋（除 `agent_infeasible` 直接 shelved 不增 attempts、`spawn_fast_fail` 也不增）。

完整 reason × 觸發 × session 處理 × cascade × event 投影對照表 → `docs/failure_modes.md` §2。

### 3.2 Backward

對 goal 拆出一條 Strategy + N 個 sub-goal。OR-aware：每條 strategy 用 strategy-isolated 檔名（`_strategy_s<sid>.lean` + sub-goal slug 含 `s<sid>_` 前綴）、parent 的 lean_path **不被 Backward 改動**、留待 Verify 勝出時改寫。

**完整 flow**：

```
1. F53 同 session retry 判斷：
   sid = db.get_backward_session_id(goal_id)
   is_retry = sid is not None
   若 retry：拿舊 dead strategy 的 id 重用（F53/A，避免 agent session memory 用 stale slug）
            清 strategy_subgoals 的舊 link、把 strategy 重置回 'proposed'
   若 cold：INSERT 新 strategy 拿 fresh sid

2. 準備 Context.md：
   cold start → 完整編 Context.md（含 ## Strategy naming：sid 鎖死 sub-goal slug 前綴）
   warm retry → 不重編、改 fetch 上次 lake stderr 當 retry_context 注入 prompt

3. F52 預寫 patch.lean skeleton：
   把 parent stub 的 `theorem <slug> <binders> : <type>` 簽名複製、改名 sX、body=sorry
   agent 只能改 body；任何簽名邊動會被 _signature_prefix diff 抓到

4. spawn claude（cwd=Problems/<p>/、第一次 --session-id、重試 --resume）

5. 驗 agent 輸出：
   - PROPOSAL.md 必存在
   - patch_*.lean + new_*.lean 必存在（缺則 parse_proposal_fail；若 PROPOSAL 標
     decline_reason=parent_type_infeasible → agent_infeasible）
   - forbidden_lemmas grep 全文件
   - patch.lean 簽名沒被改（normalize whitespace 後比對 skeleton）
   - 每個 sub-goal 檔名 = `new_s<sid>_sub_<N>.lean`（不符 → naming_violation）

6. dedupe：
   對每個 candidate sub-goal、batch 呼叫 Lean kernel isDefEq 比對候選池：
     (a) 嚴格 ancestor chain
     (b) 同 parent 的 orphan-proved sub-goal（cross-strategy 重用，F42）
     (c) 跨 branch 的任何 proved goal（commit 865655d）
   命中候選 → 寫 alias 檔 `:= by apply <c.slug> <;> assumption`、不 INSERT 新 goal、
   strategy_subgoals 直接 link 到 canonical
   單一 lake-env 子進程跑完所有 pair；解 statement / kernel error → fail-open（走 non-dedupe）

7. 把檔案搬到永久路徑：
   - sub-goals: Problems/<p>/proofs/L_<slug>.lean
   - scratch:   Problems/<p>/proofs/_strategy_s<sid>.lean

8. lake build batch（sub-goals 含 sorry stubs + scratch 一起、確認組裝合法）

9. 過：UPDATE strategy.scratch_path + proposal_md + status='proposed'
        對非 dedupe 的 sub-goal INSERT goals + strategy_subgoals
        outcome='success'、session 清掉（strategy 已 commit、不需要 retry）
   不過：unlink 此 strategy 寫進的所有檔、strategy='dead'、_abort
```

**特殊 placement (item 7 SG 教訓)**：agent 偶爾把整段 valid proof 寫進 `new_*.lean` 而不是留 sorry stub。framework 偵測到 sorry-free + axioms 在白名單就直接把該 sub-goal mark proved、跳過後續 Backward dispatch（`_try_promote_sorry_free`）。

**Backward 失敗模式**：步驟 5 結構驗證走 `parse_proposal_fail` / `forbidden_lemma` / `patch_signature_mismatch` (F52) / `naming_violation`；步驟 8 走 `lake_build_error`；spawn 層走 `agent_rc_nonzero` / `agent_timeout` (額外 postmortem) / `agent_infeasible` / `spawn_fast_fail`。Backward **沒有 declined channel**（agent 想退出走 `agent_infeasible` 含反例）、也**沒有 `agent_no_output`**（agent rc=0 但少檔走 `parse_proposal_fail`）。

cascade 對 Backward 的狀態轉移：success → goal `attempting`（**還沒 proved**、等 Verify）；其他 → attempts++、過 SHELVE_THRESHOLD 就 shelved + `_propagate_shelve` 上拋（同樣的 `agent_infeasible` / `spawn_fast_fail` 例外）。

完整對照 → `docs/failure_modes.md` §2。

---

## 4. Verify housekeeping

每輪 dispatcher tick 在 cascade 之後跑、純框架、無 LLM。

它的工作：把 sub-goal 全 proved 的 strategy 組裝編譯、把 parent goal 的 sorry stub 改寫成「我用這條 strategy 證的」。

```
loop（最多 max_iters=8 圈）:
  ready = strategies_ready_for_verify(DB)
        — 過濾條件：strategy 'proposed' AND 所有 sub-goal 'proved' AND parent goal 不是 'proved'
  若 ready 為空 → break
  
  對每條 strategy s（序列、單執行緒）:
    Step 1: lake build _strategy_s<sid>.lean
            （組裝 patch、import 各 sub-goal proofs）
    Step 2: 把 parent goal 的 .lean 檔改寫成 alias（atomic os.replace）：
              import Problems.<p>.proofs._strategy_s<sid>
              namespace Problems.<p>
              def <parent_slug> := @Problems.<p>.s<sid>
            F52 簽名鎖死保證 alias 的 type 跟 parent 完全相符
    Step 3: lake build alias-form parent
    
    全過 → strategy='succeeded'、parent goal='proved'
            sibling strategies 標 'superseded'、F22 playbook hook
            鏈式：parent goal 可能是更上層 strategy 的 sub-goal、下一圈會撈到
    任一壞 → backup 還原 parent、strategy='dead'
            cascade 處理（attempts++、SHELVE 處理、_propagate_shelve 上拋）
```

**為什麼是 stage 而非 worker_kind**：純框架操作沒 LLM、不該佔 worker pool slot。早期版本（pre-F56）把 Verify 當第三種 worker_kind、每輪佔一個 ThreadPool 格子 ~60s、無收益。

**為什麼遞迴 max_iters=8**：深度 4 的題可能一輪 sweep 連帶 4 層 strategy 全部 promote；上限避免病態 case 卡住整個 tick。

**為什麼單執行緒**：housekeeping 在主迴圈 sequential 跑、自然解掉 OR-race（過去 P0-#1 的 `busy_parents` 已不需要）。

**為什麼沒有 LLM 修復**：早期 F41 設計過「Step 1 失敗叫 LLM 修一次 patch」。實證 26 次 verify 0 觸發 — F52（鎖死 strategy 簽名）+ Backward commit 前先 build 過 sorry-stub 已過濾掉絕大部分組裝錯誤。再加 LLM 修復是為極罕見事件付架構成本。Step 1 真的開始失敗才回頭加。

---

## 5. Spawn 前準備

**Context.md 編譯**：每次 spawn 前框架從 DB 編一份 `Context.md` 寫進 `.attempts/<pid>/`。**agent 看到的所有訊息都從這裡來**（companion file 是備援、agent 經常不會主動讀）。Sections 順序固定、每個 `_section_*` 不適用時回 `[]`：

```
Goal statement
Sandbox                         ← 讀寫權限邊界 + 預寫檔名約定
Strategy naming                 ← Backward only：sid 鎖死 sub-goal slug 前綴
Parent goal & strategy          ← origin='backward' only：parent statement + parent strategy proposal_md 截斷
Mathlib hints
FORBIDDEN_LEMMAS
Strategic notes
Library available
Playbook
Builder declines                ← Backward only：上次 Builder agent_declined 的 PROPOSAL 摘要（step 4 將合進 Goal history）
Your previous progress note     ← F55 timeout 留下的進度筆記（§6）
Goal history (umbrella)         ← v1 已落地、4 sub-section：
  ### Direct attempts on this goal
  ### Sibling decompositions that failed Verify
  ### Strategies whose decomposition died
  ### Sub-goals reported infeasible
```

`Goal history` umbrella 的 event 投影邏輯在 `Tooling/pipeline/events.py`（5 個函數 + `_NON_AGENT_REASONS` filter）。Empty bucket 整段省略；空 umbrella 連 `## Goal history` header 都不寫。完整設計與 audience 規則見 `docs/dev/goal_history_unified.md`。

**Sandbox**（F44 + M1 + M3）：
- cwd = `Problems/<p>/`
- claude `--add-dir` 列：problem_dir、attempts_dir、`.lake/packages/`
- 讀允許：cwd subtree、`.lake/packages/mathlib/Mathlib/`
- 讀禁止：其他 `Problems/<...>/`（agent 想看別的 problem 的 sketch 也擋）
- agent 工具：Read / Write / Edit / Grep / Bash + `python -m Tooling.loogle *`（Mathlib lemma 搜尋 wrapper）

**預寫框架要鎖的檔**：
- Builder：不預寫，agent 自由改 `patch.lean`（其實是 parent goal 的 lean 檔）
- Backward：F52 預寫 `patch.lean` skeleton — copy parent stub 的 `theorem <slug> <binders> : <type>` 簽名、改名 `theorem s<sid>`、body 留 sorry。agent 只改 body、簽名邊動會被偵測

---

## 6. Spawn 後的失敗 / 中斷處理

`agent.spawn_llm` 結束後 framework 看 rc 分四條路：成功（rc=0）/ 普通失敗 / timeout（rc=124）/ spawn fast-fail（rc≠0 且 wall-clock < 10s）。三種失敗的 session 與 `.drafts/` 處理不同。

### 6.1 普通失敗（rc≠0、wall-clock ≥ 10s）

例：lake build 沒過、agent 引用不存在的 lemma、forbidden_lemma 命中。

```
1. 把 .attempts/ 裡的檔全部打包進 dead_attempts.artifacts JSON
2. 抽 lake stderr / parse error 進 dead_attempts.failure_detail
3. 保留 session_id（claude session 還在 disk、--resume 還能拉）
4. 對 Backward：strategy 標 'dead'、unlink 寫進的 proofs/ 檔
5. 對 Builder：parent.lean 的 backup 已還原（lake build 失敗時 framework 已 restore）
6. cascade：attempts++、過 SHELVE 就 shelved
```

下次 dispatch（warm retry）：
```
sid 在 DB 還在 → is_retry=True
fetch 同 goal 上次 dead_attempt 的 failure_detail（lake stderr 等）→ retry_context
spawn claude --resume <sid> + retry_context inline 進 prompt
agent session 記憶接得上、看到「上次的 lake error 是 X」直接改
```

普通失敗不需要持久化任何 partial 內容（不寫 `.drafts/`），session 記憶是足夠的接續媒介。

### 6.2 Timeout（rc=124、process 被 SIGKILL）— F55 postmortem

主 spawn 超過 600s（`WORKER_TIMEOUT_SEC`）被 SIGKILL。session memory 還在（pinned 在 disk），但 process 已死、沒機會把當下思考寫成檔。

```
1. 主 spawn timeout、SIGKILL
2. 框架立刻發第二次 spawn（同一個 _run_pipeline 內、sid 還沒清）：
   claude --resume <sid> + 短 prompt（Tooling/prompts/<kind>_postmortem.md）：
     「你被中斷了、用 150 字寫下你的方向、卡在哪裡，存進 _progress.md」
   限時 180s（POSTMORTEM_TIMEOUT_SEC）
3. agent 用 session 記憶寫 .attempts/<pid>/_progress.md
4. 框架把 _progress.md 複製到 Problems/<p>/.drafts/<kind>_g<gid>.md（持久層）
5. attempts dir 接著被刪（WorkArea.__exit__）
6. 清 DB 的 session_id（標記 sid 已 retire）
7. cascade：attempts++、過 SHELVE 就 shelved
```

下次 dispatch（cold start，session_id 已清）：
```
編 Context.md 時讀 .drafts/<kind>_g<gid>.md
inline 成「## Your previous progress note」section
agent 看到自己的回顧筆記、繼續做（fresh session）
```

**為什麼不直接讓 agent 邊想邊存 PROPOSAL.md**（早期 F55 設計）：agent 同時思考又要維護 deliverable、注意力分裂、容易過早承諾分解方向。改成事後 postmortem 把 deliverable 跟思考紀錄解耦。

**postmortem 自己也死怎麼辦**：180s cap + 任何 rc≠0 都當 best-effort 失敗（next spawn 直接 cold start、不比沒 F55 差）。

`.drafts/` 在下次 spawn 成功 commit 時自動清掉（pipeline 成功就沒理由再保留進度筆記）。

### 6.3 Spawn fast-fail（rc≠0 且 wall-clock < 10s）— F46

real claude.exe 啟動 ~3-5s、最快的 legitimate 失敗（patch 結構錯）也至少要一個 model turn。低於 10s 的 rc≠0 幾乎肯定是 infra 故障：claude.exe crash、cwd 失效、quota cut、network down。

```
1. failure_reason 標 'spawn_fast_fail'（_spawn_failure 內讀 _spawn.stderr 進 failure_detail）
2. cascade：不增 attempts（不是 agent 的錯、不該燒 goal 的預算）
3. dispatcher 給 (target_id, kind) 設 30s cooldown（SPAWN_COOLDOWN_SEC）
4. 全域 consec_fast_fails 計數 +1
5. 若 consec_fast_fails ≥ 10（CONSEC_SPAWN_FAIL_LIMIT）→ daemon 退出 rc=2
   （claude.exe 持續壞、需要人工介入）
   任何非 fast-fail outcome 重置計數為 0
```

cooldown 期內 `bfs_refill` 跳過該 (target, kind)、queue 不會 burst-retry。`.attempts/<pid>/_spawn.stderr` 留有 stderr tail 供 forensic。

---

## 7. 設計取捨速查

| 決策 | 為什麼 |
|---|---|
| Context.md 必看訊息 inline、companion 只當備援 | F43 教訓：agent 不會主動讀 companion |
| Timeout 走 postmortem 而非邊想邊存 | 主任務不被 deliverable 維護分心 |
| 進度筆記只保留最近一次（overwrite） | F33/F53 session 記憶通常 incorporate 上次內容 |
| Verify inline dispatcher 不佔 worker slot | 純框架操作沒理由佔 LLM pool 格子 |
| F41 LLM Verify 修復取消 | 26 次實證 0 觸發、不為罕見事件付架構成本 |
| OR passive (cap=1) 不 eager fanout | 強模型下純粹浪費 token |
| Dedupe 用 Lean kernel isDefEq | 字串比對命中率低；schema 零改動、Lean 知道 α/β/η/defeq |
| Phase 1 用 `by hint` + 寫回精確 winner | 把 mathlib `register_hint` curated set 接過來；artifact 留具名 tactic（forensic）；多花一個 confirm build 但搜尋集合自動跟 mathlib 同步 |
| Spawn fast-fail 不算 agent error | infra 問題不該燒 goal 預算 |

---

## 8. 跨參考

- 系統靜態形狀（角色、不變量、DB schema、cascade 規則完整版）：`docs/architecture.md`
- 操作員 CLI / 環境變數：`docs/OPERATOR.md`
- 當前狀態 / 待辦：`docs/STATUS.md`
- Context.md 失敗 section 即將重構：`docs/dev/goal_history_unified.md`
