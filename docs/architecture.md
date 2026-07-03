# Asterism — 架構

原寫於 2026-05-06；2026-07-03 對照代碼全面重寫。本檔講**概念形狀**：系統由哪些角色組成、
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
  Root/Defs 目前仍必須存在；變 optional 是 Phase 6 未做項。

---

## 2. 角色：五種 worker、一個 housekeeping

**Worker 是 LLM 介入點，純框架操作不佔 worker slot** —— 這條原則決定角色邊界。

| 角色 | target_kind | 做什麼 |
|---|---|---|
| **Builder** | Goal | 先 deterministic tactic（`by hint`）、不行請 LLM 寫 patch 收尾 |
| **Backward** | Goal | 請 LLM 拆成一條 Strategy + N 個 sub-Goal |
| **Forward** | Problem | Strategist 派、產一條新 toolkit lemma（theorem/def/structure/class）、進 BFS 或 leaf-bypass |
| **Strategist** | Goal (root) | 讀 problem state、下決策（七種、見下） |
| **Librarian** | Problem (per-file) | 已證 + opt-in 後走五階段鏈：dedup → classify → migrate → cleanup → bridge |
| **Verify housekeeping** | — | 非 worker：dispatcher tick 內 sequential 跑，組裝全 proved 的 strategy、寫 alias 進 parent、跑 G1 revival |

Strategist 決策七種：`Inject` / `ConfirmShelve` / `EmitDirective` / `RequestUserAmend` /
`MarkDeliverable` / `Ingest` / `Noop`。觸發四種：`first_launch` / `routine` /
`pending_review` / `inject_batch_done`。

並發紀律：每個 Goal 同時最多一條 pipeline（passive OR、cap=1）；Forward / Strategist 同
problem 各最多一條 in-flight；Librarian 以檔為平行單位。`ingest_signoff_pending` 的
problem 一切 Librarian 自動路徑暫停（等人 sign-off）。

---

## 3. 狀態存在哪

| 形式 | 內容 |
|---|---|
| **DB**（`asterism.db`、sqlite WAL、schema v14、11 張表） | 整棵 graph、pipeline 歷史、dead attempt forensics、Strategist 決策、Librarian lifecycle、KB lessons |
| **`Manifest.md`** | 唯一人手檔（§4） |
| **`Defs.lean` / `Root.lean`** | problem 自訂定義 / 框架管的 root（§5） |
| **`proofs/L_<slug>.lean`、`_strategy_s<sid>.lean`** | 每 sub-Goal 一檔、每 Strategy 一份組裝 patch |
| **`.drafts/`、`.presearch/`** | 跨 spawn 的進度筆記 / per-node pre-search cache |
| **`.attempts/<pid>/`** | 純暫存，spawn 結束 unconditional rmtree（artifact 先打包進 `dead_attempts.artifacts`） |

**proofs/ 檔案的一切 mutation 走 `state/proof_store.py` 單一 chokepoint**（原子寫 +
ownership guard + drift inventory；lint test 禁止門外裸寫）。`asterism drift-check` 隨時可驗
DB↔檔一致。

schema 是「程式碼即文件」：表定義、欄位、migration 全在 `Tooling/state/db.py`。狀態
enum 的 SoT 在 `Tooling/state/transitions.py`（goal 8 態、strategy 5 態含 `stalled`），
schema CHECK 由測試綁定、不會漂。

---

## 4. 人機介面

**Manifest.md**（YAML frontmatter + markdown body）：statement、`axioms_whitelist`、
`forbidden_lemmas`、`library: true`（opt-in Library 化）、自由 strategic notes。`init` 寬解：
缺欄位給 default + warning。`## Lemma hints` 仍會被解析，但 pre-search 上線後 prover
context 的主 hint 通道已是自動生成的 `## Candidate lemmas`。

**anchor+claim 的人工介入點**（CLI）：`asterism review`（看 deliverable + kernel anchor
閉包）、`asterism reject`（反向閉包 cascade 作廢）、`approve-ingest` / `reject-ingest`
（harvest 前的 sign-off 閘）。

---

## 5. Root.lean 三態

框架管理、不手改。**A 初始**：`init` 寫 sorry stub。**B 過程中**：框架只在 `proofs/`
下產檔、Root.lean 不動。**C 證完**：`prune.reconcile_proved_goals` 改成薄 indirection ——

```lean
import Problems.<p>.proofs._strategy_s<NN>
namespace Problems.<p>
def main := @Problems.<p>.s<NN>
end Problems.<p>
```

注意是 `def`（型別由 winner strategy 簽名推得）；keyword modifier（`noncomputable`）與
`@[instance]` 前綴保留（root 可宣告 Prop instance——框架只證 Prop、不產 data）。
`init` 偵測現有形態：sorry stub → A；alias → C（noop）；其它 → 要 `--force`。

---

## 6. Dispatcher 主迴圈

每 tick 固定順序：cascade → verify housekeeping → post-proved gate（reconcile + root
integrity）→ librarian refill → exit check → bfs refill → strategist triggers →
reconcile_stuck_states（per-tick 安全網）→ spawn。逐步細節與退出條件見 `data-flow.md` §2。

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

cascade 的概念形狀（完整 outcome × 轉移表在 `data-flow.md` §3 + `failure_modes.md` §2）：

- 失敗計 `attempts`，達 SHELVE_THRESHOLD → `shelved` 並**上拋**：殺掉依賴它的 parent
  strategy；parent 無活 strategy → 自己也可能 shelve、繼續上拋。
- `open_goals` 用 recursive CTE 濾掉死分支下的 orphan；`detached=1`（Forward output、
  Strategist 重啟目標）額外 union 進 alive seed。
- 每筆 Inject decision 寫 outcome；同 batch 全落地 → enqueue Strategist
  `inject_batch_done`（batch_id immutable、以「全部 outcome 非 NULL」推導完成）。
- proved 的前置條件見 §10 公理閘。

---

## 8. OR 順序展開（passive）

每個 Goal 同時只跑一條 Strategy；死了才生下一條。強模型下 eager fanout 純浪費 token；
代價是第一條走錯方向時 wall-clock 較慢，緩解靠 SHELVE_THRESHOLD + 給 Backward 看「過去
死掉的分解試過什麼」。每條 Strategy 用 strategy-isolated 檔名（`_strategy_s<sid>.lean`、
定理名 `s<sid>` 由框架鎖定）；parent 的 `lean_path` 只在 Verify 勝出時被改。sub-goal slug
是 agent 取的描述名、全題唯一（`UNIQUE(problem, slug)`）。

---

## 9. Dedupe（sub-goal 等價共享）

Backward 拆出新 sub-goal 時，框架用 Lean kernel probe（`apply @<canonical> <;> assumption`
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
- Forward 端：dedupe 命中 alive → 拒提案；命中 **proved** → 直接落地 alias（提案自動變
  引用）。cite-gate 會 resolve alias、proved alias 可被引用。
- **G1 shelved-revival**：Forward 落地新 goal X 時反向探「X 能否 discharge 某 shelved S」，
  命中先記 link；X 之後 proved，housekeeping 補寫 alias body、S 復活轉 proved 上拋。

---

## 10. 公理閘體系

原則（2026-07-03 定案）：**`proved` 只在公理集驗過 whitelist 之後才標；每次高風險改寫
之後都要重驗**。whitelist 來自 Manifest `axioms_whitelist`、缺席時 framework default
（Classical.choice / propext / Quot.sound）+ warning——**絕不因欄位缺席而 skip**。

| 閘 | 位置 | 守什麼 |
|---|---|---|
| **pipeline 出口閘** | `_axiom.axiom_gate`，Builder / Backward leaf-bypass / Forward 三處共用（own-slot、~150ms） | 任何 goal 標 proved 前，其證明的公理集 ⊆ whitelist（結構 lint test 斷言三 pipeline 都走它） |
| **root integrity gate** | root 翻 proved 時（`integrity_verified` marker 守、翻離 proved 自動清） | 整條 alias 鏈的唯一一次完整 elaboration；抓 drift + 漏網 sorryAx，元凶 bisect + rollback 重拆 |
| **Librarian migrate gate** | 每檔搬進 Library 時 | per-decl `#print axioms` ⊆ whitelist + import 閉包 + Gate D def-equivalence；`axiom` 宣告一律 hard-fail |
| **cleanup 收尾 re-gate** | cleanup 改寫證明體之後 | 同 per-decl 檢查對**最終文本**重跑——LLM 改寫段（simplify / near-dup bridge / audit 整檔重寫）是 migrate 之後唯一能改公理集的地方 |
| **bridge 終局閘** | chain 末端 | classic：Gate B 從 Library 重推 root（statement-pin + axiom probe）；deliverable：cite_drop 後逐檔 per-decl 公理閘、PASS 才寫 INDEX |

verify-collapse 設計不變：per-level `verify_strategy` 是純機械 alias rewrite、不逐層
elaborate；root gate 的 rollback 是 false-proved 溜過機械驗證時的修正網（實務極少 fire、
但不可拆——verify-collapse 刻意不 probe non-leaf promote）。

---

## 11. 代碼地圖

```
Tooling/
  core/       dispatcher.py（主迴圈+排程）、librarian_sched.py（五階段 DAG 排程）、
              cli.py、config.py、lifecycle
  state/      db.py（schema+migration+query）、transitions.py（狀態機）、
              proof_store.py（proofs/ chokepoint）、recovery.py（startup 修復+orphan sweep）、
              kb.py / kb_ingest.py（lessons、Model B）
  pipeline/   builder.py / backward.py / forward.py / strategist.py
              librarian/（_base/astslice/bridge/classify/context/execute/gate/run/schedule）
              _retry.py（session retry helper）、_assembly.py、_axiom.py（共用公理閘）、
              _cite_gate.py、_constants.py（含 anchor_closure RPC wrapper）、_drafts.py、
              _feedback.py、_infra.py、_lake.py、_olean_warm.py、_presearch.py、
              _reflection.py、_skeleton.py、events.py
  quality/    verify.py（housekeeping+root gate）、dedupe.py、prune.py、
              librarian/（dedup/gates/inventory/relabel + cleanup/{mechanical,simplify,audit,decide}）
  agent/      context.py / phase2_context.py（Context.md 編譯）、runtime.py
  llm/        claude_cli.py（spawn+watchdog）、gemini/openai 後端
  lsp/        gateway.py（warm verify_file + validate_file + anchorClosure RPC）、lifecycle
  knowledge/  loogle 等 lemma 搜尋
  prompts/    各 worker system prompt（每 pipeline 一檔）
```

---

## 12. Context.md：agent 唯一介面

每次 spawn 前框架從 DB 編一份 Context.md——**agent 看到的所有訊息都從這裡來**（companion
檔只是備援，agent 常不讀）。編譯原則：必看訊息 inline、curated 不 dump、跨 spawn 穩定的
段落（BRIEF、KB lessons）放最前讓 prompt cache 命中。lessons 來源是 DB `kb_entries`
（Model B：global-only、reflection 寫入、每 spawn inline）；pre-search 在場時注入
`## Candidate lemmas` 並取代 proved-siblings 段。完整 section 順序見 `data-flow.md` §5。

---

## 13. 不做（什麼東西在這個系統不存在、為什麼）

| 不做 | 原因 |
|---|---|
| 'running' state 在 pipelines 表 | 只放 finished rows，daemon 死了不留 zombie |
| Active cancellation propagation 表 | cascade 入口 no-op 已被動接住 OR 落敗者 |
| Generalizer / Refuter 等新 worker_kind | schema 留洞、deferred（backlog「考慮中」） |
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
- worker_kind ↔ target_kind：Builder/Backward → Goal、Forward → Problem、Strategist →
  Goal (root)、Librarian → Problem（per-file target `problem\x1ffile`）；Verify 不是 worker

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

**Strategist**
- ConfirmShelve 與 Inject(Backward|Builder) 不得指向同一 target 或其 descendant
- `strategist_decisions.batch_id` immutable；「同 batch 全部 outcome 非 NULL」推導完成
- Forward output goal 必 `detached=1`
- deliverable 題 harvest 前必經 `ingest_signoff_pending` 人工 sign-off

**進程**
- daemon process tree 綁 kill-on-close Job Object（parent 死、children 自動回收）

---

已證題目清單不再維護於本檔——看 DB（`origin='root' AND status='proved'`）、README 進度
log、或 `Library/INDEX.md`。
