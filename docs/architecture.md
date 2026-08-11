# Asterism — 架構

原寫於 2026-05-06；2026-07-03 對照代碼全面重寫；2026-07-29 漂移校正（Formalizer 合併、
research mode、problem FSM）；2026-08-02 補討論小組樹（v35）。本檔講**概念形狀**：系統由哪些角色組成、
狀態存在哪、哪些不變量在撐著正確性。動態流程（tick 怎麼跑、pipeline 逐步）見
`docs/data-flow.md`；失敗語彙見 `docs/failure_modes.md`；技術細節以代碼為準、動手時再讀。

---

## 1. 在做什麼

把「用 LLM 證 Lean 4 定理」抽象成 AND/OR graph 上的 BFS：

```
Goal      = OR  : 任一 Strategy 成功 → Goal 成功
Strategy  = AND : 所有 sub-Goal 成功 → Strategy 成功
```

葉子 Goal 由 LLM 直接寫 tactic 收掉；非葉子 Goal 靠 Strategy 拆解。整棵推理樹活在
sqlite（`goals` × `strategies` × `strategy_subgoals`），**DB 是單一真實來源**。

收束有兩種模式：

- **classic**：root goal 證出 → integrity gate → （opt-in）Library 化。
- **anchor+claim**（2026-06 起）：人用自然語言寫 Manifest，Strategist 生成 def/claim 並用
  `MarkDeliverable` 標記交付物；kernel 算 anchor 閉包供人 `asterism review` / `reject`；
  全部 deliverable 終態後 Strategist 下 `Ingest`，經**人工 sign-off**（`approve-ingest` /
  `reject-ingest`）才 harvest 進 Library。root 此時可以只是鷹架（`main : True`）。
  `Root.lean` / `Defs.lean` 皆 optional——pure-NL 題兩者全缺：無 root goal 列，
  靠 structural stall 喚起第一次 Strategist。

---

## 2. 角色：四種 worker、一個 housekeeping

**Worker 是 LLM 介入點，純框架操作不佔 worker slot** —— 這條原則決定角色邊界。

| 角色 | target_kind | 做什麼 |
|---|---|---|
| **Formalizer** | Goal / Problem | 唯一 Lean 證明 worker（2026-07-27 由 Builder/Backward/Forward 三種合併、v33）。Goal-target：intake 分流（含 falsity scan、可 decline）→ 自行決定直接證明或拆成 Strategy + N 個 sub-Goal；Problem-target（**mint**）：Strategist 派、產一條新 toolkit lemma。實作仍分 `pipeline/backward.py`（prove/split）與 `forward.py`（mint）兩檔 |
| **Strategist** | Problem | 讀 problem state、寫提案包（Programme 修訂 + 決策批）、經 Adversary 裁決放行後 commit（決策九種、見下） |
| **Scholar** | Problem | Strategist `FetchPaper` 派：抓白名單論文進 `Papers/`、建索引（v23） |
| **Librarian** | Problem (per-file) | 已證 + opt-in 後走五階段鏈：dedup → classify → migrate → cleanup → bridge |
| **Verify housekeeping** | — | 非 worker：dispatcher tick 內 sequential 跑，組裝全 proved 的 strategy、寫 alias 進 parent、跑 G1 revival |

**Adversary（判官）不是 worker kind**——它是 Strategist wake 內逐輪 fresh 的
sub-spawn，在投影目錄硬隔離下審提案包、產 `verdict.json`，框架從逐準則裁決推導
放行/反駁（見下「研究模式」）。

Strategist 決策十一種（SoT：`strategist.py` `DECISION_KINDS`）：`Inject` /
`ConfirmShelve` / `EmitDirective` / `RequestUserAmend` / `MarkDeliverable` / `Ingest` /
`FetchPaper` / `AttemptDisproof`（框架機械鑄 ¬P goal——信念不被信任、兩個方向都要
kernel）/ `Delegate` / `ReturnToParent`（後兩種屬小組樹、見下；`ReturnToParent`
子組限定）/ `Noop`。觸發三種：`routine`（含 belief audit 第一階段）/ `pending_review` /
`inject_batch_done`（structural stall 的喚醒也歸這類——fresh 題、deadlock、root 已證待
Ingest 都算「empty batch done」）。`Ingest` 是唯一終態：root 在場時未 proved 前框架硬性
拒絕；`ingested_at` 驅動 T1/T4 活性、Librarian selfstart 與 daemon 退出。

並發紀律：每個 Goal 同時最多一條 pipeline（passive OR、cap=1）；Strategist 同 problem
最多一條 in-flight；mint 以 `(target, kind, decision_id)` 為去重單位——同 batch 的
N 條 mint Inject 會並行 fan-out；Librarian 以檔為平行單位。`ingest_signoff` 態的
problem 一切 Librarian 自動路徑暫停（等人 sign-off）。

### 研究模式（Programme + Adversary，2026-07 起）

Strategist 每批決策不再裸提交：一份**提案包**（`proposal.md`：`# Title` / `## Argument`
/ `## Proof` / `## Roadmap`）連同決策批送 Adversary 逐輪審查，反駁騎在 verify-retry
迴圈上（與機械檢查共用輪數上限）；到頂仍被反駁 → 提案+批評全存 `programme_revisions`
（v30、status='rejected'）、session 拋棄。通過的 Programme 修訂鏈是 problem 的戰略
SoT（`PROGRAMME.md` 只是 render；v31 以 partial unique index 釘每 rev 至多一 passed）。
**NL-first**（2026-07-25 起）：worker 以 Programme 的 `## Proof` 為前提工作，goal 對應
不到任何 NL 步驟時以 `no_nl_correspondence` 上交、不發明數學。{`FetchPaper`,
`RequestUserAmend`, `Noop`, `ReturnToParent`} 全豁免包閘；提案必附 ≥1 實驗
（`Inject`/`AttemptDisproof`/`Delegate`）。設計 SoT：
`docs/internal/research_mode_design.md`、`nl_first_design.md`。

### 討論小組樹（2026-08-02、v35）

NL 論證層從「一份 Programme、一個 strategist、一個判官管整題」長成**一棵樹**：

> 小組 = 一份 charter + 自己的 Programme + 自己的 strategist/判官迴圈 + 它底下的子樹。

charter 是父組交派的一段自然語言宣稱——**charter 之於子組＝Manifest 之於整題**，
子組因此沿用整題層全部機制一路到終局。小組是**同一 problem 內的分區**（跨 problem
引用被 cite gate 禁止），不是遞迴的 problem；頂層組是 `groups` 表裡
`parent_group_id IS NULL` 的真實列、每題唯一（partial unique index 釘住）、只有它對人。

- **`Delegate`**：把一段自己還證不出的宣稱交派給新組（可帶 `target_goal_id` 當救援
  錨、錨轉 `attempting`）。豁免判官封閉律準則 4——交派物本身就是論證；判官改審
  charter 精確可判 / Proof 假設它成立後完整 / 不依賴任何祖先 charter 或本組結論 /
  是重擔不是跳步。
- **`ReturnToParent`**：子組交回（`refuted` 須指向 proved 的 ¬charter 磚 / `amend`
  附建議新 charter / `exhausted` 附屍檢）。
- **結構牆（都在 verifier 層）**：頂層組不得 `ReturnToParent`（無處可去——機器不把
  難題丟回給人）；子組不得 `RequestUserAmend`（看不到 user 檔、走 `ReturnToParent`
  由父組決定是否升級）。
- **父組派完即安靜**：`Delegate` 與 `Inject` 同吃批次在飛帳（兩道在飛謂詞都認得
  「活著的子組」為第三種產物——這條「同進兩道」有 invariant test 釘住），子組終態
  才喚醒父組。子組的 `Ingest` 是輕量版（標 `delivered`、不碰簽核/harvest/problem
  FSM）；交回標 `returned`、救援錨落回 `shelved`。
- wake 席位、routine 鐘、牆態偵測、Programme 修訂鏈、plan note、判官投影全部
  **per-group**；goal 的組歸屬是推導、不存欄位（錨優先 → 最近產出決策的作者組 →
  頂層組；解析到非 active 組換最近 active 祖先）。

設計 SoT：`docs/internal/discussion_group_design.md`。

---

## 3. 狀態存在哪

| 形式 | 內容 |
|---|---|
| **DB**（`asterism.db`、sqlite WAL；版本號與表清單以 `state/db.py` `_CURRENT_USER_VERSION` 為準（撰稿時 v35、17 張表）；近代里程碑：v17 queue lease、v21 spawn_usage 計帳、v23 Scholar/FetchPaper、v25 AttemptDisproof、v28 user_file_history、v29 problem FSM、v30/v31 Programme 修訂鏈、v33 Formalizer 合併、v35 討論小組樹） | 整棵 graph、pipeline 歷史、dead attempt forensics、Strategist 決策、Programme 修訂、小組樹、Librarian lifecycle、KB lessons、spawn 用量 |
| **`Manifest.md`** | 唯一人手檔（§4） |
| **`Defs.lean` / `Root.lean`** | problem 自訂定義 / 框架管的 root（§5） |
| **`proofs/L_<slug>.lean`、`_strategy_s<sid>.lean`** | 每 sub-Goal 一檔、每 Strategy 一份組裝 patch |
| **`.drafts/`、`.presearch/`** | 跨 spawn 的進度筆記 / per-node pre-search cache |
| **`.attempts/<pid>/`** | 純暫存，spawn 結束 unconditional rmtree（artifact 先打包進 `dead_attempts.artifacts`） |

**proofs/ 檔案的一切 mutation 走 `state/proof_store.py` 單一 chokepoint**（原子寫 +
ownership guard + drift inventory；lint test 禁止門外裸寫）。`asterism drift-check` 隨時可驗
DB↔檔一致。

schema 是「程式碼即文件」：表定義在 `Tooling/state/db.py`、migration 全集在
`state/db_migrations.py`。狀態 enum 的 SoT 在 `Tooling/state/transitions.py`
（goal 8 態、strategy 5 態含 `stalled`、problem 5 態——見 §7）；group 4 態
（`active`/`delivered`/`returned`/`closed`）由 `state/groups.py` `set_status` 單一
驅動。schema CHECK 由測試綁定、不會漂。

---

## 4. 人機介面

**Manifest.md**（YAML frontmatter + markdown body；欄位 SoT `state/manifest.py`）：
`axioms_whitelist`、`forbidden_lemmas`、`library: true`（opt-in Library 化）、
`signoff: false`（benchmark 無人值守專用、跳過人工 sign-off；解析異常一律 coerce 回
true）；`paper:` 已棄用（綁定移 `problem_papers` 表）。`init` 寬解：缺欄位給 default +
warning。**body 一個字都不解析**（2026-08-11）：operator 想下什麼小標就下什麼，整份
原樣送到每個 agent 面前（616 份 Manifest 的 body 中位數 440B）。曾經被具名抽取的
`## Statement` / `## Strategic notes` 都不再是欄位——正典陳述在 `Root.lean` 的
theorem 簽名，prover 的 hint 通道是自動生成的 `## Candidate lemmas`。

**anchor+claim 的人工介入點**（CLI）：`asterism review`（看 deliverable + kernel anchor
閉包）、`asterism reject`（反向閉包 cascade 作廢）、`approve-ingest` / `reject-ingest`
（harvest 前的 sign-off 閘）。

**Problem 佈局**：`<Domain>.<slug>` → `Problems/<Domain>/<slug>/`；Domain 對齊 mathlib
頂層命名（`Topology`/`NumberTheory`/`Analysis`…慣例、非硬編白名單）。舊 problem 不能
純 `git mv` 搬移——Lean module path = 檔案路徑，會壞 build。`Defs.lean` / `Root.lean`
皆 optional（pure-NL 可全缺）；手改 Root statement 後要重 `init` 或 `asterism repin`
（user 檔 baseline 走 `user_file_history`，v28）。

---

## 5. Root.lean 三態

**A 初始**：使用者手寫 sorry stub（框架不產；`init` 只做 lake build 型檢 + 抽
statement，`--force` 是型檢旁路；root goal 起始 `frozen`）。**B 過程中**：框架只在
`proofs/` 下產檔、Root.lean 不動。**C 證完**：兩種欽定寫法——(a) assembly 直接就地寫
完整 `theorem main`（statement byte-for-byte 保留）；(b) `prune.reconcile_proved_goals`
改成薄 indirection——

```lean
import Problems.<p>.proofs._strategy_s<NN>
namespace Problems.<p>
def main := @Problems.<p>.s<NN>
end Problems.<p>
```

注意是 `def`（型別由 winner strategy 簽名推得）；keyword modifier（`noncomputable`）與
`@[instance]` 前綴保留（root 可宣告 Prop instance——框架只證 Prop、不產 data）。
兩形皆過 `verify._root_statement_pin_ok`（statement pin、task #120——proved root 釘回
user baseline）。

---

## 6. Dispatcher 主迴圈

每 tick 固定順序：cascade → verify housekeeping → post-proved gate（reconcile + root
integrity）→ librarian refill → exit check → quota-wait gate → bfs refill →
strategist triggers → reconcile_stuck_states（per-tick 安全網）→ lease sweep → spawn。
逐步細節與退出條件見 `data-flow.md` §2。

**紀律**：cascade 的**傳播**永遠在主線程 sequential（`transitions.assert_main_thread` 守；
CI strict 模式 raise）。worker thread 可以對**自己的 target** 做 commit 時刻的狀態轉移
（一律經 transitions 的 checked mutator），但絕不跑傳播入口。這條消除了整類 OR-race。

**pipeline = slot**（#118）：dispatch.pool 與 gateway workers 1:1、一起伸縮；pipeline 入場
claim 一格 warm slot、整個生命週期的驗證都打自己這格（own-slot、無 eviction）。borrow
（`verify_file`）只限非-pipeline context，挑格 unclaimed 優先。語意細節見 data-flow §0。

daemon 起手把整棵 process tree 綁進 kill-on-close Job Object——daemon 死、子進程（claude /
lake）自動回收，不需要手動清 orphan。

---

## 7. 狀態機與 cascade（概念）

所有 goal/strategy 狀態轉移走 `state/transitions.py` 的 checked mutator：合法邊註冊在
`GOAL_EDGES` / `STRATEGY_EDGES`，CI strict 模式下未註冊的邊直接 raise、production 大聲
log。lint test 以計數 ratchet 禁止新增 raw `UPDATE … SET status`。

cascade 的概念形狀（完整 outcome × 轉移對照**只在** `failure_modes.md` §2）：

- 失敗計 `attempts`，達 SHELVE_THRESHOLD → 轉 `pending_strategist_review` 交 Strategist
  裁決——**ConfirmShelve 才真 `shelved` 並上拋**（殺掉依賴它的 parent strategy；parent
  無活 strategy → 繼續上拋）。硬終態 `dead`（如 `missing_parent_stub`）仍直接上拋。
- `open_goals` 用 recursive CTE 濾掉死分支下的 orphan；`detached=1`（mint output、
  Strategist 重啟目標）額外 union 進 alive seed。
- 每筆 Inject decision 寫 outcome；同 batch 全落地 → enqueue Strategist
  `inject_batch_done`（batch_id immutable、以「全部 outcome 非 NULL」推導完成）。
- proved 的前置條件見 §10 公理閘。

**Problem 層另有五態 FSM**（v29、`problems.state`）：`active` / `awaiting_human` /
`ingest_signoff` / `ingested` / `revoked`。`WAKE_LEGALITY` 只許 `active` 收 Strategist
wake（其餘為人類擁有或終態）；唯一 mutator `apply_problem_transition`；`revoked`
（入庫後 un-prove）由 `asterism revive` 復活。「stalled」刻意不是狀態、是 `active` 上
的推導守衛——機器無合法靜止態。設計 SoT：`docs/internal/problem_fsm_design.md`。

---

## 8. OR 順序展開（passive）

每個 Goal 同時只跑一條 Strategy；死了才生下一條。強模型下 eager fanout 純浪費 token；
代價是第一條走錯方向時 wall-clock 較慢，緩解靠 SHELVE_THRESHOLD + 給 Formalizer 看
「過去死掉的分解試過什麼」。每條 Strategy 用 strategy-isolated 檔名（`_strategy_s<sid>.lean`、
定理名 `s<sid>` 由框架鎖定）；parent 的 `lean_path` 只在 Verify 勝出時被改。sub-goal slug
是 agent 取的描述名、全題唯一（`UNIQUE(problem, slug)`）。

---

## 9. Dedupe（sub-goal 等價共享）

Formalizer 拆出新 sub-goal 時，框架用 Lean kernel probe（`apply @<canonical> <;> assumption`
單一 batch cold 呼叫）比對候選池：ancestor chain / sibling orphan / 跨 branch proved /
同題 disproved / reuse tier（open·attempting·shelved）。命中 → 不 INSERT、
`strategy_subgoals` link 到 canonical、檔案寫成 alias 並 build-verify。fail-open：probe
壞掉一律當 no-hit、不阻斷主流程。

要點：

- **alias 機制 theorem-only**——data def 不 alias（def-blind 誤判修正 `cbe5bc3`、
  soundness-adjacent）。
- 命中 disproved → 整批 abort（「已給過反例、別再提」）。
- `no_progress` 守門是單-canonical apply 探針：sub-goal 若能被正在拆的 goal 或其未證
  ancestor 一發 discharge → 拒（拆了等於沒拆）。
- mint 端三分支：命中同題 alive/parked 孿生 → **reuse**（Inject 重指到既有 goal、必要
  時復活 detach，不新建）；命中 **proved** → 直接落地 alias（提案自動變引用）；其餘
  正常落地。cite-gate 會 resolve alias、proved alias 可被引用。
- **G1 shelved-revival**：mint 落地新 goal X 時反向探「X 能否 discharge 某 shelved S」，
  命中先記 link；X 之後 proved，housekeeping 補寫 alias body、S 復活轉 proved 上拋。

---

## 10. 公理閘體系

原則（2026-07-03 定案）：**`proved` 只在公理集驗過 whitelist 之後才標；每次高風險改寫
之後都要重驗**。whitelist 來自 Manifest `axioms_whitelist`、缺席時 framework default
（Classical.choice / propext / Quot.sound）+ warning——**絕不因欄位缺席而 skip**。

| 閘 | 位置 | 守什麼 |
|---|---|---|
| **pipeline 出口閘** | `_axiom.axiom_gate`，Formalizer 兩入口（prove/split leaf-bypass + mint）共用（own-slot、~150ms） | 任何 goal 標 proved 前，其證明的公理集 ⊆ whitelist（結構 lint test 斷言） |
| **root integrity gate** | root 翻 proved 時（`integrity_verified` marker 守、翻離 proved 自動清） | 整條 alias 鏈的唯一一次完整 elaboration；抓 drift + 漏網 sorryAx，元凶 bisect + rollback 重拆 |
| **Librarian migrate gate** | 每檔搬進 Library 時 | per-decl `#print axioms` ⊆ whitelist + import 閉包 + Gate D def-equivalence；`axiom` 宣告一律 hard-fail |
| **cleanup 收尾 re-gate** | cleanup 改寫證明體之後 | 同 per-decl 檢查對**最終文本**重跑——LLM 改寫段（simplify / near-dup bridge / audit 整檔重寫）是 migrate 之後唯一能改公理集的地方 |
| **bridge 終局閘** | chain 末端 | classic：Gate B 從 Library 重推 root（statement-pin + axiom probe）；deliverable：cite_drop 後逐檔 per-decl 公理閘、PASS 才標 bridge 完成（`problems.library_bridged_at`，v18） |

verify-collapse 設計不變：per-level `verify_strategy` 是純機械 alias rewrite、不逐層
elaborate；root gate 的 rollback 是 false-proved 溜過機械驗證時的修正網（實務極少 fire、
但不可拆——verify-collapse 刻意不 probe non-leaf promote）。

---

## 11. 代碼地圖

```
Tooling/
  core/       dispatcher.py（主迴圈+排程）、librarian_sched.py（五階段 DAG 排程）、
              cli.py、config.py、quota_wait.py / usage_quota.py（額度）、
              warmup.py（NL-first gateway 暖機）、process_group.py（Job Object）
  state/      db.py（schema DDL+query）、db_migrations.py（migration 全集）、
              transitions.py（goal/strategy/problem 狀態機+ProvedReceipt+cascade_one）、
              programme.py（Programme 修訂鏈）、manifest.py、proof_store.py（proofs/
              chokepoint）、recovery.py（startup 修復+orphan sweep）、failures.py
              （failure-reason registry=機器 SoT）、thresholds.py、regress.py、
              consistency.py（drift-check 謂詞）、kb.py / kb_ingest.py（lessons、Model B）
  pipeline/   backward.py / forward.py（Formalizer 的 prove-split / mint 兩入口）、
              _intake.py（Formalizer intake 閘）、strategist.py、adversary.py（判官）、
              scholar.py（論文抓取）、
              librarian/、_retry.py（session retry helper）、_assembly.py、
              _axiom.py（共用公理閘）、_cite_gate.py、_presearch.py、_reflection.py、
              events.py 等
  quality/    verify.py（housekeeping+root gate）、dedupe.py、prune.py、review.py、
              knowledge_stats.py、librarian/（dedup/gates/inventory/relabel + cleanup/*）
  agent/      context.py / phase2_context.py（Context.md 編譯）、runtime.py（spawn +
              spawn_usage 計帳）、sandbox.py
  llm/        claude_cli.py（spawn+watchdog+sandbox flags）、spawn_guard.py、
              gemini/openai 後端
  lsp/        gateway.py（warm verify_file + validate_file + anchorClosure RPC）、
              client.py、decl_oracle.py、lifecycle
  knowledge/  loogle 等 lemma 搜尋
  papers/     fetch / index / search / shelf（Papers/ 書架）
  serve/      web console（`asterism serve`：星圖、Engine 視圖、chat explainer）
  prompts/    每 worker 一資料夾、多階段檔（formalizer/{intake,formalize,mint}、
              strategist/、adversary/、scholar/、librarian/、_shared/）
```

---

## 12. Context.md：agent 唯一介面

每次 spawn 前框架從 DB 編一份 Context.md——**agent 看到的所有訊息都從這裡來**（companion
檔只是備援，agent 常不讀）。編譯原則：必看訊息 inline、curated 不 dump、跨 spawn 穩定的
段落（BRIEF、KB lessons）放最前讓 prompt cache 命中。lessons 來源是 DB `kb_entries`
（Model B：global-only、reflection 寫入、每 spawn inline、cap 25）；pre-search 在場時
注入 `## Candidate lemmas` 並取代 proved-siblings 段。research mode 下 Programme 的
`## Proof` 以 programme 段注入 worker context（NL-first 前提）；bulky 內容走
`CATALOG.md` / `PAPER_MAP.md` companion、inline 只留索引指標。完整 section 順序見
`data-flow.md` §5。

---

## 13. 不做（什麼東西在這個系統不存在、為什麼）

| 不做 | 原因 |
|---|---|
| 'running' state 在 pipelines 表 | 只放 finished rows，daemon 死了不留 zombie |
| Active cancellation propagation 表 | cascade 入口 no-op 已被動接住 OR 落敗者 |
| Generalizer / Refuter 等新 worker_kind | 仍 deferred（Scholar v23、Formalizer v33 已示範 kind 擴張路徑） |
| 自動 prune OR 落敗 strategy 檔 | blast radius 太大（Jordan 2026-05-26）；只自動 reconcile，prune 是 operator opt-in `asterism prune` |
| events 表 audit log | dead_attempts.artifacts JSON + stdout 夠 |
| `commit_state` pending/live 兩段式 | backup-restore + `os.replace` 夠用 |

---

## 14. 不變量（修改前先看）

**併發與狀態**
- 狀態寫入只走 `transitions` checked mutator；未註冊邊 CI raise（lint：raw `UPDATE …
  status` 計數 ratchet 守）
- cascade **傳播**只在主線程（`assert_main_thread` 守）；worker thread 只對自己的 target
  做 commit-time 轉移
- **pipeline = slot**：pipeline 生命週期內的驗證走自己 claim 的 gateway 格
  （`_axiom.verify_on_own_slot`）；borrow 只限非-pipeline context、挑格 unclaimed 優先
- `pipelines` 表只存 finished rows
- worker_kind ↔ target_kind：Formalizer → Goal（prove/split）或 Problem（mint）、
  Strategist → Problem、Scholar → Problem、Librarian → Problem（per-file target
  `problem\x1ffile`）；Verify 不是 worker
- `problems.state` 轉移只走 `apply_problem_transition`；wake 只投給 `active`（WAKE_LEGALITY）

**soundness**
- `proved` 只在 `axiom_gate` 通過後才標；Library 內容每次高風險改寫後重驗公理（§10）
- Library 永不引入 `axiom` 宣告
- `proofs/` 檔案 mutation 只走 `proof_store`（原子寫 + ownership guard；lint 守）

**檔案與 schema**
- `goals.lean_path` UNIQUE；`strategies.lean_path` 不 UNIQUE（多 strategy 共享 parent target）
- strategy `scratch_path` write-once（INSERT 時可空、補寫一次後不再變）
- sub-goal slug 全題唯一（`UNIQUE(problem, slug)`）；strategy 檔名/定理名 `s<sid>` 框架鎖定
- `.attempts/<pid>/` unconditional rmtree、agent 輸出先打包進 `dead_attempts.artifacts`
- Schema 修改要 bump user_version + 寫 migration

**小組樹**
- 每題恰一個頂層組（`parent_group_id IS NULL`、partial unique index）；頂層組是
  真實列、不是代碼特例
- 「活著的子組」作為第三種在飛產物，必須**同時**被 `has_active_inflight_inject`
  （停滯側）與 `has_live_inflight_inject`（反閒置側）認得（invariant test 釘住；
  兩者歷史上分歧過三次、每次都是 livelock/deadlock）
- 頂層組不得 `ReturnToParent`；子組不得 `RequestUserAmend`（皆 verifier 駁回）
- 子組 Ingest 不碰 `problems.ingested_at`/簽核/harvest/problem FSM
- group 狀態轉移只走 `groups.set_status`

**Strategist**
- ConfirmShelve 與 goal-target Inject 不得指向同一 target 或其 descendant
- `strategist_decisions.batch_id` immutable；「同 batch 全部 outcome 非 NULL」推導完成
- mint output goal 必 `detached=1`
- 非豁免決策批必附通過 Adversary 的提案包；Programme 修訂鏈每 rev 至多一 passed（v31）
- deliverable 題 harvest 前必經 `ingest_signoff` 人工 sign-off（`signoff: false` 的
  benchmark 題除外）

**進程**
- daemon process tree 綁 kill-on-close Job Object（parent 死、children 自動回收）

---

已證題目清單不維護於本檔——查 DB：`origin='root' AND status='proved'`；Library 索引即
`library_decls` + `problems.library_bridged_at`（v18 起 INDEX.md 退役、DB 即索引）。
