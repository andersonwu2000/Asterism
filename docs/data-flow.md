# Asterism — 資料流向

本檔講**動態**：dispatcher 一輪 tick 怎麼跑、每條 pipeline 的流程、跨 pipeline 共用的機制。
靜態形狀（角色、不變量、schema）見 `docs/architecture.md`；失敗語彙的完整對照**只在**
`docs/failure_modes.md` §2，本檔不重複。

> 原寫於 2026-05-06；2026-07-29 對照代碼全面重寫（Formalizer 合併、research mode、常數校正）；
> 2026-08-02 補討論小組樹（v35、席位 per-group）。
> 文中數值皆為**程式預設**；本 repo 的覆寫在 `Asterism.yaml`，以它為準。

---

## 0. 先讀：兩個全域慣例

**編譯驗證走 LSP gateway，不是 cold `lake build`。**
所有 pipeline 的 elaborate / build 驗證都打常駐的 LSP gateway warm worker（`lake serve`），
省掉每次 5–15s 的 cold 啟動。少數例外**刻意** cold：dedupe 的 apply/isDefEq probe、每個
problem 首次 dispatch 前的 Defs/Root pre-flight、Librarian 的異閉包 decl gate / 最終
warn-gate / import-swap 後 rebuild-gate（warm slot 只服務同閉包整檔 gate）。

**`dispatch.pool == gateway workers`，1:1 綁定 + own-slot 紀律（#118）。**
worker 池大小等於 gateway 後端數、一起伸縮（實際格數再扣 RAM clamp 與 serve UI 保留的
`gateway.interactive_slots`）。pipeline 每次 spawn 前 `/register` claim 一格，生命週期內
的驗證都打**自己這格**（`verify_in_session` 帶 session token；共用分派在
`_axiom.verify_on_own_slot`，無 token 時 fall back `verify_file`）。`verify_file` 是
**borrow** 入口（gateway 挑格、會踢掉該格 warm 內容），只給非-pipeline context 用：主線程
housekeeping（G1 revival、root integrity gate）、operator CLI、以及 spawn 前的框架 probe
（hint 前置、skeleton 簽名、intake 前驗證）。borrow 挑格 unclaimed 優先。

---

## 1. 三層儲存

| 層 | 位置 | 壽命 | 用途 |
|---|---|---|---|
| **暫存** | `.attempts/<pipeline_id>/` | 一次 spawn | agent 工作目錄；結束無條件 `rmtree` |
| **跨 spawn** | `Problems/<p>/.drafts/<kind>_g<gid>.md` | 該 goal 證完前 | timeout 後留給下次的進度筆記 |
| **永久** | DB + `proofs/L_*.lean` + `_strategy_s*.lean` + `Root.lean` | 與 problem 同壽 | 單一真實來源（SoT） |

agent 寫進 `.attempts/<pid>/` 的所有東西（不論成敗），在 `rmtree` 前先打包進
`dead_attempts.artifacts`。**DB 永遠是 SoT。**

---

## 2. 一輪 dispatcher tick

主迴圈每輪依固定順序跑：

| # | 步驟 | 做什麼 |
|---|---|---|
| 1 | **cascade** | 收割上一輪完成的 pipeline outcome，套 goal/strategy 狀態轉移（詳 `failure_modes.md` §2） |
| 2 | **verify housekeeping** | 組裝 sub-goal 全 proved 的 strategy、寫 alias 進 parent；跑 shelved-revival（§4） |
| 3 | **post-proved gate** | root 剛 flip proved 的 problem：修 drift → root 完整性驗證 → 刷 TREE（§4 末段） |
| 4 | **librarian refill** | opt-in 且已 Ingest 的 problem 排 Library 化工作（§3.5） |
| 5 | **exit check** | `all_problems_ingested` ∧ 無 Librarian 待辦 ∧ 無 outstanding harvest → daemon 退出 |
| 5b | **quota-wait gate** | 訂閱額度確認耗盡 → 睡到 resets_at、暫停一切 spawn（DB 側 trigger 照跑；budget 鐘扣除等待時間） |
| 6 | **bfs refill** | open goal 一律排 `Formalizer`；`attempts ≥ SHELVE_THRESHOLD` 的改送 strategist review、不派工 |
| 7 | **strategist triggers** | 排 routine（T1）/ stall（T4）喚醒；v35 起**席位 per-group**（`groups_needing_t1` / `groups_stalled`、queue 列 `target_kind='Group'`；legacy Problem 列仍認）；wake 只投給 `problems.state='active'`（WAKE_LEGALITY） |
| 7b | **reconcile_stuck_states** | per-tick 安全網：孤兒 pending_review / NULL-outcome Inject 修復 |
| 7c | **lease sweep** | 釋放 owner 已死**或**逾 TTL（6h）的 leased queue row（Windows 會重用 PID，雙判準） |
| 8 | **spawn** | 有空格就 pop queue、派 pipeline 進 worker thread |

tick 尾端另有：`--once` 退出、idle 退出（無 in-flight、queue 空、無 open goal、無 ready
strategy）、週期性 TREE.md 重繪、budget 到期退出。daemon 也會偵測 source/config 指紋漂移，
drain 後 spawn 後繼 daemon 換代（`dispatch.handoff_on_code_change`）。

### Step 8 — spawn 細節

**v17 起 pop = lease claim**：row 標 `owner_pid`+`leased_at` 而非刪除（並發 dispatcher 搶
不到同一 row；lease row 對去重查詢照樣算「在 queue」），pipeline 結束才 `complete_queue_row`
刪除。pop／flush／startup 清理都按 daemon `--scope` 過濾。**NL-first 閘**：gateway 未 warm
時只 pop 非-Lean kind（Strategist/Scholar 先走，Lean 工作留在 queue）。

pop 到 spawn 之間依序：

1. 3-tuple `(target_id, kind, decision_id)` 去重（同 batch 的 mint siblings 靠 decision_id 區分、可並行）
2. 跳過 quota cooldown 中的 kind
3. 已 Ingest 的 problem 的 Strategist row 直接丟棄（stale）
4. **lazy verify gate**：該 problem 本次 daemon run 首次 dispatch，先付一次 `lake build Defs+Root`（~5–15s）；失敗就 quarantine
5. `pool.submit(_run_pipeline, ...)` 進 worker thread

> 活的 queue kind 只有四種：`Strategist` / `Formalizer` / `Scholar` / `Librarian`。
> `Builder`/`Backward`/`Forward` 是合併前的 legacy row 名，dispatcher 仍認得、同樣路由。

---

## 3. Pipeline flows

### 3.0 共同骨架

**一條 pipeline = 一個 claude session 的完整 lifecycle**（含 retry），收在
`Tooling/pipeline/_retry.py` 的 `run_with_session_retries`。outcome 五種：
`proved` / `success` / `failed` / `exhausted` / `moot`。

**入場**：預寫框架要鎖的檔（§5）→ **intake**（fresh 短 session 寫 `intake.json`：
proceed / decline；decline 詞彙只有 `no_nl_correspondence` 與 `unprovable`，後者必附反例
note、否則 fail-open 放行）→ proceed 才跑 presearch + 編 Context.md。intake 的 session
接著被 work loop resume（continuation），不浪費。

**retry loop（最多 budget 圈；budget = SHELVE_THRESHOLD − goal.attempts）**

每圈先 cascade re-check（goal 已終態 → `moot`），再 spawn，依 rc 分支：

| rc | 意義 | 處理 |
|---|---|---|
| 0 | 正常返回 | `parse_fn` → terminal 就 return；非 terminal failure → buffer + 下一圈 warm resume |
| 124 | timeout（SIGKILL） | 先 salvage parse 一次；不成再 postmortem 寫 `.drafts/` → `exhausted`（§6.2） |
| 125 | stale session（僅 warm） | 原地重 mint sid + cold 重 spawn，不耗 budget |
| 128 | thinking-trap watchdog | fresh-sid takeover 續跑，不耗 budget（reason `agent_stuck_thinking`） |
| 129 | daemon 關閉 | 收尾 reason `daemon_shutdown` |
| 126 / 127 / fast-fail | infra | 早返 `failed`，不耗 budget、不 buffer（§6.3） |

**收尾**：dispatcher 寫 pipelines row → flush 累積的 pending_failures（每筆一條
dead_attempt）→ `cascade_one` 套狀態轉移 → 清 `.attempts/`；成功 outcome 才清 `.drafts/`。

容易誤解的點：

- **attempts++ 是即時的**（每圈失敗當下），dead_attempt row 延到 flush 才寫；daemon 中途
  被 kill 會讓 attempts 多一筆（帳面 drift、明文接受）。
- **`.drafts/` 清除條件依 kind**：成功 token（`proved`/`success`）與 `moot` 清；
  `failed`/`exhausted` 保留給下次 cold restart。

**Strategist Inject 例外**：pipeline 帶 `decision_id` 時 budget gate 完全 bypass（budget
給滿、不查 attempts 上限）——Strategist 看完 failure replay 仍下指令，框架不二猜；唯一
守住的是 goal status 已終態則 `moot`。收斂責任在 Strategist 的 ConfirmShelve 紀律。

---

### 3.1 Formalizer — goal job（prove / split）

對一個 goal 決定「直接證」或「拆解」，agent 在同一 session 內自主選擇。OR-aware：每條
strategy 用隔離檔名（scratch `_strategy_s<sid>.lean`、定理名 `s<sid>` 框架鎖定），parent
的 `lean_path` 不動、留待 §4 Verify 勝出時改寫。

**hint 前置（零 spawn）**：`goal.attempts == 0` 時先把 strategy skeleton 的 body 換成
`by hint` probe——Lean 跑 mathlib `register_hint` 註冊的 tactic 集，命中就把具名 winner
寫進 `patch.lean`、走與 agent patch **完全相同**的 commit 閘；失敗無聲落入正常流程。

**入場**：INSERT 新 strategy 拿 fresh `s<sid>`（不重用死 strategy）→ 從 parent stub 算
skeleton（沿用宣告 kind、改名 `s<sid>`、body sorry；stub 抽不出簽名時用 declInfo oracle
的 `ppSignature` 重建，再不行才 `parent_stub_not_decomposable`）→ 預寫 `patch.lean`。

**parse_fn（每圈一次）**：

1. bail 偵測：`_progress.md` 有內容 + patch 未動 + 無 `new_*.lean` → `agent_bailed`
2. glob `patch*.lean` → 缺檔 `parse_proposal_fail`
3. 檔頂 `-- decline:` 分流：`unprovable` / `return_to_parent` / `shelve` / `needs_decomposition` / `no_nl_correspondence`
4. 簽名未被改（比對 skeleton）→ 否則 `patch_signature_mismatch`
5. **leaf-bypass**：0 個 `new_*.lean` 且 body 非 sorry → 當 0-subgoal strategy：forbidden
   grep + 單檔 verify + 公理閘 + race guard → 過就 commit
6. `forbidden_lemmas` grep（patch + 所有 `new_*.lean`）
7. sub-goal slug 驗證（lowercase、≤60 chars；撞名 auto-suffix）
8. **dedupe**：batch probe `apply @<canonical> <;> assumption` 比對候選池（ancestor /
   sibling orphan / 跨 branch proved / 同題 disproved），前置 slug-pattern 預檢與
   no-progress 守門。命中 alive → 寫 alias 並 build-verify（不過就退回開新 sub-goal）；
   命中 disproved → 整批 abort
9. 搬檔到 `proofs/` + 自動注入 import（agent 常忘）
10. cite gate（decomp 路徑允許 auto-link 收進可平行的 open siblings）
11. scratch 不得殘留 sorry → `patch_body_contains_sorry`
12. `verify_file` batch（subs + scratch）→ 失敗 unlink + `lake_build_error`
13. race guard：goal 已非 open/attempting → unlink + `goal_no_longer_open`
14. INSERT goals + strategy_subgoals；sorry-free / dedupe-hit 的 sub 直接 proved
15. UPDATE strategy → `outcome='success'`

結束時 `outcome != 'success'` → strategy 標 dead（infra reason 或空 row 則直接 DELETE）。
各 failure_reason 的 cascade 語意見 `failure_modes.md` §2。

---

### 3.2 Formalizer — mint job

Strategist 用無 target 的 `Inject` 派（shape-derived），產一條新 toolkit lemma 進池。
`target_kind='Problem'`；同 batch 的多條 mint 以 decision_id 區分、可並行。lemma kind：
`theorem` / `def` / `structure` / `class` / `inductive` / `instance`（具名）。

流程（`forward.py`；retry budget = `FORWARD_RETRY_BUDGET`）：

1. LSP edit-mode 針對**固定檔** `new_forward.lean`（框架預寫 seed scaffold），agent 就地編輯
2. intake 同 goal job（decline 兩詞彙）；work-turn decline `-- decline: library_sufficient` → `agent_declined` 終態
3. `extract_forward_metadata`：slug / rationale / kind / sorry_free；缺欄或 kind 不認得 → `parse_rejected`；`inductive` 帶 sorry 直接拒
4. auto-prepend imports → self_verify（`verify_file` probe；build error → `forward_no_new_goal` + retry_context）
5. **Defs 語彙保護**：non-theorem kind 的 slug 撞 Manifest statement 詞彙 → 拒、導向 `RequestUserAmend(Defs.lean)`
6. sorry-bearing 且無型別註記 → declInfo oracle 補簽名，補不到才拒
7. **dedupe 三分支**：同題 alive/parked 孿生 → `reuse`（Inject 重指到既有 goal、cascade-shelved 的復活+detach，不新建）；命中 proved → 落地 alias；其餘正常 commit
8. `commit_forward_lemma`：搬到 `proofs/L_<slug>.lean` + INSERT goal（sorry_free → proved、否則 open；一律 `detached=1`）
9. shelved_link（G1）：反向 probe 同題 shelved goals，命中先記 link，等 X proved 時 §4 補寫 alias
10. 無條件回填 decision 的 `produced_goal_id`；proved 時直接 propagate inject outcome

失敗不動任何 goal 的 attempts（mint 是 goal-less 的）；infra 失敗 re-enqueue 同
decision_id。防亂提雙線：dedupe 擋重複、Strategist 自己在 failure replay 看結果調整 brief。

---

### 3.3 Strategist

`target_kind='Group'`（v35 起席位屬於**組**；legacy `Problem` 列仍認、映射到頂層組）。
**trigger 三種**（spawn 時判定，優先序 routine > inject_batch_done > pending_review >
stall）：

| trigger | 何時 |
|---|---|
| `routine` | 離上次 routine commit ≥ `strategist.interval_min`（預設 120 min；鐘住 `groups.last_routine_at`、per-group；problem 級舊鐘 dual-write 中、待 Stage D 退役）。wake 第一階段先做 belief audit |
| `inject_batch_done` | 某 batch（Inject/Delegate 同吃一個批次帳）全部 outcome 落地；**或 spawn 時該組為 structural stall**（fresh 組 / deadlock / root 已證待 Ingest 都算「empty batch done」；牆態偵測 per-group、`is_group_stalled`） |
| `pending_review` | goal 轉 `pending_strategist_review`（decline 上交或 attempts 達標）；路由到**擁有那顆 goal 的組** |

所有 wake 先過 `problem_accepts_wake`：`problems.state` 非 `active` 一律拒收。
同 problem 的多個組可各自持有席位；`_strategist_inflight` 以組為單位去重。

**提案包 + Adversary 迴圈**（research mode，一律開啟）：

1. spawn 產 `decision.json`（JSON array）＋ 非豁免批必附 `proposal.md`（`# Title` /
   `## Argument` / `## Proof` / `## Roadmap`；豁免 kind = {FetchPaper, RequestUserAmend,
   Noop}；非 endgame 批必附 ≥1 實驗 = Inject / AttemptDisproof）
2. 機械檢查（schema、cross-decision invariant、包形狀）不過 → 同 session 修訂
3. 過機械檢查 → **Adversary**：每輪 fresh sub-spawn，在硬隔離投影目錄審提案包、產
   per-criterion `verdict.json`，pass/rebut 由框架推導；rebut → 同 session 帶批評修訂
4. 機械錯誤與 rebuttal **共用**輪數上限 `strategist.verify_retry`（預設 6）；到頂仍被
   反駁 → `strategist_proposal_rejected`：提案+批評存 `programme_revisions`
   （status='rejected'）、session 拋棄、下一 wake 只帶一行紀錄盲重推、target cooldown
5. 通過 → commit 決策批 + `programme.record_pass`（重繪 `PROGRAMME.md`）

**commit_decisions 副作用**（決策九種）：

| decision | 動作 |
|---|---|
| `Inject`（無 target） | enqueue mint（Formalizer/Problem）+ decision row（寫 batch_id） |
| `Inject`（有 target） | 強制 reopen + 必要時 detach + un-stall 上游 strategy + enqueue Formalizer |
| `ConfirmShelve` | goal terminal(shelved) + propagate |
| `EmitDirective` | 設 problem 常駐指令 |
| `RequestUserAmend` | 寫 `.proposed_<file>` + problem 轉 `awaiting_human` |
| `MarkDeliverable` | 標 deliverable（anchor+claim） |
| `Ingest` | **頂層組**：蓋 `ingested_at`（唯一終態；root 在場未 proved 則框架拒絕）；library:true 再走 sign-off/harvest。**子組**：輕量版——組標 `delivered`、喚醒父組，不碰簽核/harvest/problem FSM；閘=錨 proved（救援形狀）或本組標過 ≥1 deliverable（無錨形狀） |
| `FetchPaper` | enqueue Scholar（payload 帶 query/reason；outcome 由 Scholar 回填） |
| `AttemptDisproof` | 框架**機械**否定手術鑄 ¬P goal（不讓 LLM 改寫語句、防 strawman） |
| `Delegate` | INSERT 新組（charter=brief）+ 立即排新組席位；帶 target 時錨轉 `attempting`。outcome 保持 NULL 至子組終態——與同批 Inject 共用批次帳、都終態才喚醒父組 |
| `ReturnToParent` | 子組限定：組標 `returned`、救援錨落 `shelved`（含級聯）、父組 Delegate outcome=`failed:returned`、喚醒父組 |
| `Noop` | 只 INSERT audit row |

收尾：batch 層 touch `last_strategist_at`（routine 另 touch `last_routine_at`、才 re-arm
時鐘）；routine wake 另可經 `kb_curation.json` sidecar 增修全域 lessons（上限 10 ops）。

---

### 3.4 Scholar

`FetchPaper` 決策派出的單階段 spawn：用 `Tooling.papers.search` / `papers.fetch` 在白名單
來源找副本，成功 → 論文入 `Papers/<shelf-id>/` + 綁定 `problem_papers`（`paper_fetched`）；
找不到可抓副本 → `paper_unfetchable`，精確請求寫進 decision `outcome_detail` 交人工通道。

---

### 3.5 Librarian

把已證 problem 收成 mathlib 形狀的 `Library/`。自動啟動條件：Manifest `library: true` ∧
已 Ingest ∧ 尚無 harvest 產物；sign-off pending 時一切自動路徑暫停。

鏈式 `dedup → classify → migrate → cleanup → bridge`，work-kind 由 `library_decls`
lifecycle 推出、tick 層每次成功後重新 derive 直到排空。`migrate`/`cleanup` 以整檔為平行
單位。

| 步驟 | 形式 | 做什麼 |
|---|---|---|
| **dedup** | 純機械 | 限縮到 harvest 目標的 live 使用閉包，標 `keep → deduped` |
| **classify** | one-shot JSON spawn | agent 給檔案佈局+順序；框架 SCC-merge + toposort 修正 |
| **migrate** | LSP + commit-retry | 一次寫整檔 decls → commit gate → `migrated` |
| **cleanup** | LLM 多段 + 機械收尾 | per-file 精修（drop/merge/simplify/audit/rename/import-min）；零-warning 硬閘 + post-rewrite 公理閘 → `cleaned`/`dropped` |
| **bridge** | 無 agent | Gate B 整體意義驗證，PASS 回填簽名 + 標 `library_bridged_at`、終止 chain |

**commit gate（每次 migrate；cleanup 收尾與 deliverable bridge 共用）**：Gate A import
閉包 ⊆ {Mathlib, Library, Init, Std, Batteries, Lean}；整檔 0 error 0 sorry；per-decl
`#print axioms` ⊆ whitelist；Gate D 對 `def` 做 `rfl` def-equivalence；任何 `axiom` 宣告
hard-fail。失敗 rollback、chain 卡在該檔，連續失敗超過 `LIBRARIAN_MAX_CHAIN_RETRIES`
（=2，即第 3 次）→ STALLED。

**post-rewrite 公理閘（cleanup 收尾）**：cleanup 的 LLM 改寫段是 migrate 閘之後唯一能改
公理集的地方（例：`by native_decide` 拉進 `Lean.ofReduceBool`），收尾對**最終文本**重跑
per-decl 公理檢查，不過 → `librarian_axiom_violation`、該檔留 `migrated` 重試。

**Gate B（bridge、「定海神針」）**：從 Library 重新推導出原始 root（Defs-free），
statement-pin + import 閉包 + build + axiom whitelist。marker 存在 = Library 真的能重證
原題。deliverable 題（無 root 可重推）改為：builds-only + 對每個 harvested 檔最終文本跑
per-decl 公理閘。

> 三道 Gate：**A** import 閉包、**B** root 重推、**D** def-equivalence。沒有 Gate C。

---

## 4. Verify housekeeping

每輪 tick 在 cascade 之後跑，**純框架、無 LLM、單執行緒**。每圈撈兩種待辦（最多
`max_iters=8` 圈）：

- **ready strategies**：`proposed` ∧ scratch 非空 ∧ parent 不在終態 ∧ 所有 sub-goal proved
- **revivals（G1）**：shelved goal S 的 `alias_target_id = X` 且 X 已 proved

**對每條 ready strategy**：parent `.lean` 原子改寫成 alias（import strategy module +
`def <parent_slug> := @...s<sid>`；簽名鎖死保證 type 相符、純字串模板）→ strategy
`succeeded`、parent `proved`（樂觀標）、siblings `superseded`→ 背景 olean 暖機
（`OleanWarmer` 獨立 thread 跑 cold build，不佔主線程也不佔 LLM pool；kill switch
`verify.olean_warm`）。parent 可能是更上層的 sub-goal，下一圈連鎖撈到。

**對每個 revival (S, X)**：S 的 sorry body 重寫成 `apply <X> <;> assumption` + build-verify
（不過就還原、留 shelved）→ S 轉 proved + propagate。

### root 完整性閘（§2 step 3 的核心）

root flip proved 後跑單一 integrity gate：`axiom_probe(Problems.<p>.main)`（900s cap、
唯一一次完整 elaboration），同時抓 alias 鏈 drift 與漏網 sorryAx。

- **happy path**：`set_integrity_verified(1)` + 清 cascade backup。不寫 Library 檔、不退出
  daemon（Library 化與退出各由 §2 step 4/5 決定）。
- **rogue sorryAx**：`bisect_sorryax_source` 找元凶 strategy → `rollback_cascade_chain`
  逐層還原（root 退出 proved、下個 tick 重拆元凶）；該題已 Ingest → 自動撤銷 + Librarian
  un-harvest 全自動下架。

> 實證 41+ 次 cascade verify 0 攔截——所以 per-level verify 是純機械 alias rewrite、不逐層
> elaborate；root gate 是 false-proved 的最後修正網，實務極少 fire 但不可拆。

---

## 5. Spawn 前準備

### Context.md 編譯

每次 spawn 前框架從 DB 編一份 `Context.md`。**agent 看到的訊息都從這裡來**（companion 檔
只是備援）。三支編譯器：`compile_context`（Formalizer goal job）、
`compile_forward_context`（mint）、`compile_strategist_context`。section 不適用時整段省略。

**goal job**（`compile_context`），由上而下：BRIEF inline → KB lessons（跨 spawn 不變、
放最前吃 prompt cache）→ paper index → **Programme `## Proof`**（NL-first 前提）→
directive → Strategist brief（Inject 時）→ goal statement → Library available →
strategy naming → parent goal & strategy → mathlib lemmas（過去 lake error）→
Candidate lemmas（pre-search；在場時取代 proved-siblings 段）→ **catalog 指標**（精確
statement 在 `CATALOG.md` companion）→ 上次進度筆記 / 上次 patch → Goal history
（umbrella、4 sub-section；投影邏輯在 `pipeline/events.py`，設計史
`docs/archive/design/goal_history_unified.md`）。

**mint**（`compile_forward_context`）：brief → Library inventory → 過去 mint 提案 →
active goals → Manifest meta → paper index。（無 TREE、**無 Programme 段**。）

**Strategist**（`compile_strategist_context`）：trigger →（pending_review 才有：失敗
replay / 既有 strategies / ancestor chain）→ stall warning + Ingest availability →
disproof guidance → **Programme**（現行 rev 全文 + Adversary reservations + 上輪 rejection
一行）→ directive → plan note（`.drafts/strategist_plan.md` 私人筆記）→ 已完成 Inject
batches（帶 landed decl 名）→ pending reopen-promises → active goals → recent decisions →
TREE → catalog → Manifest meta →（routine 才有：KB curation surface）。

### Sandbox

agent cwd 鎖在 problem_dir：

- **`--add-dir`**：problem_dir、attempts_dir、`.lake/packages/`、`Library/`、`Papers/`
  （各自存在時）。**Adversary 例外：全部清空**，trust boundary 只剩投影目錄
- **讀禁止**：其他 `Problems/<...>/`；operator 狀態（`~/.claude/projects/**` deny +
  auto-memory 關閉 + `spawn_guard` PreToolUse 白名單 hook）
- **工具**：`Read` / `Write` / `Edit` / `Grep` / `Bash`，Bash 只白名單
  `python -m Tooling.knowledge.loogle` 與 `python -m json.tool`（Scholar 另加
  `papers.search` / `papers.fetch`；spawn env 注入 repo root 到 `PYTHONPATH`）；LSP MCP
  工具（apply_edit / goal_at / errors_at / validate_file）
- **spawn flags**：`--setting-sources ""`（CLAUDE.md 一律不載入）、user 檔
  （Manifest/Defs/Root/PROGRAMME）Write+Edit 全 disallow

### 預寫框架要鎖的檔

| job | 預寫 |
|---|---|
| Formalizer goal job | `patch.lean` = strategy skeleton（簽名鎖死、agent 只改 body） |
| Formalizer mint | `new_forward.lean` seed scaffold（imports + namespace、就地編輯） |
| Strategist | 不寫 patch，輸出 `decision.json`（+ `proposal.md`） |

---

## 6. Spawn 後的失敗 / 中斷處理

### 6.1 普通失敗 retry

（build 沒過、forbidden_lemma、無 annotation 等）helper 把 snapshot buffer 進
pending_failures、抽 stderr 進 detail，下一圈 warm resume 帶 retry_context。budget 用盡 →
`exhausted`。普通失敗**不寫 `.drafts/`**——session 記憶 + retry_context 已是接續媒介。

**Reflection callback**：helper 完成（成功、exhausted、或 decline directive）後在同
thread spawn 第二個 claude（`--resume`、120s cap）對這條 pipeline 寫一行 lesson 進
`LESSONS.md`。best-effort、infra failure 不觸發、kill switch `lessons.reflection_enabled`。
另有獨立的 framework feedback tail step（`feedback.enabled`）與 infra 死因筆記通道。

### 6.2 Timeout（rc=124）

主 spawn 超過 `dispatch.spawn_timeout_sec`（預設 900s）被 SIGKILL。處理順序：

1. **salvage parse**：agent 可能已在 disk 留下 valid 輸出——直接跑一次 `parse_fn`，得到
   terminal success/decline 就照常收（timeout 也能算成功）
2. salvage 不成且 watchdog 判定 thinking trap → fresh-sid takeover 續跑（不 exhaust）
3. 否則 **postmortem**：`claude --resume` + 短 prompt（180s cap）「用 150 字寫下方向/卡
   點」存 `_progress.md` → 複製到 `.drafts/<kind>_g<gid>.md` → `exhausted`（不續 retry）

下次 dispatch（fresh pipeline）編 Context 時 inline 成「## Your previous progress note」。

> timeout 強制 exhaust 的理由：思考路徑卡死、同 session resume 會撞同卡點；`.drafts/` 的
> 目的就是給 cold restart。postmortem 自己死了也只是 best-effort 損失。

### 6.3 Infra 噪訊（不耗 budget、不寫 dead_attempt）

五種 `PROVIDER_INFRA_REASONS`：

| reason | 觸發 | 處置 |
|---|---|---|
| `spawn_fast_fail` | rc≠0 且 wall-clock < 10s | 30s target cooldown；連續 10 次 → 先問 usage endpoint，確認 quota 就轉 quota-wait，否則 daemon 退出 rc=2 |
| `quota_exhausted` | rc=126 | **per-kind 指數退避**（30s×2ⁿ、cap 600s）+ flush 同 kind queue + 可進 quota-wait |
| `missing_dep` | rc=127（CLI 缺） | 30s cooldown、operator-fix |
| `gateway_unreachable` | HTTP transport 失聯 | 30s cooldown；連續 8 次 → daemon 退出 rc=2 |
| `transient_timeout` | RPC 超時（slot 競爭） | 30s cooldown、**不進任何 CONSEC**（健康過載非死亡） |

cooldown 期內 bfs_refill 跳過該 (target, kind)；`.attempts/<pid>/_spawn.stderr` 留 forensic。

---

## 7. 關鍵常數（程式預設；覆寫看 `Asterism.yaml`）

| 常數 | 預設 | 出處 |
|---|---|---|
| `dispatch.pool`（= gateway workers） | 4 | config.py（另受 RAM clamp 與 interactive_slots 扣減） |
| `SHELVE_THRESHOLD` | 8 | `dispatch.shelve_threshold`（達標轉 strategist review，不再自動 shelve） |
| 主 spawn 硬上限（SIGKILL） | 900s | `dispatch.spawn_timeout_sec` / `WORKER_TIMEOUT_SEC` |
| intake 短 turn 上限 | 300s | `dispatch.intake_timeout_sec` |
| Strategist wake 硬上限 | 10800s | `strategist.timeout_sec`（hang guard） |
| Adversary 輪上限 | 7200s | `adversary.timeout_sec` |
| postmortem / reflection cap | 180s / 120s | `POSTMORTEM_TIMEOUT_SEC` / `_REFLECTION_TIMEOUT_SEC` |
| spawn_fast_fail 門檻 | 10s | `SPAWN_FAST_FAIL_SEC` |
| spawn cooldown / quota backoff | 30s / 30s×2ⁿ cap 600s | `SPAWN_COOLDOWN_SEC` / `QUOTA_BACKOFF_*` |
| 連續 fast-fail / gateway 失聯上限 | 10 / 8 | `CONSEC_*_LIMIT`（daemon 退出 rc=2） |
| queue lease TTL | 6h | `LEASE_TTL_SEC` |
| Strategist routine interval | 120 min | `strategist.interval_min` |
| Strategist verify/Adversary 修訂輪 | 6 | `strategist.verify_retry` |
| mint retry budget | 3 | `FORWARD_RETRY_BUDGET` |
| verify housekeeping 迭代上限 | 8 | `max_iters` |
| Librarian chain 重試上限 | 2（第 3 次 STALL） | `LIBRARIAN_MAX_CHAIN_RETRIES` |

---

## 8. 設計取捨速查

| 決策 | 為什麼 |
|---|---|
| Context.md 必看訊息 inline、companion 只當備援 | 教訓：agent 不會主動讀 companion |
| Timeout 走 postmortem 而非邊想邊存 | 主任務不被 deliverable 維護分心 |
| Pipeline = session lifecycle、retry 收進 pipeline 內 | sid 是 local var，無跨 pipeline 攜帶 |
| 編譯統一走 LSP gateway | 省每次 5–15s cold 啟動 |
| Verify inline、不佔 worker slot；verify-time LLM 修復取消 | 純框架操作；LLM 修復實證 0 觸發 |
| Builder/Backward/Forward 合併為 Formalizer | 證/拆是同一個判斷，分 kind 造成路由 hack 與 context 斷裂 |
| OR passive（cap=1）不 eager fanout | 強模型下純浪費 token |
| Dedupe 用 apply-probe | Lean 懂 α/β/η/defeq；字串比對命中率低 |
| hint 前置 + 寫回具名 winner | 接 mathlib curated set；artifact 留具名 tactic |
| Infra 失敗不算 agent error | 不燒 goal 預算 |
| 提案包過 Adversary 才 commit | 任務與行動之間需要受評的整份論證（research mode） |

---

## 9. 跨參考

- 靜態形狀（角色、不變量、schema）：`docs/architecture.md`
- 失敗 reason × 觸發 × cascade × event 完整對照：`docs/failure_modes.md` §2
- Goal history umbrella 設計史：`docs/archive/design/goal_history_unified.md`
