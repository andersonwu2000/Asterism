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

主迴圈每輪做五件事、順序固定。每個 stage 短說明資料怎麼動、深入的展開連結到後章。

```
1. cascade             — 收割上一輪完成的 worker outcome、更新 goal/strategy 狀態
2. verify housekeeping — 撈 ready strategy 組裝寫 alias 進 parent；同 loop 內跑 G1
                         shelved-revival pass
3. root_proved? exit   — 若 root proved → reconcile + prune + library promote、退出
4. bfs_refill          — 把 open goal 排進 queue；同時 enqueue Strategist routine
                         trigger（離上次 ≥ interval）+ inject_batch_done trigger（batch
                         全部 outcome 落地後 fire）
5. spawn               — 有空格就從 queue 拉、spawn pipeline；pre-spawn 對 gateway
                         POST /register 取 session token
```

**Stage 1 — cascade**：worker thread 完成後 INSERT 一個 finished pipeline row、主執行緒讀 outcome、套狀態轉移（Builder proved → goal proved；Backward success → goal attempting；Forward success → 落地新 goal、依 sorry_free 走 proved 或 open + detached=1；Strategist → 多 row 寫 `strategist_decisions` + 各 kind 各自副作用；任一失敗 → attempts++ → 到 SHELVE_THRESHOLD 就 shelved 並上拋）。完整規則在 architecture.md §7。**worker thread 絕不直接改 goal/strategy 狀態**、這條紀律消除整類 OR-race。

**Stage 2 — verify housekeeping**：純框架、無 LLM、單執行緒、可能遞迴連帶多層。詳解 §4。

**Stage 3 — root proved exit**：root goal 進入 proved 後跑：`prune.reconcile_proved_goals`（修 OR-race 留下的 file/DB drift）→ `prune.prune_problem`（GC orphan 檔）→ `library.maybe_promote`（dormant、目前不自動 promote、見 architecture.md §10）、然後 dispatcher 退出。

**Stage 4 — bfs_refill**：對 open goal 走 recursive CTE 過濾掉 dead/superseded 分支下的 orphan、剩下的依 `entry_kind`（Manifest 寫的或 Backward agent 標的、attempts ≥ BUILDER_THRESHOLD 強制升 Backward）排進 queue。每個 (target_id, kind) 同時最多一條 in-flight（passive OR cap=1）。Strategist 喚醒走另一路徑：`maybe_enqueue_inject_batch_done`（cascade 期間 / `update_strategy_status` hook）+ routine interval timer + pending_review enqueue（agent_shelved 後）。

**Stage 5 — spawn**：從 queue 拉一個、用 `ThreadPoolExecutor.submit` 派一條 pipeline 進 worker thread。pipeline 入場前 POST `/register` 給 gateway 拿 session token、再寫 `_mcp_config.json` 給 claude.exe。pipeline 內部 flow 是 §3 主題。dispatch.pool == gateway workers、locked together（#118 1:1 binding）。

---

## 3. Pipeline flows

### 3.0 共同骨架

Phase 7 — pipeline = 一個 claude session 的 lifecycle。retry 收進 pipeline
內部、由 `Tooling/pipeline/_retry.py` 的 `run_with_session_retries` helper
管理：sid 是 helper local var、cold spawn `--session-id <sid>`、warm spawn
`--resume <sid>`。helper 的 budget = `(BUILDER|SHELVE)_THRESHOLD - goal.attempts`
動態算出。

**Strategist Inject 例外**：若 `decision_id` 非 None（pipeline 由 Strategist
Inject 認可而非 bfs_refill organic dispatch），helper 跳過 budget 扣 attempts、
fresh budget = `(BUILDER|SHELVE)_THRESHOLD`；同時 `goal_still_active` 跳過
`attempts ≥ shelve_threshold` 檢查。Strategist 已在 failure_replay 看完 attempts
歷史、認可後仍下指令、framework 不二猜。唯一守住的硬上限是 goal status
（已 proved / disproved / dead / pending_strategist_review 仍 moot、防 Inject
撞 parallel cascade terminal）。收斂責任落在 Strategist 自身的 ConfirmShelve
紀律（見 `Tooling/prompts/strategist/pending_review.md`）。

```
框架側準備（pipeline 入場一次）：
  - 預寫框架要鎖的檔（Backward 預寫 patch.lean skeleton；Builder 不需要）
  - 若 .drafts/ 有上次 timeout 留的進度筆記 → cold-iter compile_context 時併入 Context.md
  ↓
Helper retry loop（最多 budget 次）：
  - cascade re-check：goal 已終態 → return outcome='moot'
  - cold (attempt 0): compile Context.md + spawn `--session-id <sid>`
    warm (attempt > 0): spawn `--resume <sid>` + retry_context（上次失敗 detail）
  - rc=125 (stale_session) on warm: in-place re-mint sid + cold spawn、不耗 budget
  - rc=124 (timeout): postmortem 寫 `.drafts/` → buffer 失敗 → return 'exhausted'
  - rc=126/127 / spawn_fast_fail: 早返 outcome='failed'、不耗 budget、不 buffer 自身
  - rc=0: parse_fn → terminal (proved/success/agent_declined/agent_infeasible/
    goal_no_longer_open) → return；非 terminal failure → buffer + 下一輪
  ↓
框架側收尾：
  - dispatcher 寫 pipelines row（一條 pipeline = 一筆）
  - flush helper 的 pending_failures：每筆 → 一條 dead_attempt + attempts++（all-or-nothing：
    daemon 中途 kill、attempts 不動、無孤兒 dead_attempts）
  - 對 outcome='moot' 跳過 flush（uniform no-op）
  - cascade_one：依 outcome / failure_reason 做 status transition
  - WorkArea 清 .attempts/<pid>/；成功則清 .drafts/
```

outcome 五種：`proved` / `success` / `failed` / `exhausted` / `moot`。框架對每種有不同的 .drafts 處理（§6）。

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

**Phase 2 — `tactic_llm`（in-pipeline retry helper、Phase 7）**

helper budget = `BUILDER_THRESHOLD - goal.attempts`、每輪同 sid。

```
helper iter (cold attempt 0 / warm attempt 1+):
  cold: agent.compile_context(...) → spawn claude --session-id <sid>
  warm: spawn claude --resume <sid> + retry_context (上次 lake error)
  ↓
parse_fn:
  1. _safe_glob patch*.lean → 缺檔則 failed/agent_no_output
  2. extract leading comments；分流 decline directive：
     `-- decline: needs_decomposition` → terminal failed/agent_declined
     `-- decline: unprovable` → terminal failed/agent_infeasible
     `-- decline: return_to_parent` → terminal failed/parent_needs_fix
     `-- decline: shelve` → failed/agent_shelved（轉 pending_strategist_review）
     leading 空白 → failed/agent_no_annotation
  3. forbidden_lemmas grep → failed/forbidden_lemma
  4. cite gate（`_cite_gate._resolve_cite_dependencies`）：patch 內所有 `import
     Problems.<p>.proofs.<sib>` 必 對應 proved goal。命中未 proved sibling →
     failed/cite_unproved_sibling（防 Builder 引用 shelved sibling 的 sorry-bearing
     wrapper、避免 axiom_probe 後段才 catch sorryAx）
  5. backup parent.lean → 套 patch → lake build
  6. 過 → outcome='proved'（patch 含 annotation 直接是 proved goal source）
     不過 → 還原 backup → failed/lake_build_error
```

helper 對非 terminal failure：buffer dead_attempt + 下一輪 retry。
budget 用盡 → outcome='exhausted'、carry last failure_reason/detail。
rc=124 → postmortem 寫 `.drafts/builder_g<gid>.md` → buffer + 強制 exhaust。
rc=125 (warm only) → in-place 重 mint sid + cold spawn、不耗 budget。
rc=126/127/spawn_fast_fail → 早返 outcome='failed'、不耗 budget、不 buffer 自身。

**Builder 失敗模式**：Phase 1 hint 失敗 fall-through 進 helper、不獨立成 outcome。
Phase 1 自身可能直接 return：`forbidden_lemma`（hint 結果命中 forbidden）/
`lean_file_missing`。Phase 2 透過 helper 走 `lake_build_error` / `forbidden_lemma` /
`agent_declined` / `agent_infeasible` / `agent_no_output` / `agent_no_annotation` /
`agent_rc_nonzero` / `agent_timeout` / `spawn_fast_fail` / `quota_exhausted` /
`missing_dep`。

cascade 對 Builder：
- `proved` → goal proved
- `exhausted` → 讀當前 attempts；過 SHELVE 就 shelved + propagate；過 BUILDER 不額外動（下次 dispatch 由 `next_worker_kind` 改派 Backward）
- `moot` → no-op
- `failed/agent_declined` → attempts++ 一次 + `entry_kind='Backward'`
- `failed/agent_infeasible` → attempts++ 一次 + 直接 disproved + propagate
- `failed/parent_needs_fix` → attempts++ 一次 + 直接 dead + propagate
- `failed/agent_shelved` → attempts++ 一次 + 轉 pending_strategist_review（不 propagate）
- `failed/spawn_fast_fail` / `quota_exhausted` / `missing_dep` → 不 ++、設 30s cooldown
- `failed/<其他>`（多為 Phase 1 直接 return）→ attempts++、過 SHELVE 就 shelved

完整 reason × 觸發 × helper 處理 × cascade × event 投影對照表 → `docs/failure_modes.md` §2。

### 3.2 Backward

對 goal 拆出一條 Strategy + N 個 sub-goal。OR-aware：每條 strategy 用 strategy-isolated 檔名（`_strategy_s<sid>.lean` + sub-goal slug 含 `s<sid>_` 前綴）、parent 的 lean_path **不被 Backward 改動**、留待 Verify 勝出時改寫。

**完整 flow**（Phase 7 in-pipeline retry helper、budget = `SHELVE_THRESHOLD - goal.attempts`）：

```
pipeline 入場（一次）：
  1. INSERT 新 strategy 拿 fresh strategy_id、sid_token=s<id>
     （Phase 7 — 每個 pipeline 永遠 fresh strategy_id；不再跨 pipeline 重用 dead strategy）
  2. 讀 parent stub 文字、用 _build_strategy_skeleton 算出 skeleton 文字 + skeleton_signature
     （skeleton 把 `theorem <slug> <binders> : <type>` 簽名複製、改名 sX、body=sorry）

helper iter (cold attempt 0 / warm attempt 1+):
  cold: agent.compile_context(...) + 寫 patch.lean = skeleton → spawn --session-id <sid>
  warm: spawn --resume <sid> + retry_context（patch.lean 不重寫、保留 agent 上輪 edits）
  ↓
parse_fn（每輪一次、rc=0 才會 call）:
  3. _safe_glob patch*.lean → 缺檔則 parse_proposal_fail
  4. extract patch.lean 檔頂 `--` leading comments
     `-- decline: unprovable` → terminal agent_infeasible
     `-- decline: return_to_parent` → terminal parent_needs_fix
     `-- decline: shelve` → terminal agent_shelved（轉 pending_strategist_review）
     leading 空白 → agent_no_annotation（retryable）
  5. patch.lean 簽名沒被改（normalize whitespace 後比對 skeleton_signature）
     不符 → patch_signature_mismatch
  6. **Phase 6.5 leaf-bypass**：new_*.lean 為 0 個但 patch.lean body 非 sorry →
     視為 0-subgoal strategy、forbidden grep + 跑 lake build patch 單檔、
     race guard 過了就 commit；body=sorry 才 parse_proposal_fail
  7. forbidden_lemmas grep（patch + 所有 new_*.lean）
  8. 驗每個 sub-goal slug：lowercase `[a-z][a-z0-9_]*`、≤ 60 chars、不符 → naming_violation
     跨 problem 名稱衝突 → framework auto-suffix `_2`/`_3`/...
  9. dedupe：batch `apply @<canonical> <;> assumption` probe 比對候選池（ancestor
     chain / sibling orphan / cross-branch proved / 同 problem disproved），命中
     alive → 寫 alias `:= by apply <slug> <;> assumption`、命中 disproved → 整 batch
     abort (`same_as_disproved`)
  10. 把檔案搬到永久路徑：
      - sub-goals: Problems/<p>/proofs/L_<slug>.lean
      - scratch:   Problems/<p>/proofs/_strategy_s<sid>.lean
  11. inject_imports_for_subs（agent 常忘 import）
  12. cite gate（`_cite_gate._resolve_cite_dependencies` 在 leaf-bypass 路徑 + 也在
      decomp 路徑、後者 `allow_auto_link=True` 把 parallel-buildable open siblings 進
      strategy_subgoals）
  13. lake build batch（subs + scratch 一起）→ 失敗則 unlink placed + lake_build_error
  14. race guard：再讀 goal status；非 open/attempting → unlink + goal_no_longer_open
  15. INSERT goals + strategy_subgoals；dedupe-hit / sorry-free 的 sub 直接 mark proved
  16. UPDATE strategy.scratch_path + proposal_md → outcome='success'

pipeline 結束：
  - outcome != 'success' → mark strategy 'dead'（outer cleanup、不再每個 _abort 各自 mark）
```

helper 對非 terminal failure：buffer dead_attempt + 下一輪 retry。
budget 用盡 → outcome='exhausted'。rc=124 → backward postmortem 寫 `.drafts/backward_g<gid>.md`
+ 強制 exhaust。rc=125 (warm) → in-place re-mint。rc=126/127/spawn_fast_fail → 早返不耗 budget。

**特殊 placement**：agent 偶爾把整段 valid proof 寫進 `new_*.lean` 而不是留 sorry stub。framework 偵測到 sorry-free + axioms 在白名單就直接把該 sub-goal mark proved、跳過後續 Backward dispatch（`_try_promote_sorry_free`）。

**Backward 失敗模式**：parse_fn 走 `parse_proposal_fail` / `agent_no_annotation` / `patch_signature_mismatch` / `naming_violation` / `forbidden_lemma` / `lake_build_error` / `goal_no_longer_open`（race guard、terminal）。terminal 從 helper 直返：`agent_infeasible` / `parent_needs_fix` / `agent_shelved` / `goal_no_longer_open`。spawn 層 helper 處理：`agent_rc_nonzero` / `agent_timeout`（postmortem）/ `spawn_fast_fail` / `quota_exhausted` / `missing_dep`。Backward **沒有 `agent_declined` channel**（agent 想退出走 `unprovable` 含反例 / `return_to_parent` 含 fix hint / `shelve` 等 Strategist 覆核 三條）、也**沒有 `agent_no_output`**（rc=0 但少檔走 `parse_proposal_fail`）。

cascade 對 Backward：
- `success` → goal `attempting`（**還沒 proved**、等 Verify housekeeping promote）
- `exhausted` → 過 SHELVE 就 shelved + propagate；否則 status 不動讓下次 dispatch 重派
- `moot` → no-op
- `failed/agent_infeasible` → attempts++ 一次 + 直接 disproved + propagate
- `failed/parent_needs_fix` → attempts++ 一次 + 直接 dead + propagate
- `failed/agent_shelved` → attempts++ 一次 + 轉 pending_strategist_review（不 propagate）
- `failed/spawn_fast_fail` / `quota_exhausted` / `missing_dep` → 不 ++、設 cooldown
- `failed/<其他>`（goal_not_found / missing_parent_stub 等 framework race）→ generic attempts++

完整對照 → `docs/failure_modes.md` §2。

### 3.3 Forward

Strategist `Inject(pipeline="Forward")` 派、產一條新 toolkit lemma（kind ∈ {theorem,def,structure,class}）進池、後續由 Backward / Builder 攻或 leaf-bypass 直接 proved。同 problem 內最多一條 in-flight。target_kind='Problem'、target_id=problem 名（不 tie 任何 goal）。

```
pipeline 入場（一次）：
  1. /register + 寫 _mcp_config.json + Context.md（含 Strategist brief 入口）

helper iter (cold attempt 0 / warm attempt 1+)：
  cold: compile_forward_context（含 Strategist brief / library inventory / forward history）
        → spawn --session-id <sid>
  warm: spawn --resume <sid> + retry_context（上次 parse/lake/dedupe 失敗 detail）
  ↓
parse_fn:
  2. _safe_glob new_*.lean → 缺檔則 forward_no_new_goal
  3. 偵測 decline directive `-- decline: library_sufficient` → 終態 agent_declined
  4. extract_forward_metadata：slug / rationale / entry_kind / kind / sorry_free
     缺 rationale / 不合 slug regex / kind unrecognized → parse_rejected
  5. auto-prepend imports (Mathlib + Defs + Defs-level opens) — agent 漏 import 不算錯
  6. self_verify：lake elaborate（leading sorry OK；偵 sorry_free）
     有 lake error → forward_no_new_goal + retry_context 帶 error
  7. dedupe：find_canonicals_batch（problem 內 alive/proved 候選 + disproved）
     命中 alive → forward_no_new_goal（detail: dedupe blocked）
  8. commit_forward_lemma：搬到 proofs/L_<slug>.lean + INSERT goal
     - Curry-Howard 統一規則：sorry_free → status='proved'、否則 'open'
     - 永遠 detached=1（無 strategy 上游）
     - kind ∈ {theorem,def,structure,class} 一致對待、def/structure/class 帶 sorry 也進 BFS
  9. shelved_link（G1）：find_shelved_revivals_for_forward 對同 problem 內 shelved goals
     反向 probe「apply @<forward> <;> assumption」、命中即 set_alias_target(S, X)；
     不寫 alias body（X 還沒 proved）、由 verify housekeeping revival pass 在 X→proved
     時 deferred 寫入
  10. 若 decision_id 非 NULL 且 outcome != 'proved' → set_inject_decision_produced_goal
      （inject_batch_done 觸發以「lemma 真實狀態」而非「agent 寫完」為時機）

pipeline 結束：cascade 寫 outcome；helper flush pending_failures
```

cascade 對 Forward：
- `success` → 新 goal 已 INSERT、無父關係不上拋
- `proved` → 同 success、sorry-free leaf 直接 proved
- `failed/forward_no_new_goal` → 不 ++ 任何 goal 的 attempts（Forward goal-less）、fill inject decision outcome
- 其他 infra failure → cooldown、不影響任何既有 goal

**雙線防亂提**：(a) dedupe 擋現有 alive/proved 的重複提案；(b) Strategist 自己 failure replay 看到上次差的 Forward 結果會調整下次 brief。

### 3.4 Strategist

target_kind='Goal'（root）。trigger 種類：
- `first_launch`：root frozen、第一次喚醒、必須選 RequestUserAmend / Inject(Forward) / Inject(Backward, target=root) 其一
- `routine`：離上次 strategist run ≥ interval（預設 30 min）
- `pending_review`：goal `pending_strategist_review`（agent 自己 shelve 後等審）；payload 帶 target_goal_id
- `inject_batch_done`：某條 Inject batch 內所有 row outcome 非 NULL；同 root in-queue dedup

```
pipeline 入場：
  1. /register + 寫 _mcp_config.json
  2. compile_strategist_context → Context.md
     sections: trigger / [pending_review_*] / inject_batch_outcomes / pending_reopens
              / active_goals / failure_replay / TREE / manifest_meta
  3. spawn --session-id <sid>（無 retry helper、Strategist 不 retry）

parse_fn:
  4. _safe_glob decision.json → 缺檔則 agent_no_output
  5. parse_decisions：JSON array、每 row schema verify（kind / 必填欄位）
  6. verify_decisions：cross-decision invariant
     - ConfirmShelve 不能單獨送（必 pair Inject 同 array）
     - target_id 在 active goal list（normalize int / slug）
     - Inject(Backward|Builder) target 的 ancestor 不在 disproved/dead
     - Inject pipeline ∈ {Forward, Backward, Builder}
     不過 → strategist_schema_invalid（infra-reason、不 ++）
  7. all-Noop batch → strategist_noop（infra-reason）

commit_decisions:
  8. inject_batch_id = uuid4().hex if any Inject in array else None
  9. 對每筆 decision：
     - Inject(Forward) → enqueue Forward + INSERT strategist_decision row、batch_id 寫上
     - Inject(Backward|Builder) → 強制 reopen target + 必要時 detached=1 + `entry_kind ← pipeline`（防 bfs_refill 平行排錯誤 kind）+ enqueue
     - ConfirmShelve → _set_goal_terminal_and_propagate(shelved) + _propagate_shelve；
                       row INSERT 時 batch_id = inject_batch_id（同 array 內 link）
     - EmitDirective → set_problem_strategist_directive
     - RequestUserAmend → 寫 .proposed_<file> + INSERT row outcome='awaiting_human'
     - Noop → 只 INSERT audit row
  10. update_problem_last_strategist_at + set_problem_bootstrap_done
```

cascade 對 Strategist：committed decisions 各自副作用已在 commit 內套；cascade 只負責設 pipeline outcome。`inject_batch_done` 不在這裡 enqueue、而在 `propagate_inject_outcome_from_goal` / `update_strategy_status` 等 hook 內、由 `maybe_enqueue_inject_batch_done` 偵測「同 batch_id 所有 row outcome 非 NULL」時 fire。

---

## 4. Verify housekeeping

每輪 dispatcher tick 在 cascade 之後跑、純框架、無 LLM。

它的工作：把 sub-goal 全 proved 的 strategy 組裝編譯、把 parent goal 的 sorry stub 改寫成「我用這條 strategy 證的」。

```
loop（最多 max_iters=8 圈）:
  ready = strategies_ready_for_verify(DB)
        — 過濾條件：strategy 'proposed' AND 所有 sub-goal 'proved' AND parent goal 不是 'proved'
  revivals = _pending_shelved_revivals(DB)
           — G1：shelved goal S where S.alias_target_id = X AND X.status='proved'
             AND latest ConfirmShelve(S) batch 已全部 outcome 非 NULL AND 此 surfacing
             之後沒更新的 ConfirmShelve/Reopen 處理過
  若 ready + revivals 都空 → break
  
  對每條 strategy s（序列、單執行緒）:
    Step 1: 把 parent goal 的 .lean 檔改寫成 alias（atomic os.replace）：
              import Problems.<p>.proofs._strategy_s<sid>
              namespace Problems.<p>
              def <parent_slug> := @Problems.<p>.s<sid>
            Strategy 簽名鎖死保證 alias 的 type 跟 parent 完全相符。
            純字串模板、microsecond 級、無 Lean 介入。
            Backup 保留在 disk（verify_backup_path key by sid_token），
            等 root verify 結果再 cleanup 或 rollback。

    Step 2: strategy='succeeded'、parent goal='proved'（樂觀標）
            sibling strategies 標 'superseded'、strategy.proposal_md 寫進
            parent .lean 檔頂作 annotation（替代已退役的 per-problem playbook 流程）
            鏈式：parent goal 可能是更上層 strategy 的 sub-goal、下一圈會撈到

  對每個 revival (S, X)（G1 shelved-revival pass）:
    Step R1: 讀 S.lean_path、若有 `:= by sorry` body → build_alias_content
             重寫成 `:= by apply <X_canonical> <;> assumption`（自動加 import X_module）
             無 sorry body（agent 手改 / 已 promote）→ refuse、留 link 給 operator 看
    Step R2: _set_goal_terminal_and_propagate(S, 'proved')
             下一圈 loop ready 可能撈到 S 的 parent strategy（其唯一缺的 sub 就是 S）

最終 root verify（library.maybe_promote、root goal flip 為 proved 後、單一 integrity gate）：
    Step F: axiom_probe(Root.lean, axioms_for=main_fq)
            唯一 Lean elaboration 點 — lake serve worker 走完整 alias 鏈、
            缺 olean 的 L_*.lean on-demand elaborate
              - 抓 promote_to_alias drift（compile error → Lean 印 .lean 檔名+行號）
              - 抓任何漏網 sorryAx（rogue: [sorryAx]）
    Step Fa（happy）: cleanup_cascade_backups + library.promote 寫
                     Library/<Topic>/<problem>.lean、daemon idle-exit
    Step Fb（rogue sorryAx）:
              - bisect_sorryax_source: 對每個 'succeeded' strategy 跑
                #print axioms（deepest first）、找第一個 scratch 含 sorryAx 的
              - rollback_cascade_chain: 從元凶往 root 走、每層
                rollback_promote(parent_abs, backup) 恢復 sorry-stub、
                culprit strategy='dead'/goal='open'、上游 strategy='proposed'
                /goal='attempting'
              - dispatcher re-check `db.root_proved`：False → 繼續 main loop、
                下個 tick re-Backward culprit goal
```

empirical: 41+ 次 cascade verify 0 次攔到任何 sorry / drift（verify-collapse
rollout 26 + SG #19 10 + PN refactor 5）。唯一 caught sorryAx 案例（SG s378）發生在
Backward leaf-bypass submit time、不是 cascade。Mechanical-only cascade
把零收益的 verify 全省掉、failure path 用 bisect 補回 attribution。

**為什麼是 stage 而非 worker_kind**：純框架操作沒 LLM、不該佔 worker pool slot。早期版本（verify-collapse 之前）把 Verify 當第三種 worker_kind、每輪佔一個 ThreadPool 格子 ~60s、無收益。

**為什麼遞迴 max_iters=8**：深度 4 的題可能一輪 sweep 連帶 4 層 strategy 全部 promote；上限避免病態 case 卡住整個 tick。

**為什麼單執行緒**：housekeeping 在主迴圈 sequential 跑、自然解掉 OR-race（過去 per-goal Verify serialization 用的 `busy_parents` 已不需要）。

**為什麼沒有 LLM 修復**：早期設計過「Step 1 失敗叫 LLM 修一次 patch」。實證 26 次 verify 0 觸發 — 鎖死 strategy 簽名 + Backward commit 前先 build 過 sorry-stub 已過濾掉絕大部分組裝錯誤。再加 LLM 修復是為極罕見事件付架構成本。Step 1 真的開始失敗才回頭加。

---

## 5. Spawn 前準備

**Context.md 編譯**：每次 spawn 前框架從 DB 編一份 `Context.md` 寫進 `.attempts/<pid>/`。**agent 看到的所有訊息都從這裡來**（companion file 是備援、agent 經常不會主動讀）。Builder/Backward/Forward 共用 `compile_context`、Strategist 自己一支 `compile_strategist_context`、Sections 順序固定、每個 `_section_*` 不適用時回 `[]`：

**Builder / Backward / Forward**：

```
Goal statement                  ← Builder/Backward；Forward 改顯 Forward brief
Sandbox                         ← 讀寫權限邊界 + 預寫檔名約定
Strategy naming                 ← Backward only：sid 鎖死 sub-goal slug 前綴
Parent goal & strategy          ← origin='backward' only：parent statement + parent strategy proposal_md 截斷
Forward brief                   ← Forward only：Strategist Inject 的 brief 整段
Library inventory               ← Forward only：避免重複提案
Forward history                 ← Forward only：past Forward outputs（slug + outcome）
Mathlib hints
FORBIDDEN_LEMMAS
Strategic notes
Proved goals on this problem
Your previous progress note     ← timeout 留下的進度筆記（§6）
Goal history (umbrella)         ← Builder/Backward only、4 sub-section：
  ### Direct attempts on this goal       (kind-agnostic；含 agent_declined)
  ### Sibling decompositions failed Verify (Backward/None gate)
  ### Strategies whose decomposition died  (kind-agnostic)
  ### Sub-goals reported infeasible        (cross-goal、Backward/None gate)
```

**Strategist**：

```
Trigger                                  ← trigger_kind + pending_review target
Pending review (failure / strategies / ancestors)   ← pending_review only
Completed Inject batches                 ← 任何 trigger、有未 ack 的 batch
Pending reopen-promises                  ← G2：只列「該 batch 已完全 outcome 落地、
                                             且 Strategist 還沒處理過」的 promise
Active goals                             ← 非 terminal status 速覽
Failure replay                           ← Strategist 自己最近決策 + outcome
TREE                                     ← problem 樹 snapshot
Manifest meta                            ← first_launch / amend-relevant 時
```

`Goal history` umbrella 的 event 投影邏輯在 `Tooling/pipeline/events.py`（4 個函數 + `_NON_AGENT_REASONS` filter）。Empty bucket 整段省略；空 umbrella 連 `## Goal history` header 都不寫。完整設計與 audience 規則見 `docs/archive/goal_history_unified.md`。

Playbook section 已退役（Phase 3、commit `5be9a33`）— `Proved goals on this problem` 是它的 grep-based 取代。

**Sandbox**（agent cwd anchored at problem_dir + mathlib allowlist + --add-dir packages）：
- cwd = `Problems/<p>/`
- claude `--add-dir` 列：problem_dir、attempts_dir、`.lake/packages/`
- 讀允許：cwd subtree、`.lake/packages/mathlib/Mathlib/`
- 讀禁止：其他 `Problems/<...>/`（agent 想看別的 problem 的 sketch 也擋）
- agent 工具：Read / Write / Edit / Grep / Bash + `python -m Tooling.loogle *`（Mathlib lemma 搜尋 wrapper）

**預寫框架要鎖的檔**：
- Builder：不預寫、agent 自由改 `patch.lean`（其實是 parent goal 的 lean 檔）
- Backward：框架預寫 `patch.lean` skeleton — copy parent stub 的 `<kind> <slug> <binders> : <type>` 簽名（kind ∈ {theorem,def,structure,class}、`_skeleton._DECL_HEAD_RE` 統一解析）、改名 `<kind> s<sid>`、body 留 `by sorry`。agent 只改 body、簽名邊動會被偵測
- Forward：不預寫、agent 自由寫 `new_<slug>.lean`（statement + sorry stub 或 sorry-free 完整 proof）
- Strategist：不寫 patch、輸出 `decision.json`（JSON array）

---

## 6. Spawn 後的失敗 / 中斷處理（Phase 7 in-pipeline retry）

helper 在 retry loop 內看 rc 分支處理；失敗種類對應到不同的 buffer / .drafts 行為。

### 6.1 普通失敗 retry（rc≠0、wall-clock ≥ 10s；或 rc=0 + parse-stage failure）

例：lake build 沒過、forbidden_lemma 命中、agent_no_annotation。

```
1. helper 把 .attempts/ snapshot 進 PipelineResult.pending_failures（dict 含 reason / detail / artifacts）
2. 抽 lake stderr / parse error 進 detail；下一輪 retry 時當 retry_context inline 進 prompt
3. Backward 額外：parse_fn 內 unlink 寫進的 proofs/ 檔（builder backup 已 restore）
4. helper 下一輪：cold→warm（同 sid + --resume）；retry_context 帶上次失敗 detail
5. budget 用盡 → outcome='exhausted'、否則 proved/success → return
6. dispatcher 在 pipelines INSERT 後 flush pending_failures：每筆 dead_attempt + attempts++（all-or-nothing）
7. cascade 對 'exhausted' 做 status transition；過 SHELVE 才 shelved
```

普通失敗不寫 `.drafts/`：session 記憶 + retry_context 在同個 pipeline 內已經是接續媒介；
要跨 pipeline 的進度筆記只在 timeout 路徑留（§6.2）。

**Reflection callback**（`_reflection.py`、Phase 7 之後加）：每次 helper 完成（outcome ∈
{proved, success, exhausted} 或 decline directive：agent_declined / agent_infeasible /
parent_needs_fix / agent_shelved）會在同 worker thread 內 spawn 第二個 claude（`--resume
<sid>` + 180s cap）讓 agent 對自己這條 pipeline 寫一行 lessons 進 `Problems/<p>/LESSONS.md`
（cap 由 Manifest 控）。reflection 不影響主 pipeline outcome、純 best-effort。infra
failure（spawn_fast_fail / quota / missing_dep / goal_no_longer_open / moot）不觸發。
共用同 worker thread 的 /register slot（main release 後 reflection register、序列）。

### 6.2 Timeout（rc=124、process 被 SIGKILL）— postmortem

主 spawn 超過 600s（`WORKER_TIMEOUT_SEC`）被 SIGKILL。session memory 還在（pinned 在 disk），但 process 已死、沒機會把當下思考寫成檔。

```
1. 主 spawn timeout、SIGKILL
2. helper call postmortem_fn(sid)：
   claude --resume <sid> + 短 prompt（Tooling/prompts/<kind>_postmortem.md）：
     「你被中斷了、用 150 字寫下你的方向、卡在哪裡，存進 _progress.md」
   限時 180s（POSTMORTEM_TIMEOUT_SEC）
3. agent 用 session 記憶寫 .attempts/<pid>/_progress.md
4. helper buffer 'agent_timeout' failure → return outcome='exhausted'（不再續 retry、決策 3）
5. wrapper（run_builder / run_backward）把 _progress.md 複製到 Problems/<p>/.drafts/<kind>_g<gid>.md
6. dispatcher 在 pipelines INSERT 後 flush pending_failures（含 timeout 那筆）
7. WorkArea.__exit__ 刪 attempts_dir
8. cascade 對 'exhausted' → 過 SHELVE 才 shelved
```

下次 dispatch（fresh pipeline、新 sid）：
```
編 Context.md 時讀 .drafts/<kind>_g<gid>.md
inline 成「## Your previous progress note」section
agent 看到自己的回顧筆記、繼續做（fresh session）
```

**為什麼 timeout 強制 exhaust 不繼續同 session retry**（決策 3）：timeout 表示 agent 思考路徑卡死；同 session resume 會撞同卡點。`.drafts/` 持久化的整個目的就是給 cold restart 用。

**postmortem 自己也死怎麼辦**：180s cap + 任何 rc≠0 都當 best-effort 失敗（next pipeline 直接 cold start、不比沒 postmortem 差）。

`.drafts/` 在下次 pipeline 成功 commit 時自動清掉（success / moot 都 clear；exhausted 才 persist）。

### 6.3 Spawn fast-fail / quota_exhausted / missing_dep — infra 噪訊路徑

三種 rc 走相同處理（不耗 budget、不寫 dead_attempt、設 cooldown）：
- **spawn_fast_fail**：rc≠0 且 wall-clock < 10s。real claude.exe 啟動 ~3-5s、最快 legitimate 失敗（patch 結構錯）也至少要一個 model turn。低於 10s 的 rc≠0 幾乎肯定是 infra 故障：claude.exe crash、cwd 失效、network down。
- **quota_exhausted** (rc=126)：provider rate limit / quota 耗盡（gemini free-tier）。
- **missing_dep** (rc=127)：CLI 二進位缺。

```
1. helper 偵測 rc → 早返 outcome='failed'、不 buffer 自身、不耗 budget
   （prior iter 的 pending_failures 仍 attached、會被 dispatcher flush）
2. cascade：is_infra → return（不 ++ attempts、不寫 final dead_attempt）
3. dispatcher 給 (target_id, kind) 設 30s cooldown（SPAWN_COOLDOWN_SEC）
4. spawn_fast_fail only：consec_fast_fails 計數 +1；
   ≥ 10（CONSEC_SPAWN_FAIL_LIMIT）→ daemon 退出 rc=2（claude.exe 持續壞、需要人工介入）
   quota / missing_dep 不進 CONSEC（quota 自己會 recover、missing_dep 是 operator-fix）
   任何非 fast-fail outcome 重置 CONSEC 為 0
```

cooldown 期內 `bfs_refill` 跳過該 (target, kind)、queue 不會 burst-retry。`.attempts/<pid>/_spawn.stderr` 留有 stderr tail 供 forensic。

---

## 7. 設計取捨速查

| 決策 | 為什麼 |
|---|---|
| Context.md 必看訊息 inline、companion 只當備援 | 教訓：agent 不會主動讀 companion |
| Timeout 走 postmortem 而非邊想邊存 | 主任務不被 deliverable 維護分心 |
| 進度筆記只保留最近一次（overwrite） | timeout postmortem 重寫即可、cold restart agent 看到的是最新一次 |
| Pipeline = session lifecycle（Phase 7、in-pipeline retry helper） | retry 收進 pipeline 內、sid 是 local var；移除 `goals.*_session_id` columns + cross-pipeline 攜帶機制 |
| Verify inline dispatcher 不佔 worker slot | 純框架操作沒理由佔 LLM pool 格子 |
| Verify-time LLM 修復方案被取消 | 26 次實證 0 觸發、不為罕見事件付架構成本 |
| OR passive (cap=1) 不 eager fanout | 強模型下純粹浪費 token |
| Dedupe 用 Lean kernel isDefEq | 字串比對命中率低；schema 零改動、Lean 知道 α/β/η/defeq |
| Phase 1 用 `by hint` + 寫回精確 winner | 把 mathlib `register_hint` curated set 接過來；artifact 留具名 tactic（forensic）；多花一個 confirm build 但搜尋集合自動跟 mathlib 同步 |
| Spawn fast-fail 不算 agent error | infra 問題不該燒 goal 預算 |

---

## 8. 跨參考

- 系統靜態形狀（角色、不變量、DB schema、cascade 規則完整版）：`docs/architecture.md`
- Context.md `## Goal history` umbrella 設計史：`docs/archive/goal_history_unified.md`
