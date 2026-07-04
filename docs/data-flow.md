# Asterism — 資料流向

本檔講**動態**：dispatcher 一輪 tick 怎麼跑、每條 pipeline 的完整流程與失敗模式、跨 pipeline 共用的機制。
靜態形狀（角色、不變量、DB schema、cascade 規則完整版）見 `docs/architecture.md`。

> 原寫於 2026-05-06，2026-06-05 對照代碼全面校正並重寫。

---

## 0. 先讀：兩個全域慣例

整份文件反覆用到這兩件事，先講一次，後面不再重複解釋。

**編譯驗證走 LSP gateway，不是 cold `lake build`。**
證明 pipeline（Builder / Backward / Forward / Librarian）所有的 elaborate / build 驗證，
都打到常駐的 LSP gateway warm worker（`lake serve`），省掉每次 5–15s 的 cold 啟動。
少數例外**刻意** cold（`lake env lean` / `lake build`）：dedupe 的 apply/isDefEq probe、
每個 problem 首次 dispatch 前的 Defs/Root pre-flight、以及 #35 記載的異閉包 decl gate /
最終 warn-gate / import-swap 後 rebuild-gate（warm slot 只服務同閉包整檔 gate）。

**`dispatch.pool == gateway workers`，1:1 綁定 + own-slot 紀律（#118）。**
worker 池大小等於 gateway 後端數、一起伸縮——但 1:1 的實質是 **pipeline = slot**：
pipeline 入場 `/register` 即 claim 一格、終身持有到 `/release`；生命週期內所有驗證都
應打**自己這格**（`verify_in_session` 帶 session token；共用分派在
`_axiom.verify_on_own_slot`，warm ~50-200ms、無 eviction）。`verify_file` 是 **borrow**
入口（gateway 挑格、會踢掉該格 warm 內容）——只限**非-pipeline** context 用：
主線程 housekeeping（G1 revival、root integrity gate）、operator CLI、Builder Phase 1
（spawn 前、尚未 register）。borrow 挑格 unclaimed 優先、只在全 pool 都被 claim 時才碰
別人的格。框架自持 session（librarian cleanup mechanical span）合法：它同時佔一個 pool
thread、額度守恆。

---

## 1. 三層儲存

| 層 | 位置 | 壽命 | 用途 |
|---|---|---|---|
| **暫存** | `.attempts/<pipeline_id>/` | 一次 spawn | agent 當下的工作目錄；spawn 結束無條件 `rmtree` |
| **跨 spawn** | `Problems/<p>/.drafts/<kind>_g<gid>.md` | 該 goal 證完前 | timeout 後留給下次的進度筆記 |
| **永久** | DB + `proofs/L_*.lean` + `_strategy_s*.lean` + `Root.lean` | 與 problem 同壽 | 真實狀態的單一來源（SoT） |

設計理由：暫存隨 spawn 拋掉，保證每次乾淨起手；跨 spawn 層只放「需要傳給下次」的東西；永久層就是 DB + Lean 檔。

agent 寫進 `.attempts/<pid>/` 的所有東西（不論成敗），在目錄被 `rmtree` 之前先打包進
`dead_attempts.artifacts` JSON 欄位。**DB 永遠是 SoT。**

---

## 2. 一輪 dispatcher tick

主迴圈每輪依固定順序跑下列步驟。每步先一句話講它做什麼，深入展開連到後章。

| # | 步驟 | 做什麼 | 詳解 |
|---|---|---|---|
| 1 | **cascade** | 收割上一輪完成的 pipeline outcome，套 goal/strategy 狀態轉移 | 本節 + §3 各 pipeline |
| 2 | **verify housekeeping** | 撈 sub-goal 全 proved 的 strategy，組裝寫 alias 進 parent；同迴圈跑 shelved-revival | §4 |
| 3 | **post-proved gate** | 對「root 剛 flip proved」的 problem：修 drift → root 完整性驗證 → 刷 TREE | §4 末段 |
| 4 | **librarian refill** | 對 opt-in 且已 Ingest 的 problem，把 Library 化工作排進 queue | §3.5 |
| 5 | **exit check** | `all_problems_ingested && 無 Librarian 待辦` → daemon 退出 | — |
| 6 | **bfs refill** | 把 open goal 排進 queue（每 goal 最多一條 pipeline） | 本節 |
| 7 | **strategist triggers** | 排 routine（T1）/ stall（T4）喚醒 | §3.4 |
| 7b | **reconcile_stuck_states** | per-tick 安全網：孤兒 pending_review / NULL-outcome Inject wedge 修復 | — |
| 8 | **spawn** | 有空格就 pop queue、派 pipeline 進 worker thread | 本節 |

> 注意 step 3–5 在 bfs/spawn **之前**：root 一旦證完，先把完整性驗證和 Library 化排掉，再決定要不要繼續排證明工作。

### Step 1 — cascade

worker thread 完成後 INSERT 一筆 finished pipeline row；主執行緒讀 outcome，套狀態轉移：

- Builder `proved` → goal `proved`
- Backward `success` → goal `attempting`（還沒 proved，等 §4 promote）
- Forward `success` → 新 goal 已落地（sorry-free 則 `proved`，否則 `open` + `detached=1`）
- Strategist → 各 decision 的副作用已在 commit 時套好，cascade 只設 pipeline outcome
- 任一失敗 → `attempts++`，到 `SHELVE_THRESHOLD` 就 `shelved` 並向上拋

完整規則見 architecture.md §7。

> **關鍵紀律：worker thread 絕不直接改 goal/strategy 狀態。** 所有狀態轉移都集中在主執行緒的 cascade，消除整類 OR-race。

cascade 也是兩個 Strategist 喚醒的觸發點（見 §3.4）：goal 轉 `pending_strategist_review` 時 enqueue
`pending_review`；某條 Inject batch 全部 outcome 落地時 enqueue `inject_batch_done`。

### Step 6 — bfs refill

對每個 open goal 走 recursive CTE，濾掉 dead/superseded 分支下的 orphan，剩下的依 `entry_kind` 排進 queue：

- `entry_kind` 來自 Manifest、或 Backward agent 標記、或 Strategist 決策
- `attempts ≥ BUILDER_THRESHOLD` 強制升 Backward（`next_worker_kind`）

**一個 goal 同時最多一條 pipeline（任意 kind）。** 若該 goal 已有 queue 或 running 的 pipeline
（含 Strategist Inject 排的），本輪 organic routing 一律 defer，避免和 Strategist 決策的 kind 互打。

### Step 8 — spawn

pool 有空格就 pop 一筆 queue row，派一條 pipeline。**v17 起 pop = lease claim**：
row 標 `owner_pid`+`leased_at` 而非刪除（跨行程 in-flight 可見——並發 dispatcher 搶不到
同一 row；lease row 對所有 in-queue 去重查詢照樣算「在 queue」），pipeline 結束或 pop 端
skip 時才 `complete_queue_row` 刪除；死 owner／逾 TTL 的 lease 由 per-tick sweep 釋放
（PID 死**或** TTL 過期雙判準——Windows 會重用 PID）。pop／flush／startup 清理全部按
daemon 的 `--scope` 過濾（`queue.problem` 欄），scoped daemon 互不干擾（舊 #74 類）。
Librarian per-file 單位的檔名走 `queue.payload` JSON；`problem\x1ffile` 組合字串只作
行程內派工身分 + `librarian_fail_counts` key（STATUS reset 規則不變）：

1. 3-tuple `(target_id, kind, decision_id)` 去重（同 batch 的 Inject siblings 共用 target+kind、靠 decision_id 區分）
2. 跳過 quota cooldown 中的 kind
3. **lazy verify gate**：該 problem 本次 daemon run 首次 dispatch，先付一次性 `lake build Defs+Root`（~5–15s）；失敗就把 problem quarantine 起來
4. `pool.submit(_run_pipeline, ...)` 丟進 worker thread

> `/register` 取 session token 和寫 `_mcp_config.json` 都發生在 worker thread 內、pipeline 入場時（§3.0），不在這個 dispatcher 步驟。

收尾還有兩個非 root-proved 的退出點：`--once` 模式下 queue 空即退；以及 idle exit（沒有 in-flight、queue 空、
無 open goal、無 ready strategy）—— 代表 goal 全 shelved 或全 dead，沒事可做。

---

## 3. Pipeline flows

### 3.0 共同骨架

**一條 pipeline = 一個 claude session 的完整 lifecycle**（含 retry）。retry 不再跨 pipeline，
全收進 `Tooling/pipeline/_retry.py` 的 `run_with_session_retries`：

- `sid`（session id）是 helper 的 local 變數
- cold spawn（attempt 0）用 `--session-id <sid>`；warm spawn（attempt > 0）用 `--resume <sid>`
- budget = `(BUILDER|SHELVE)_THRESHOLD - goal.attempts`，動態算出

**outcome 五種**：`proved` / `success` / `failed` / `exhausted` / `moot`。

**入場（一次）**

- `/register` 取 session token + 寫 `_mcp_config.json`
- 預寫框架要鎖的檔（Backward 預寫 `patch.lean` skeleton；Builder/Forward 不預寫）
- `.drafts/` 有上次 timeout 的進度筆記 → 編 Context.md 時併入

**retry loop（最多 budget 圈）**

每圈先 cascade re-check（goal 已終態 → `moot`），再 spawn：cold（attempt 0）走 `--session-id <sid>`；
warm 走 `--resume <sid>` + retry_context（上次失敗 detail inline）。然後依 rc 分支：

| rc | 處理 |
|---|---|
| `0` | `parse_fn` → 命中 terminal 就 return；非 terminal failure → buffer + 下一圈 |
| `124`（timeout） | postmortem 寫 `.drafts/` → buffer → `exhausted`（不續 retry） |
| `125`（stale session，僅 warm） | 原地重 mint sid + cold 重 spawn，不耗 budget |
| `126` / `127` / spawn_fast_fail | 早返 `failed`，不耗 budget、不 buffer 自身 |

**收尾**

- dispatcher 寫一筆 pipelines row
- flush 累積的 pending_failures：每筆 → 一條 dead_attempt（`attempts++` 已在失敗當下做）；`moot` 跳過 flush
- `cascade_one`：依 outcome / failure_reason 做狀態轉移
- WorkArea 清 `.attempts/<pid>/`；該 kind 的成功 outcome 才清 `.drafts/`

幾個容易誤解的點：

- **attempts++ 是即時的，不是 all-or-nothing。** 每圈失敗時 helper 立刻 `attempts++`（在 `buffer_failure` 內），
  只有配對的 dead_attempt row 延到 dispatcher flush 才寫。daemon 中途被 kill 會讓 attempts 比 dead_attempts 多一筆（純帳面 drift，無害）。
- **`.drafts/` 的清除條件依 kind 不同**：Builder 的成功 token 是 `proved`、Backward 是 `success`（外加 `goal_no_longer_open`）；
  另加 `moot` 都清。`failed` / `exhausted` 則保留 .drafts 給下次 cold restart。

#### Strategist Inject 例外

若 pipeline 由 Strategist Inject 認可而非 bfs_refill organic dispatch（`decision_id` 非 None）：

- helper 不扣 attempts、budget 直接給滿（`= (BUILDER|SHELVE)_THRESHOLD`）
- `goal_still_active` 跳過 `attempts ≥ shelve_threshold` 檢查

理由：Strategist 已在 failure replay 看完 attempts 歷史、認可後仍下指令，framework 不二猜。
唯一守住的硬上限是 goal status —— 只要 goal 不是 `open`/`attempting`（已 proved / disproved / dead /
pending_strategist_review）就回 `moot`，防 Inject 撞到 parallel cascade 的終態。收斂責任落在 Strategist 自己的
ConfirmShelve 紀律（見 `Tooling/prompts/strategist/pending_review.md`）。

---

### 3.1 Builder

對 fresh sorry-stub goal 嘗試直接閉合。兩個 phase。

#### Phase 1 — `tactic_try`（無 agent、純 script）

**觸發**：`goal.attempts == 0` 且 parent lean 檔有 `:= by sorry` 行（`_is_sorry_stub`，MULTILINE 行尾錨點，
保護結構化 patch 不被誤觸）。

兩階段，都走 LSP `verify_file`：

1. **Probe** — 把 sorry body 換成 `by hint`，`verify_file`（不寫 olean）。Lean elaborator 跑所有
   mathlib `register_hint` 註冊過的 tactic（含 decide / norm_num / omega / linarith / aesop / exact? / ring …），
   對每個閉合 goal 的 tactic emit `info: [apply] 🎉️ <tac>`。framework 從 info diagnostics parse 第一個 `🎉️` 當 winner。全失敗 → 落 Phase 2。
2. **Confirm** — 把 sorry body 重寫成 `by <winner>`，再 `verify_file`（寫 olean）。確認精確 tactic 真的 work，
   且 patch 檔留下具名 tactic 而非 opaque `hint`（forensic + source 清晰）。

Confirm 後還有兩道閘：forbidden_lemma grep、axiom whitelist 檢查。任一不過 → 還原 sorry stub、
**直接 terminal return**（`forbidden_lemma` / `axiom_violation`），不落 Phase 2。

成功：patch 內是 `:= by <winner>`，outcome `proved`，artifact 留 `won_hint.lean` snapshot。

> **為什麼用 `by hint` 而非自維護 tactic list**：把 mathlib `register_hint` 的 curated set 直接接過來，
> 維護責任歸 mathlib、升級自動跟上；多付一個 confirm build，換具名 winner（forensic）。

#### Phase 2 — `tactic_llm`（in-pipeline retry helper）

budget = `BUILDER_THRESHOLD - goal.attempts`。`parse_fn` 每圈（rc=0 才呼叫）依序：

1. glob `patch*.lean` → 缺檔 `agent_no_output`
2. 抽檔頂 `--` 註解，分流 decline directive：
   - `needs_decomposition` → `agent_declined`
   - `unprovable` → `agent_infeasible`
   - `return_to_parent` → `parent_needs_fix`
   - `shelve` → `agent_shelved`（轉 pending_strategist_review）
   - 空白 → `agent_no_annotation`
3. forbidden_lemmas grep → `forbidden_lemma`
4. cite gate：patch 內每個 `import Problems.<p>.proofs.<sib>` 必對應 proved goal。命中未 proved sibling →
   `cite_unproved_sibling`（防引用 shelved sibling 的 sorry-bearing wrapper，避免 axiom_probe 後段才 catch）
5. backup parent.lean → 套 patch → `verify_file`
6. 過 → `proved`（patch 含 annotation，直接是 proved goal 的 source）；不過 → 還原 backup → `lake_build_error`

**cascade 對 Builder**：

| outcome / reason | 動作 |
|---|---|
| `proved` | goal proved |
| `exhausted` | 讀 attempts；≥ SHELVE 就 shelved + 上拋；≥ BUILDER 但未達 SHELVE 不動（下次改派 Backward） |
| `moot` | no-op |
| `agent_declined` | attempts++；未達 SHELVE → `entry_kind='Backward'`；達 SHELVE → 轉 review |
| `agent_infeasible` | attempts++ + 直接 disproved + 上拋 |
| `parent_needs_fix` | attempts++ + 直接 dead + 上拋 |
| `agent_shelved` | attempts++ + 轉 pending_strategist_review（不上拋） |
| `spawn_fast_fail` / `quota_exhausted` / `missing_dep` | 不 ++，設 30s cooldown |
| 其他（多為 Phase 1 terminal） | attempts++，≥ SHELVE 就 shelved |

完整 reason × 觸發 × cascade × event 投影對照 → `docs/failure_modes.md` §2。

---

### 3.2 Backward

對 goal 拆出一條 Strategy + N 個 sub-goal。**OR-aware**：每條 strategy 用 strategy-isolated 檔名
（scratch `_strategy_s<sid>.lean`、strategy 定理名 `s<sid>`），parent 的 `lean_path` **不被 Backward 改動**，
留待 §4 Verify 勝出時改寫。sub-goal 檔是 `L_<slug>.lean`，`<slug>` 是 agent 取的描述名（**不帶 `s<sid>_` 前綴**）。

budget = `SHELVE_THRESHOLD - goal.attempts`。

**入場（一次）**

1. INSERT 新 strategy → 拿 fresh `strategy_id`、`sid_token = s<id>`（每條 pipeline 永遠 fresh，不重用 dead strategy）
2. 讀 parent stub → `_build_strategy_skeleton` 算出 skeleton + signature：沿用 parent 的 `<kind>`（`theorem`/`def`/`structure`/`class`，不寫死 theorem），改名 `s<sid>`、body `sorry`。parent 無 top-level type colon（如已是 alias）→ `parent_stub_not_decomposable`

**每圈 spawn**

- **cold**（首圈）：編 Context.md + 寫 `patch.lean = skeleton` → `spawn --session-id <sid>`
- **warm**（後續）：`spawn --resume <sid>` + retry_context；`patch.lean` 不重寫，保留 agent 上輪 edits

**parse_fn（rc=0 才跑，每圈一次）**

1. glob `patch*.lean` → 缺檔 `parse_proposal_fail`
2. 抽檔頂註解分流 decline：`unprovable`→`agent_infeasible` ／ `return_to_parent`→`parent_needs_fix` ／ `shelve`→`agent_shelved` ／ 空白→`agent_no_annotation`
3. 簽名沒被改（normalize whitespace 比對 `skeleton_signature`）→ 否則 `patch_signature_mismatch`
4. **leaf-bypass**：0 個 `new_*.lean` 但 patch body 非 sorry → 視為 0-subgoal strategy；forbidden grep + `verify_file` 單檔 + axiom whitelist + race guard → 過就 commit
5. `forbidden_lemmas` grep（patch + 所有 `new_*.lean`）
6. sub-goal slug 驗證：lowercase `^[a-z][a-z0-9_]*$`、≤ 60 chars；跨 problem 撞名 → auto-suffix `_2`/`_3`
7. **dedupe**（見下）
8. 搬檔到永久路徑：sub-goals → `proofs/L_<slug>.lean`；scratch → `proofs/_strategy_s<sid>.lean`
9. `inject_imports_for_subs`（agent 常忘 import）
10. cite gate（decomp 路徑 `allow_auto_link=True`，把可平行 build 的 open siblings 收進 strategy_subgoals）
11. assembly gate：strategy scratch 不得殘留 sorry → `patch_body_contains_sorry`
12. `verify_file` batch（subs + scratch 一起）→ 失敗 unlink + `lake_build_error`
13. race guard：再讀 goal status，非 open/attempting → unlink + `goal_no_longer_open`
14. INSERT goals + strategy_subgoals；dedupe-hit / sorry-free 的 sub 直接 mark proved
15. UPDATE `strategy.scratch_path` + `proposal_md` → `outcome='success'`

**結束**：`outcome != 'success'` → mark strategy `dead`（outer cleanup）

**dedupe（parse_fn step 7）**：對每個候選 sub-goal，batch probe `apply @<canonical_fqn> <;> assumption` 比對候選池——
ancestor chain / sibling orphan / cross-branch proved / 同 problem disproved，另加兩道前置：

- **slug-pattern 預檢**（剝 `_alias`/`_2`… 後綴比對 proved）
- **no-progress 守門**：候選 ≡ 正在拆的 goal 或其未證 ancestor → `no_progress`（retryable，非 terminal）

命中 alive → 寫 alias `:= by apply <canonical_slug> <;> assumption`（bare slug，非 `@`），**並 build-verify**；
build 不過就放棄這次 dedupe、退回開新 sub-goal。命中 disproved → 整 batch abort（`same_as_disproved`）。

**sorry-free 直接 promote**：agent 偶爾把整段 valid proof 寫進 `new_*.lean` 而非留 sorry stub。framework 偵測到
sorry-free + axioms 在白名單，直接把該 sub-goal mark proved、跳過後續 dispatch（`_try_promote_sorry_free`）。

**cascade 對 Backward**：

| outcome / reason | 動作 |
|---|---|
| `success` | goal `attempting`（**還沒 proved**，等 §4 promote） |
| `exhausted` | ≥ SHELVE 就 shelved + 上拋；否則 status 不動，下次重派 |
| `moot` | no-op |
| `agent_infeasible` | attempts++ + 直接 disproved + 上拋 |
| `parent_needs_fix` | attempts++ + 直接 dead + 上拋 |
| `agent_shelved` | attempts++ + 轉 pending_strategist_review（不上拋） |
| `spawn_fast_fail` / `quota_exhausted` / `missing_dep` | 不 ++，設 cooldown |
| 其他 framework race | generic attempts++ |

> Backward **沒有 `agent_declined` channel**（想退出走 `unprovable`/`return_to_parent`/`shelve` 三條，各帶不同資訊），
> 也**沒有 `agent_no_output`**（rc=0 缺檔走 `parse_proposal_fail`）。其餘 Backward 專屬 reason
> （`same_as_disproved` / `no_progress` / `patch_body_contains_sorry` / `axiom_violation` / `agent_bailed` 等）見 failure_modes.md §2。

---

### 3.3 Forward

Strategist 用 `Inject(pipeline="Forward")` 派，產一條新 toolkit lemma 進池，後續由 Backward/Builder 攻或
leaf-bypass 直接 proved。`target_kind='Problem'`、`target_id=problem 名`（不綁任何 goal），同 problem 內最多一條 in-flight。

lemma 的 `kind ∈ {theorem, def, structure, class}`。

**每圈 spawn**

- **cold**：`compile_forward_context` → `spawn --session-id <sid>`
- **warm**：`spawn --resume <sid>` + retry_context（上次 parse/build/dedupe 失敗 detail）

**parse_fn**

1. glob `new_*.lean` → 缺檔 `forward_no_new_goal`
2. decline `-- decline: library_sufficient` → 終態 `agent_declined`
3. `extract_forward_metadata`：slug / rationale / entry_kind / kind / sorry_free。缺 rationale / slug regex 不符 / kind 不認得 → `parse_rejected`
4. auto-prepend imports（Mathlib + Defs + opens；agent 漏 import 不算錯）
5. self_verify：`verify_file`（probe；leading sorry OK；偵 sorry_free）。有 build error → `forward_no_new_goal` + retry_context 帶 error
6. dedupe：`find_canonicals_batch`（同 problem alive/proved + disproved）；命中 alive → `forward_no_new_goal`；命中 **proved** → `commit_forward_alias`（提案自動變 alias 落地、不算失敗）
7. `commit_forward_lemma`：搬到 `proofs/L_<slug>.lean` + INSERT goal
   - sorry_free → `proved`，否則 `open`
   - 永遠 `detached=1`（無 strategy 上游）
   - 所有 kind 一致對待，`def`/`structure`/`class` 帶 sorry 也進 BFS
8. shelved_link（G1）：對同 problem 的 shelved goals 反向 probe `apply @<forward> <;> assumption`，命中即 `set_alias_target(S, X)`。不寫 alias body（X 還沒 proved），由 §4 revival pass 在 X→proved 時補寫
9. `decision_id` 非 NULL 且 outcome != `proved` → `set_inject_decision_produced_goal`（inject_batch_done 以「lemma 真實狀態」而非「agent 寫完」為時機）

**cascade 對 Forward**：`success`/`proved` → 新 goal 已 INSERT、無父關係不上拋；`forward_no_new_goal` →
不動任何 goal 的 attempts（Forward 是 goal-less 的），填 inject decision outcome；其他 infra failure → cooldown。

**雙線防亂提**：(a) dedupe 擋現有 alive/proved 的重複提案；(b) Strategist 自己 failure replay 看到上次差的 Forward 結果，調整下次 brief。

---

### 3.4 Strategist

`target_kind='Problem'`（Phase 6 起 problem-keyed；曾 key 在 root goal id）。無 retry
helper（Strategist 不 retry；只有一次 in-pipeline verify 重試）。

**trigger**（`_derive_strategist_trigger` 於 spawn 時判定）：

| trigger | 何時 | 排在哪 |
|---|---|---|
| `inject_batch_done` | 某條 Inject batch 全部 row outcome 落地；**或 spawn 時題為 structural stall**（「empty batch done」語意——fresh 題 / deadlock / root 已證待 Ingest 都算） | cascade 時 enqueue / T4 stall trigger，同 problem in-queue 去重 |
| `pending_review` | goal 轉 `pending_strategist_review`（agent 自己 shelve 後等審） | cascade 時 enqueue，payload 帶 target_goal_id |
| `routine` | 離上次 ≥ interval（預設 **60 min**，`strategist.interval_min`）、`ingested_at IS NULL` | step 7 strategist_triggers |

（Phase 6：`first_launch` / T0 退役——fresh 題無 dispatchable 工作 + 未 Ingest = 本身
即 stalled，由 T4 立刻喚醒並套 inject_batch_done 的 mandatory-advance 規則逼出第一個
Inject。喚醒的 stale-drop 判準 = `problem_ingested`；daemon 退出 =
`all_problems_ingested` + 無 Librarian 工作。）

**入場**：`/register` + `_mcp_config.json` + 編 Context.md → `spawn --session-id <sid>`

**parse_fn**

1. glob `decision.json` → 缺檔 `agent_no_output`
2. `parse_decisions`：JSON array，每 row schema 驗證
3. `verify_decisions`：cross-decision invariant（任一不過 → `strategist_schema_invalid`，infra-reason、不 ++）
   - ConfirmShelve 不得與 Inject(Backward|Builder) 指向同一 target 或其 descendant（單獨送合法）
   - target_id 在 active goal list（normalize int / slug）
   - Inject(Backward|Builder) 的 target ancestor 不在 disproved/dead
   - Inject pipeline ∈ {Forward, Backward, Builder}
4. 全 Noop → `strategist_noop`（infra-reason）

**commit_decisions**：先算 `inject_batch_id`（含任何 Inject 才有、否則 None），再逐 decision 套副作用：

| decision | 動作 |
|---|---|
| `Inject(Forward)` | enqueue Forward + INSERT decision row（寫 batch_id） |
| `Inject(Backward\|Builder)` | 強制 reopen target + 必要時 `detached=1` + `entry_kind ← pipeline` + enqueue |
| `ConfirmShelve` | 設 goal terminal(shelved) + propagate；decision row `batch_id = inject_batch_id` |
| `EmitDirective` | `set_problem_strategist_directive` |
| `RequestUserAmend` | 寫 `.proposed_<file>` + INSERT row `outcome='awaiting_human'` |
| `Noop` | 只 INSERT audit row |

收尾：`update_problem_last_strategist_at`（routine 另 touch `last_routine_at`；
`bootstrap_done` 已 vestigial、Phase 6 起不再寫）。

> **decision kinds 共七種**：`Inject` / `ConfirmShelve` / `EmitDirective` / `RequestUserAmend` /
> `MarkDeliverable` / `Ingest` / `Noop`。舊的 `Reopen` 已移除 —— 重新啟用一律走
> `Inject(Backward|Builder)`。`Ingest` commit 先蓋 `problems.ingested_at`（唯一終態），
> library:true 再走 sign-off/harvest；rollback 或 `reject-ingest` 會撤銷。

**cascade 對 Strategist**：committed decision 的副作用已在 commit 內套好；cascade 只設 pipeline outcome。
`inject_batch_done` 不在這裡 enqueue，而在 `propagate_inject_outcome_from_goal` / `update_strategy_status` 等
hook 偵測「同 batch_id 所有 row outcome 非 NULL」時 fire。

---

### 3.5 Librarian

把一個**已證的 problem** 收成 mathlib 形狀的 `Library/`。只對 Manifest 標 `library: true` 的 problem 自動啟動。

鏈式 `dedup → classify → migrate → cleanup → bridge`。每步的 work-kind 由 `library_decls` 的 lifecycle 狀態推出
（dispatcher `_derive_librarian_work`，純讀），chain 每次成功後由 tick 層 `_librarian_refill` 重新 derive、
直到狀態機排空。`migrate` / `cleanup` 以**整個檔**為平行單位，多個無依賴關係的檔可同時在 pool 裡跑。

| 步驟 | 形式 | 做什麼 |
|---|---|---|
| **dedup** | 無 agent、純機械 | 盤點已證 decl，限縮到 harvest 目標的 live 使用閉包（classic = proved root；anchor+claim = deliverables，`_reachable_from_root`），全部標 `keep → deduped` |
| **classify** | one-shot JSON spawn | agent 給檔案佈局 + 檔內順序；framework 再做 SCC-merge + 用量 toposort 修正 → `target_file` / `file_order` |
| **migrate** | LSP + commit-retry | 一次寫**整個檔**的 decls（照 `file_order`）→ 過 commit gate → `migrated` |
| **cleanup** | LLM 多段 + 機械收尾 | per-file 精修（drop/merge/near-dup bridge、simplify、audit 整檔 mathlib-ize、decide rename + import-min）；收尾零-warning 硬閘 + **post-rewrite 公理閘**（§3.5 末） → `cleaned` / `dropped` |
| **bridge** | 無 agent | cite_drop 後 Gate B 整體意義驗證（見下），PASS 就寫 `Library/INDEX.md`、終止 chain；純 mathlib 引用的 wrapper 轉 `cited` |

**lifecycle 狀態**：`candidate → deduped → classified → migrated → cleaned`；
終態另有 `dropped`（cleanup 併掉）與 `cited`（bridge 轉純 mathlib 引用）。

**migrate 單位 = 一個檔**：`next_migrate_file` 挑「依賴檔都已 migrated」的下一個 classified 檔
（file DAG 的拓樸序）。DAG 由 `file_dependency_graph` 從 per-decl 用量圖 + classify 的 `target_file` map 即時重建，
**沒有 imports 欄位**。一個 agent 寫該檔所有 decls；framework 把第 N 個 top-level 宣告和第 N 個 slug 位置配對，
回填 `target_name` 並驅動 Gate D。

**commit gate（每次 migrate）**：

- **Gate A** — import 閉包：imports ⊆ {Mathlib, Library, Init, Std, Batteries, Lean}
- 整檔 `verify_file`：0 error、0 sorry
- 每個 decl `#print axioms` ⊆ whitelist
- **Gate D** — 每個 `def` 對原始 Defs decl 做 `rfl` def-equivalence

任一不過 → 把暫存檔 rollback，該檔 decls 留在 `classified`，chain 卡在這個檔。會重試到
`LIBRARIAN_MAX_CHAIN_RETRIES`（2）次，仍失敗就標 STALLED。

另外 commit gate 對任何 `axiom` **宣告**一律 hard-fail（Library 永不引入公理）——這條連同下面的
post-rewrite 公理閘一起走 `migrate_commit_gate`，migrate / cleanup 收尾 / deliverable bridge 三處共用。

**post-rewrite 公理閘（cleanup 收尾，2026-07-03）**：原則 =「每次高風險改寫後都要重驗公理」。
cleanup 的 LLM 段（simplify / near-dup bridge one-liner / audit 整檔重寫）跑在 migrate 公理閘**之後**、
是整條 chain 唯一能改變 decl 公理集的後段改寫（`by native_decide` build 綠、零 warning、卻拉進
`Lean.ofReduceBool`）。per-file cleanup 在零-warning 閘之後、對**最終文本**重跑同一套 per-decl
`#print axioms ⊆ whitelist`（decl 名從最終文本抽、rename / audit 偷加的宣告都涵蓋）。
不過 → `librarian_axiom_violation`、該檔留 `migrated`、chain 重試。

**Gate B（`bridge` 步驟，俗稱「秒殺」/定海神針）**：對整批收成做意義檢查 —— 從 Library 重新推導出原始 root
（Defs-free），跑 statement-pin + import 閉包 + build + axiom whitelist。這是 chain 的終止步，PASS 才寫 INDEX，
所以 INDEX 存在 = 整個 Library 真的能重證原題。

**deliverable 題的 bridge**（anchor+claim、無 root 可重推）：builds-only 之外，對每個 harvested 檔的
最終 on-disk 文本（在 cite_drop —— chain 拓撲末端的最後一次改寫 —— 之後）跑同一套 per-decl 公理閘，
PASS 才寫 INDEX。classic 題不需要：Gate B 的 root 重推 probe 本身就帶 axiom whitelist、覆蓋 root 閉包。

> 三道 Gate：**A** import 閉包、**B** root 重推、**D** Defs def-equivalence。**沒有 Gate C。**
> 公理面另有兩道 re-gate：cleanup 收尾（逐檔歸因）+ deliverable bridge 末端（終局保證）。

---

## 4. Verify housekeeping

每輪 dispatcher tick 在 cascade 之後跑，**純框架、無 LLM、單執行緒**。
工作：把 sub-goal 全 proved 的 strategy 組裝起來，把 parent goal 的 sorry stub 改寫成「我用這條 strategy 證的」。

每圈撈兩種待辦（最多 `max_iters=8` 圈，兩者都空就 break）：

- **ready strategies**（`strategies_ready_for_verify`）：strategy `proposed` ∧ `scratch_path` 非空 ∧ parent goal 不在 (`proved`,`shelved`) ∧ 所有 sub-goal `proved`
- **revivals**（G1，`_pending_shelved_revivals`）：shelved goal S，其 `alias_target_id = X` 且 X 已 `proved`

**對每條 ready strategy（序列）**

1. 把 parent goal 的 `.lean` 改寫成 alias（atomic `os.replace`）：

   ```lean
   import Problems.<p>.proofs._strategy_s<sid>
   namespace Problems.<p>
   def <parent_slug> := @Problems.<p>.s<sid>
   ```

   strategy 簽名鎖死，保證 alias 的 type 跟 parent 完全相符。純字串模板、microsecond 級。
   backup 留在 disk（key by `sid_token`），等 root verify 結果再 cleanup 或 rollback。
2. strategy → `succeeded`、parent goal → `proved`（樂觀標）；sibling strategies → `superseded`；
   `proposal_md` 寫進 parent `.lean` 檔頂作 annotation。
   > 鏈式：parent goal 可能是更上層 strategy 的 sub-goal，下一圈會撈到。
3. **背景 olean 暖機（#103）**：把剛改寫的 alias module 丟給 `OleanWarmer`（`pipeline/_olean_warm.py`）——
   一條 daemon thread 序列跑 cold `lake build`，**離開主執行緒、也不佔 LLM worker pool**。alias 是全新內容（無 olean）、
   且 scratch 的舊 olean 因 sub-goal 由 sorry→proof 而失效；不暖的話，後面 root integrity probe 會在主執行緒
   付一次 cold 閉包 build（曾觀察到「validate 突然 120s」）。best-effort：olean 缺/晚只拖慢 dedupe + probe，
   `proved`-in-DB 仍是 SoT。kill switch `verify.olean_warm`。
   > 史：#64（9cc7322 加 inline build → 4128212 移出）證明 olean build 不能放主執行緒（Jordan 10-strategy
   > cascade × 30-60s 卡死 pool）；#103 用獨立背景 builder 補回暖機、不回到主執行緒。

**對每個 revival (S, X)（G1）**

1. 讀 `S.lean_path`：有 `:= by sorry` body → 重寫成 `:= by apply <X_canonical> <;> assumption`
   （自動 import X module）。改寫後 build-verify；不過就還原 stub、S 留 shelved。
   無 sorry body（agent 手改 / 已 promote）→ refuse，留 link 給 operator。
2. 設 S terminal(`proved`) + propagate。下一圈可能撈到 S 的 parent strategy。

### root 完整性閘（§2 step 3 的核心）

root goal flip `proved` 後，在 post-proved gate 跑單一 integrity gate `verify.root_integrity_gate`。

**probe** — `axiom_probe(Problems.<p>.main, module=Problems.<p>.Root)`，唯一的 Lean elaboration 點（900s cap）。
lake serve worker 走完整 alias 鏈、缺 olean 的檔 on-demand elaborate（葉子 `L_*.lean` 在 proof 時已 warm；alias 脊柱
由 §4 step 3 的背景 warmer 暖好，正常情況 probe 不必再付 cold 閉包），同時抓兩件事：

- alias 改寫的 drift（compile error → Lean 印檔名 + 行號）
- 任何漏網 sorryAx（`rogue: [sorryAx]`）

**happy path**

- `set_integrity_verified(1)`
- `cleanup_cascade_backups`（Phase 6：root-proved 自動 enqueue Librarian 已退役——harvest
  一律由 Strategist `Ingest` 驅動）

> 這裡**不**寫 Library 檔、**不**退出 daemon —— Library 化交給 §3.5 的 async chain；退出由 §2 step 5
> （`all_problems_ingested && 無 Librarian 待辦`）判斷。

**rogue sorryAx**

1. `bisect_sorryax_source`：對每個 `succeeded` strategy 跑 `#print axioms`（depth 深的先），找第一個 scratch 含 sorryAx 的元凶
2. `rollback_cascade_chain`：從元凶往 root 走，逐層 `rollback_promote` 還原 sorry-stub —— culprit strategy `dead`/goal `open`、上游 strategy `proposed`/goal `attempting`。root 因此退出 proved（`integrity_verified` 清掉），下個 tick 重新 Backward 元凶 goal。**Phase 6**：若該題已 `Ingest` → 自動撤銷（清 `ingested_at`+sign-off）並 `librarian.un_harvest` 全自動下架（刪 Library 檔、退 INDEX section、清 lifecycle rows/fail counts、loud-list 跨題 dependents）

> empirical：41+ 次 cascade verify，0 次攔到 sorry / drift。唯一 caught sorryAx 案例（SG s378）發生在
> Backward leaf-bypass 的 submit time，不在 cascade。Mechanical-only 把零收益的 verify 全省掉，
> failure path 用 bisect 補回 attribution。

**幾個設計選擇**：

- **是 stage 而非 worker_kind**：純框架操作沒 LLM，不該佔 worker pool slot。早期把 Verify 當第三種 worker_kind、
  每輪佔一格 ~60s、無收益。
- **遞迴 max_iters=8**：深度 4 的題可能一輪連帶 4 層 strategy 全 promote；上限避免病態 case 卡住整個 tick。
- **單執行緒**：在主迴圈 sequential 跑，自然解掉 OR-race。
- **沒有 LLM 修復**：早期設計過「Step 1 失敗叫 LLM 修 patch」，實證 0 觸發 —— 鎖死 strategy 簽名 +
  Backward commit 前先 build 過已過濾掉絕大部分組裝錯誤。Step 1 真開始失敗再回頭加。

---

## 5. Spawn 前準備

### Context.md 編譯

每次 spawn 前，框架從 DB 編一份 `Context.md` 寫進 `.attempts/<pid>/`。**agent 看到的訊息都從這裡來**
（companion 檔只是備援，agent 常不主動讀）。三支編譯器，各管一類 pipeline：

| 編譯器 | 服務對象 |
|---|---|
| `compile_context` | Builder / Backward |
| `compile_forward_context` | Forward |
| `compile_strategist_context` | Strategist |

section 順序固定，每個 `_section_*` 不適用時回 `[]`、整段省略。

**`compile_context`（Builder / Backward）**，由上而下：

| # | section | 條件 / 說明 |
|---|---|---|
| 1 | BRIEF.md inline | FORBIDDEN_LEMMAS / strategic notes 都折進這裡 |
| 2 | KB lessons/antipatterns inline | 來源是 DB `kb_entries`（Model B、global-only、reflection 寫入）；1–2 是跨 spawn 不變內容，放最前讓 prompt-cache prefix 命中最大化 |
| 3 | Strategist directive | problem-level 常駐指令（每次 cold-start） |
| 4 | Strategist brief | 只在這條 pipeline 由 Inject 認可時 |
| 5 | Goal statement | — |
| 6 | Library available | domain-filtered（Builder/Backward 都有，**不是** Forward 專屬） |
| 7 | Strategy naming | Backward only：鎖死的 strategy 檔名/定理名 `s<sid>` + sub-goal slug 規則 |
| 8 | Parent goal & strategy | `origin='backward'` only |
| 9 | Mathlib lemmas | 來自過去 lake error |
| 9b | Candidate lemmas（pre-search） | target-1：per-node 預搜的排序候選（Mathlib/Library/in-problem、`#check` 驗過） |
| 10 | Proved siblings on this problem | pre-search 在場時由它取代（避免重複列同批 siblings） |
| 11 | Your previous progress note | timeout 留下的 `.drafts` 筆記（§6） |
| 12 | Your previous patch.lean | Builder only：上次未驗證的 patch |
| 13 | Goal history（umbrella） | Builder/Backward only，見下 |

**`compile_forward_context`（Forward）**：Strategist brief → Library inventory（同 problem 已證 lemma）→
Past Forward proposals → TREE inline → Manifest meta。

**`compile_strategist_context`（Strategist）**，由上而下：

1. Trigger
2. *(pending_review only)* Recent failed attempts ／ Existing strategies ／ Ancestor chain
3. Framework stalled（stall warning）
4. Current standing directive
5. Completed Inject batches
6. Pending reopen-promises — G2：只列「該 batch 已全部 outcome 落地、且 Strategist 還沒處理過」的 promise
7. Active goals
8. Recent decisions（failure replay）
9. TREE
10. Manifest meta

**Goal history umbrella**（`compile_context` 第 13 段，4 個 sub-section）：

| 標題 | 受眾閘 | 內容 |
|---|---|---|
| `### Direct attempts on this goal` | kind-agnostic | 本 goal 的直接嘗試（含 agent_declined） |
| `### Sibling decompositions that failed Verify` | Backward/None | sibling 拆解組裝失敗 |
| `### Strategies whose decomposition died` | kind-agnostic | 拆解死掉的 strategy |
| `### Sub-goals declined` | Backward/None | sub-goal 回報 infeasible / parent_needs_fix / shelved |

event 投影邏輯在 `Tooling/pipeline/events.py`（4 個函數 + `_NON_AGENT_REASONS` filter）。
空 bucket 整段省略；空 umbrella 連 `## Goal history` header 都不寫。設計史見 `docs/archive/goal_history_unified.md`。

> Playbook section 已退役（Phase 3，commit `5be9a33`）—— `Proved siblings on this problem` 是它的 grep-based 取代。

### Sandbox

agent cwd 鎖在 problem_dir，配合 `--add-dir` 與 read allow/deny：

- **cwd** = `Problems/<p>/`
- **`--add-dir`**：problem_dir、attempts_dir、`.lake/packages/`（若存在）、`Library/`（若存在）
- **讀允許**：cwd subtree、attempts subtree、整個 `.lake/packages/**/*.lean`、`Library/`
- **讀禁止**：其他 `Problems/<...>/`（別的 problem 的 sketch 也擋）
- **工具**：`Read` / `Write` / `Edit` / `Grep` / `Bash`，外加 `Bash(python -m Tooling.knowledge.loogle *)`（Mathlib lemma 搜尋）

### 預寫框架要鎖的檔

| pipeline | 預寫 |
|---|---|
| Builder | 不預寫，agent 自由改 `patch.lean`（即 parent goal 的 lean 檔） |
| Backward | 預寫 `patch.lean` skeleton：沿用 parent 的 `<kind> <slug> <binders> : <type>` 簽名（`_DECL_HEAD_RE` 解析 theorem/def/structure/class），改名 `s<sid>`、body `:= by sorry`。agent 只改 body，動到簽名會被偵測 |
| Forward | 不預寫，agent 自由寫 `new_<slug>.lean` |
| Strategist | 不寫 patch，輸出 `decision.json`（JSON array） |

---

## 6. Spawn 後的失敗 / 中斷處理

helper 在 retry loop 內看 rc 分支；失敗種類對應不同的 buffer / `.drafts` 行為。

### 6.1 普通失敗 retry（rc≠0 且 wall-clock ≥ 10s；或 rc=0 + parse-stage failure）

例：build 沒過、forbidden_lemma 命中、agent_no_annotation。

1. helper 把 `.attempts/` snapshot 進 pending_failures（reason / detail / artifacts）
2. 抽 lake stderr / parse error 進 detail，下一圈當 retry_context inline 進 prompt
3. Backward 額外：parse_fn 內 unlink 寫進 `proofs/` 的檔（Builder backup 已 restore）
4. 下一圈 cold→warm（同 sid + `--resume`），帶上次 detail
5. budget 用盡 → `exhausted`；否則 proved/success → return
6. dispatcher 在 pipelines INSERT 後 flush pending_failures（每筆 → 一條 dead_attempt）
7. cascade 對 `exhausted` 做轉移，≥ SHELVE 才 shelved

普通失敗**不寫 `.drafts/`**：同個 pipeline 內，session 記憶 + retry_context 已是接續媒介。跨 pipeline 的進度筆記只在 timeout 路徑留（§6.2）。

**Reflection callback**（`_reflection.py`）：每次 helper 完成（outcome ∈ {proved, success, exhausted}，或 decline
directive：agent_declined / agent_infeasible / parent_needs_fix / agent_shelved），在同 worker thread 內 spawn 第二個
claude（`--resume <sid>`，**120s cap**），讓 agent 對自己這條 pipeline 寫一行 lessons 進 `Problems/<p>/LESSONS.md`。
純 best-effort，不影響主 pipeline outcome。infra failure（spawn_fast_fail / quota / missing_dep / goal_no_longer_open /
moot）不觸發。有 kill switch（`lessons.reflection_enabled`）+ per-problem mutex。

### 6.2 Timeout（rc=124，process 被 SIGKILL）— postmortem

主 spawn 超過 **900s**（`spawn_timeout_sec` / `WORKER_TIMEOUT_SEC`）被 SIGKILL。session memory 還 pinned 在 disk，
但 process 已死、沒機會把當下思考寫成檔。

1. 主 spawn timeout、SIGKILL
2. helper 呼叫 `postmortem_fn(sid)`：`claude --resume <sid>` + 短 prompt（`<kind>_postmortem.md`）——「你被中斷了，用 150 字寫下方向 / 卡在哪，存進 `_progress.md`」，限時 180s（`POSTMORTEM_TIMEOUT_SEC`）
3. agent 用 session 記憶寫 `.attempts/<pid>/_progress.md`
4. helper buffer `agent_timeout` → return `exhausted`（不再續 retry）
5. wrapper 把 `_progress.md` 複製到 `Problems/<p>/.drafts/<kind>_g<gid>.md`
6. dispatcher flush pending_failures（含 timeout 那筆）
7. `WorkArea.__exit__` 刪 attempts_dir
8. cascade 對 `exhausted` → ≥ SHELVE 才 shelved

下次 dispatch（fresh pipeline、新 sid）：編 Context.md 時讀 `.drafts/<kind>_g<gid>.md`，inline 成
「## Your previous progress note」。agent 看到自己的回顧筆記，在 fresh session 繼續做。

> **為什麼 timeout 強制 exhaust 不續 same-session retry**：timeout 表示思考路徑卡死，同 session resume 會撞同卡點。
> `.drafts/` 持久化的整個目的就是給 cold restart 用。
> **postmortem 自己也死**：180s cap + 任何 rc≠0 都當 best-effort 失敗（next pipeline 直接 cold start，不比沒 postmortem 差）。

`.drafts/` 在下次 pipeline 成功 commit 時自動清掉；`exhausted` 才 persist。

### 6.3 Spawn fast-fail / quota_exhausted / missing_dep — infra 噪訊

三種走相同處理（**不耗 budget、不寫 dead_attempt、設 cooldown**）：

| reason | rc | 意義 |
|---|---|---|
| `spawn_fast_fail` | rc≠0 且 wall-clock < 10s | claude.exe 啟動 ~3–5s、最快的 legitimate 失敗也要一個 model turn；< 10s 幾乎肯定是 infra（crash / cwd 失效 / network down） |
| `quota_exhausted` | 126 | provider rate limit / quota 耗盡 |
| `missing_dep` | 127 | CLI 二進位缺 |

1. helper 偵測 rc → 早返 `failed`，不 buffer 自身、不耗 budget（prior iter 的 pending_failures 仍 attached，會被 dispatcher flush）
2. cascade：is_infra → return（不 ++ attempts、不寫 final dead_attempt）
3. dispatcher 給 `(target_id, kind)` 設 30s cooldown（`SPAWN_COOLDOWN_SEC`）
4. 只有 spawn_fast_fail：`consec_fast_fails` +1；≥ 10（`CONSEC_SPAWN_FAIL_LIMIT`）→ daemon 退出 rc=2（claude.exe 持續壞、需人工介入）。quota / missing_dep 不進 CONSEC（quota 自會 recover、missing_dep 是 operator-fix）；任何非 fast-fail outcome 重置 CONSEC 為 0

cooldown 期內 `bfs_refill` 跳過該 (target, kind)，queue 不 burst-retry。`.attempts/<pid>/_spawn.stderr` 留 stderr tail 供 forensic。

---

## 7. 關鍵常數

| 常數 | 值 | 出處 |
|---|---|---|
| `dispatch.pool`（= gateway workers） | 4 | `Asterism.yaml` / config.py |
| `BUILDER_THRESHOLD`（升 Backward） | 3 | dispatcher.py |
| `SHELVE_THRESHOLD`（shelve） | 8 | dispatcher.py |
| 主 spawn 硬上限（SIGKILL） | 900s | `spawn_timeout_sec` |
| postmortem cap | 180s | `POSTMORTEM_TIMEOUT_SEC` |
| reflection cap | 120s | `_REFLECTION_TIMEOUT_SEC` |
| spawn_fast_fail 門檻 | 10s | `SPAWN_FAST_FAIL_SEC` |
| spawn cooldown | 30s | `SPAWN_COOLDOWN_SEC` |
| 連續 fast-fail 上限 | 10 | `CONSEC_SPAWN_FAIL_LIMIT` |
| Strategist routine interval | 60 min | `strategist.interval_min` |
| verify housekeeping 迭代上限 | 8 | `max_iters` |
| Librarian chain 重試上限 | 2 | `LIBRARIAN_MAX_CHAIN_RETRIES` |

---

## 8. 設計取捨速查

| 決策 | 為什麼 |
|---|---|
| Context.md 必看訊息 inline、companion 只當備援 | 教訓：agent 不會主動讀 companion |
| Timeout 走 postmortem 而非邊想邊存 | 主任務不被 deliverable 維護分心 |
| 進度筆記只留最近一次（overwrite） | cold restart agent 看到的是最新一次即可 |
| Pipeline = session lifecycle、retry 收進 pipeline 內 | sid 是 local var，移除跨 pipeline 攜帶機制 |
| 編譯統一走 LSP gateway（`verify_file`）而非 cold lake | 省每次 5–15s 啟動；warm worker 共用 olean |
| Verify inline、不佔 worker slot | 純框架操作沒理由佔 LLM pool 格子 |
| Verify-time LLM 修復被取消 | 實證 0 觸發，不為罕見事件付架構成本 |
| auto-prune / whole-root library.promote 退役 | 前者 blast radius 太大改 operator opt-in；後者由 async Librarian chain 取代 |
| Librarian dedup 改機械 keep-all | 限縮到 root live 閉包就夠乾淨，省一次 agentic 判斷 |
| OR passive（cap=1）不 eager fanout | 強模型下純粹浪費 token |
| Dedupe 用 apply-probe（Lean 知道 α/β/η/defeq） | 字串比對命中率低；schema 零改動 |
| Phase 1 用 `by hint` + 寫回精確 winner | 接 mathlib `register_hint` curated set；artifact 留具名 tactic |
| Spawn fast-fail 不算 agent error | infra 問題不該燒 goal 預算 |

---

## 9. 跨參考

- 系統靜態形狀（角色、不變量、DB schema、cascade 規則完整版）：`docs/architecture.md`
- 失敗 reason × 觸發 × cascade × event 完整對照：`docs/failure_modes.md` §2
- Context.md `## Goal history` umbrella 設計史：`docs/archive/goal_history_unified.md`
