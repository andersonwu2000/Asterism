# Asterism — 架構

寫於 2026-05-06。聚焦概念形狀，不重複代碼能說清楚的細節。資料流向見 `docs/data-flow.md`。

---

## 1. 在做什麼

把「用 LLM 證 Lean 4 定理」抽象成 AND/OR graph 上的 BFS。

```
Goal      = OR  : 任一 Strategy 成功 → Goal 成功
Strategy  = AND : 所有 sub-Goal 成功 → Strategy 成功
```

葉子 Goal 由 LLM 直接寫 tactic 收掉；非葉子 Goal 靠 Strategy 拆解。整個推理樹都活在 sqlite 的 `goals` × `strategies` × `strategy_subgoals` 三張表上，DB 是單一真實來源。

---

## 2. 四個 worker、一個 housekeeping

**Worker 是 LLM 介入點，純框架操作不佔 worker slot。** 這條原則決定下面五個角色的位置。

| 角色 | target_kind | 做什麼 | 有 LLM 嗎 |
|---|---|---|---|
| **Builder** | Goal | 試一輪 deterministic tactic、不行就請 LLM 寫一份 patch 收尾 | 第二階段有 |
| **Backward** | Goal | 請 LLM 把這個 Goal 拆成一條 Strategy + N 個 sub-Goal | 有 |
| **Forward** | Problem | 由 Strategist `Inject(Forward)` 派、產一條新 toolkit lemma (kind ∈ {theorem,def,structure,class})、進 BFS 或 leaf-bypass | 有 |
| **Strategist** | Goal (root) | 讀 problem state、決定 Inject / ConfirmShelve / EmitDirective / RequestUserAmend / Noop | 有 |
| **Verify housekeeping** | Strategy | sub-Goal 全 proved 後，把 Strategy 組裝起來編譯、寫進 parent 的 `.lean` 檔；同時跑 G1 shelved-revival pass | 沒有 |

Verify 早期是第三種 worker_kind；後來砍成 dispatcher 主迴圈末端的步驟，因為它既無 LLM 也不該佔 pool 格子。

每個 Goal 最多同時一條 Builder 或一條 Backward 在跑（passive OR、cap=1）。死掉之後才生下一條。早期是 eager fanout（同 Goal 並行多條 Strategy），實證在強模型下純粹浪費 token。

Strategist trigger 種類：`first_launch`（root frozen 第一次喚醒）/ `routine`（定期）/ `pending_review`（agent 自己 shelve 後等審）/ `inject_batch_done`（前一批 Inject 全部 terminal）。同 problem 內 Strategist queue dedup、最多一條 in-flight。Forward 同 problem 內最多一條 in-flight（dispatcher 檢查、避免並發 toolkit 衝突）。

---

## 3. 哪些東西被永久保存

| 形式 | 內容 |
|---|---|
| **DB** (`asterism.db`, sqlite + WAL) | 整棵 AND/OR graph、所有歷史 pipeline 結果、所有 dead attempt 連同 agent 寫的全部 artifact JSON |
| **`Problems/<p>/Manifest.md`** | 唯一人手檔。statement、entry_kind、forbidden lemmas、lemma hints、自由 strategic notes |
| **`Problems/<p>/Defs.lean`** | problem-specific 自訂定義，cli init 自動 import 進 Root.lean |
| **`Problems/<p>/Root.lean`** | 框架管的，有三個生命週期態（§5） |
| **`Problems/<p>/proofs/L_<slug>.lean`** | 每個 sub-Goal 一份 Lean 檔；sorry stub → 真 proof |
| **`Problems/<p>/proofs/_strategy_s<sid>.lean`** | 每條 Strategy 的組裝 patch；Verify 對它 lake build |
| **`Problems/<p>/.drafts/<kind>_g<gid>.md`** | timeout postmortem 留下的進度筆記，跨 spawn 持續 |

`.attempts/<pid>/` 是純暫存，pipeline 結束 unconditional rmtree。所有 agent 寫的東西在刪除前先打包進 `dead_attempts.artifacts` JSON，DB 永遠是 SoT。

DB schema 見 `Tooling/state/db.py`（程式碼即文件）；8 張表的意義：

- `problems` — 註冊表，含 `bootstrap_done` / `last_strategist_at` / `strategist_directive`（最近一次 EmitDirective 的 body）
- `goals` — graph 的 OR 節點。columns：`kind`（theorem/def/structure/class、Curry-Howard 統一前 def 不入 BFS、現在 sorry-bearing 一律 open）、`origin`（root/backward/forward）、`status`（open/attempting/proved/shelved/disproved/dead/frozen/pending_strategist_review）、`entry_kind`（Builder/Backward）、`detached`（Strategist Reopen / Forward output 用、繞過 strategy-chain 邏輯讓 BFS dispatch）、`integrity_verified`（root axiom_probe 通過的 marker）、`alias_target_id`（dedupe + G1 shelved-revival）、`depth` / `attempts`
- `strategies` — graph 的 AND 節點，含 `lean_path`（parent 的目標檔，**Verify 勝出才會被改**）、`scratch_path`（這條 Strategy 獨佔的組裝檔）、`proposal_md`（Backward agent 寫的 decomposition rationale、最終 promote 為 parent 檔頂 annotation）
- `strategy_subgoals` — 多對多，dedupe 把重複 sub-Goal 收成同一個 row
- `pipelines` — 只放 finished rows，沒有 'running' 狀態（daemon 死了重啟見乾淨表面）
- `dead_attempts` — 失敗的 forensic（所有 agent 輸出 artifact 全留在 JSON 欄）
- `queue` — dispatch ready 的 (kind, target_id, target_kind, decision_id) 排隊
- `strategist_decisions` — Phase 2 加；每筆 Strategist 決策一行，columns：`decision_kind`（Inject/ConfirmShelve/Reopen/EmitDirective/RequestUserAmend/Noop）、`target_id`、`brief`、`reason`、`payload`、`batch_id`（同 decision array 內所有 row 共享、用於 `inject_batch_done` 觸發）、`produced_goal_id` / `produced_strategy_id`（Inject 產出的 goal/strategy 反向 link）、`outcome`

---

## 4. Manifest.md（人手介面）

YAML frontmatter + markdown body：

```markdown
---
problem: <name>
axioms_whitelist: [propext, Classical.choice, Quot.sound]
forbidden_lemmas: []
---

# <name> — <one-line>

## Statement
<lean expr>

## Lemma hints
- <hint 1>
- ...

## Strategic notes
<自由 markdown，注入給 agent 看>
```

`init` 寬解：缺欄位給 default + warning，不 crash。

註：早期有 `## Entry kind` section、Phase 2 後 root 一律走 Strategist `first_launch` 派、entry_kind 已 vestigial、commit `c05a3c3` 刪除。

---

## 5. Root.lean 三態

`Root.lean` 是框架管理的、絕對不要手改。三個狀態：

**A. 初始**：`init` 寫一份 sorry stub
```lean
theorem main : <stmt> := by sorry
```

**B. 過程中**：框架在 `proofs/` 下產出 `_strategy_s<NN>.lean` + `L_<slug>.lean`，但 `Root.lean` 本身**不動**。

**C. 證完**：root proved 後 `prune.reconcile_proved_goals` 把它改成
```lean
import Problems.<p>.proofs._strategy_s<NN>
theorem main : <stmt> := s<NN>
```
真正的證明 body 留在 `_strategy_s<NN>.lean`，`Root.lean` 變薄 indirection。

`init` 偵測現有形態：sorry stub → A，OK；alias → C，noop；其它 → reject 要 `--force`。

---

## 6. Dispatcher 主迴圈（概念骨架）

每個 tick 做五件事、順序固定：

```
1. cascade               — 收割上一輪完成的 worker、套狀態轉移
2. verify housekeeping   — 撈 ready strategy 寫 alias 進 parent；同 loop 內跑 G1 revival pass
                           （遞迴最多 8 圈、深度 4 的題一輪可連帶 4 層）
3. root proved? exit     — 對 proved 但尚未 integrity_verified 的 root 跑 reconcile + prune
                           + integrity gate、root_proved 全到位 → 退出
4. bfs_refill            — open goal 走 alive CTE 過濾、按 entry_kind 排進 queue
5. spawn                 — pool 有空格 → 從 queue 拉、ThreadPoolExecutor.submit 進 worker
                           thread；Forward 走 pre-spawn /register + 取 session token
                           + 跑 LLM
```

**紀律**：cascade 永遠在主線程 sequential（worker thread 只 INSERT finished pipeline row、絕不直接改 goal/strategy 狀態）。這條規則消除了所有 OR-race 災難。

dispatch.pool == gateway workers（locked together、#118 1:1 binding）— 每條 spawn 永遠拿到 1 個 dedicated gateway slot。

---

## 7. Cascade 規則（概念）

對 worker 完成事件做的狀態轉移：

- **Builder proved** → goal `proved`
- **Builder failed** → `attempts++`；若達 SHELVE_THRESHOLD → `shelved` 並上拋
- **Backward success** → goal `attempting`（還沒 proved，等 Verify）
- **Backward failed** → 同 Builder 的 attempts 處理
- **Forward success** → 新 goal INSERT、origin='forward'、detached=1、sorry-free → 直接 proved（leaf-bypass）、sorry-bearing → open + 等 BFS（Curry-Howard 後 def/structure/class 跟 theorem 一致對待）
- **Forward failed** → 不影響任何既有 goal、只 fill 對應 strategist_decision row 的 outcome
- **Strategist** → 多 row INSERT 到 `strategist_decisions`、各 decision_kind 各自副作用（Inject 走 enqueue + 必要時 reopen/detached + entry_kind pin / ConfirmShelve 走 `_set_goal_terminal_and_propagate(shelved)` / EmitDirective 寫 problems.strategist_directive）

Verify 的 `succeeded`/`dead` 轉移在 `verify_housekeeping` 內套；同時 G1 shelved-revival pass 把「shelved goal aliased to 已 proved 的 Forward output」自動生 alias body + 轉 proved + 上拋（不走 cascade、housekeeping 內 inline）。

**inject_batch_done 觸發**：每筆 Inject decision 寫 `strategy_decisions.outcome`；當 batch 內所有 row 都 outcome 非 NULL、`db.maybe_enqueue_inject_batch_done` enqueue 一筆 Strategist task on root + trigger_kind=`inject_batch_done`。同 root in-queue dedup。

**Shelve 上拋**：goal `shelved` 會殺掉所有「依賴它做 sub-goal」的 parent strategy；parent goal 若無 live strategy → attempts++ → 視情況自己也 shelve、繼續上拋。

`open_goals` 用 recursive CTE 過濾掉 dead/superseded 分支下的 orphan sub-goal，所以 dispatcher 不會浪費 spawn 在死樹枝上。`detached=1` 的 goal 額外 union 進 alive seed（Forward output / Strategist Reopen with broken chain 用）。

---

## 8. OR 順序展開（passive）

每個 Goal 同時只跑一條 Strategy。這一條死了（sub-goal cascade-shelve 或 Verify 失敗）才生下一條。

- 收益：強模型下 token 不浪費、tree 簡單
- 成本：第一條走錯方向時 wall-clock 比 eager 慢
- 緩解：SHELVE_THRESHOLD 拉高 + 給 Backward agent 看「過去死掉的 Strategy 已經試過什麼分解」的提示

每條 Strategy 對 parent goal 都用 strategy-isolated 的檔名（`_strategy_s<sid>.lean` + sub-goal slug 含 `s<sid>_` 前綴），parent 的 `lean_path` 只在 Verify 勝出時被改。

---

## 9. Dedupe（同 problem 內 sub-goal 共享）

Backward 拆出新 sub-goal 時、框架查 DB 看是否有 statement 等價的既有 goal。命中就：
- 不 INSERT 新 goal、`strategy_subgoals` link 到 canonical
- sub-goal 的檔寫成 alias、body 是 `apply <canonical> <;> assumption`

等價判定走 Lean kernel `apply @<canonical> <;> assumption` probe（單一 batch lake-env 呼叫、所有候選一次比完、容忍 hypothesis-extension）。Schema 零改動、靠 `strategy_subgoals` 多對多就把 DAG 變成 graph。命中失敗（statement 解析爛）一律 fail-open、不阻斷主流程。

候選池（Backward dedupe）：
1. 嚴格 ancestor chain（lifetime 對齊、無 import cycle 風險）
2. 同一 parent 的 orphan-proved sub-goal（sibling Strategy 死了但 sub-goal 留下）
3. 跨 branch 的任何 `proved` goal（proved 無下游依賴、無 cycle 風險）
4. 同 problem 的 `disproved` goal（Phase 2、命中 = "agent 已給過反例、別再提"、整批 Backward proposal abort 走 `same_as_disproved`）

**G1 shelved-revival**（Forward 端、反向 link）：Forward 落地新 goal X 時、跑 `find_shelved_revivals_for_forward`：對同 problem 內 shelved goals S 探「`apply @X <;> assumption` 能否 discharge S」。命中 → `set_alias_target(S, X)`（注意方向是 shelved 指向新 Forward、跟標準 dedupe 反向）；此時 X 尚未 proved、不寫 alias body。當 X 後續 reach proved、`verify_housekeeping` 的 revival pass 偵測 `S.alias_target_id == X AND X.status='proved'`、套 `build_alias_content` 重寫 S.lean_path、`_set_goal_terminal_and_propagate(S, 'proved')`、parent strategy `ready_for_verify` 自然收尾。設計用例：Strategist 為「頂掉某條 shelved sub-goal」inject 的 Forward 跟原 shelved 同形時、不必 Strategist 自己回頭 Reopen。

---

## 10. Root integrity gate

Root 翻 proved 那一刻 daemon 對該 problem 跑 `verify.root_integrity_gate` —
`axiom_probe(Problems.<p>.Root, main)` 比對 Manifest `axioms_whitelist`、
偵測到 sorryAx 就走 `bisect_sorryax_source` + `rollback_cascade_chain`、
把元凶 strategy 撤回、下次 dispatcher tick 重 Backward。

這是 verify-collapse 設計下「唯一一次 Lean elaboration」的時機 —
per-level `verify_strategy` 純 mechanical alias rewrite。
gate 強制執行：Manifest 沒設 `axioms_whitelist` 時 fallback 到
framework default `(Classical.choice, propext, Quot.sound)` + log warning、
**不** 因 optional field 缺席而 skip（framework safety invariant）。

**觸發語意**：gate 由 `goals.integrity_verified` marker 守。pass → set 1、
之後 daemon tick 不重跑；任何把 root status 翻離 'proved' 的路徑（cascade
rollback、operator 手動 reset、未來 reseed）由 `db.update_goal_status`
自動清 marker、root 重新進 proved 時 gate 再 fire。dispatcher query
`db.unverified_proved_roots` 返回「proved AND marker=0」的 problem 名單、
取代舊「每 tick 對所有 manifest 重跑 axiom_probe」設計（單 daemon run
244 個 benchmark stall ~110min 的觀察、commit history 內可查）。

**Library promotion 自動機制已停用**：`Tooling/quality/library.py`（含
`promote` / `maybe_promote` / topic 推斷 + INDEX 維護）保留為 dormant code、
等之後依「人手決定哪些 problem 該進 Library」的新機制重新接上。

---

## 11. Pipeline 分檔（程式碼結構）

```
Tooling/pipeline/
  __init__.py    — shared helpers + DTO + re-export + /register + /release
  builder.py     — run_builder + Phase 1 (hint) + Phase 2 (LLM patch)
  backward.py    — run_backward + decomposition + sub-goal placement
  forward.py     — run_forward + 新 toolkit lemma 落地 + G1 shelved-link
  strategist.py  — run_strategist + parse_decision + commit_decisions
  _retry.py      — kind-agnostic in-pipeline retry helper（Phase 7）
  _assembly.py   — Backward 後段：sub-goal 檔搬遷 + strategy_subgoals 寫入
  _axiom.py      — axiom_probe wrapper + sorryAx bisect
  _cite_gate.py  — cited sibling 必須 proved 守門（Backward leaf-bypass + Builder commit）
  _drafts.py     — timeout postmortem 進度筆記持久化
  _infra.py      — _INFRA_REASONS 等
  _lake.py       — lake build invocation
  _reflection.py — proved/success/decline 後跑、寫 lessons / brief
  _skeleton.py   — strategy skeleton + alias promotion + 統一 (theorem|def|structure|class) 解析
  events.py      — Context.md `Goal history` 段的 4 條 SQL 投影
```

`compile_context`（Builder/Backward/Forward 共用）在 `Tooling/agent/context.py`、`compile_strategist_context` 在 `Tooling/agent/phase2_context.py`、`Tooling/agent/runtime.py` 只剩 WorkArea + spawn_llm。

---

## 12. Context.md：agent 唯一介面

每次 spawn 之前、框架從 DB 編一份 Context.md 寫進 `.attempts/<pid>/`。**agent 看到的所有訊息都從這裡來**（companion file 是備援、agent 經常不主動讀）。

Builder / Backward / Forward 共用 `compile_context`（`Tooling/agent/context.py`）；Strategist 自己一支 `compile_strategist_context`（`Tooling/agent/phase2_context.py`）。

### Builder / Backward / Forward sections（順序固定）

```
Goal statement
Sandbox（讀寫權限邊界 + 框架預寫的檔名約定）
Strategy naming                   ← Backward 才有；agent 自選 sub-goal 描述性 slug
Parent goal & strategy            ← origin='backward' 才有
Forward brief                     ← Forward only：Strategist Inject 的 brief
Library inventory                 ← Forward only：avoid 重複提案
Forward history                   ← Forward only：past Forward outputs
Mathlib hints
FORBIDDEN_LEMMAS
Strategic notes
Proved goals on this problem      ← grep 入口指針、0 個則整段省略
Your previous progress note       ← timeout 後留下的進度筆記
Goal history (umbrella)           ← Builder/Backward only：4 sub-section
```

### Strategist sections（順序固定）

```
Trigger                                  ← trigger_kind + 若 pending_review 帶 target
Pending review failure / strategies / ancestors  ← pending_review only
Completed Inject batches                 ← Phase 2.5：任何 trigger、有未 ack 的 batch 就顯
Pending reopen-promises                  ← G2：trigger=inject_batch_done 且 batch_id link 完整時、只列 promised 那筆 shelved goal
Active goals                             ← 非 terminal status 的 goal 速覽
Recent decisions                         ← 最近 Strategist 自己決策 + outcome
TREE                                     ← problem 樹狀 snapshot
Manifest meta                            ← first_launch / amend-relevant 時
```

`Goal history` umbrella 4 sub-section（`Direct attempts on this goal` / `Sibling decompositions that failed Verify` / `Strategies whose decomposition died` / `Sub-goals reported infeasible`）的 event 投影邏輯在 `Tooling/pipeline/events.py`。`infeasible_sub` 是 cross-goal 投影：sub-goal 的 `agent_infeasible` 反向投到 parent goal 的 next Backward。完整設計見 `docs/archive/goal_history_unified.md`。

`Proved goals on this problem` 是 Phase 4 加的入口指針 — 只給 count + path、不 push candidate list。agent 用 grep + Read 自食其力（同 mathlib 的 grep + loogle 模式）。每個 proved goal 的 `.lean` 檔頂被 Builder / Verify 寫上 `-- <slug>: <summary>` annotation block、grep 時這就是索引。`## Past wins on this problem (playbook)` section Phase 3 退役（commit `5be9a33`）— 被這條取代。

---

## 13. 不做（什麼東西在這個系統不存在、為什麼）

| 不做 | 原因 |
|---|---|
| 'running' state 在 pipelines 表 | 只放 finished rows，daemon 死了不留 zombie |
| Active cancellation propagation 表 | cascade 入口 no-op 已被動接住 OR 落敗者 |
| 額外 worker_kind（Generalizer / Refuter / ConstructionSearch） | schema 留洞、實作 deferred；Forward / Strategist 已 Phase 2 上線 |
| 主動清 OR 落敗 strategy 檔 | 留 forensics；root proved 後 dispatcher exit 自動 reconcile + prune 一次（也有 `asterism prune` 給手動跑） |
| 跨 problem 的 OR pool / 並發 | 等 Library 階段才有意義 |
| events 表 audit log | dead_attempts.artifacts JSON + stdout 夠 |
| `commit_state` pending/live 兩段式 | backup-restore + `os.replace` 夠用 |

---

## 14. 不變量（修改前先看）

- Cascade 永遠主 loop sequential、絕不在 worker thread
- Worker thread 只 INSERT finished pipeline row、不更新 goal/strategy 狀態
- `pipelines` 表只存 finished rows
- `.attempts/<pid>/` 在 `WorkArea.__exit__` unconditional rmtree（agent 輸出先打包進 `dead_attempts.artifacts`）
- Worker_kind ↔ target_kind 對應：Builder/Backward → Goal、Forward → Problem、Strategist → Goal (root)；Verify 不是 worker_kind
- Strategy 的 `scratch_path` 一旦被 INSERT 後 immutable
- `goals.lean_path` UNIQUE；`strategies.lean_path` 不 UNIQUE（多 strategies 共享 parent target）
- Backward sub-goal slug 必含 `s<sid>_` 前綴（防 sequential strategies 命名碰撞）
- Schema 修改要 bump 版本 + 寫 migration（不能光改 CHECK constraint）
- Strategist 的 `ConfirmShelve` 不能單獨送、必須跟 `Inject` 同 decision array；同 array 內所有 row 共享 batch_id（含 ConfirmShelve）— G2 機制靠這條 link 把 promise 跟 follow-up 配對
- `strategist_decisions.batch_id` 一旦寫入後 immutable；framework 用「所有 row outcome 非 NULL」推導 batch 完成
- Forward output goal 必 `detached=1`（無 strategy 上游、靠 detached seed 進 alive set）

---

## 15. 已證題目

| Problem | Prover | Wall-clock | 備註 |
|---|---|---|---|
| compactness | Opus / Sonnet | ~25 / ~60 min | |
| gen_generates | Sonnet | ~30 min | |
| inner_zero_iff_smul | Sonnet | ~21 min | |
| proj_nonexpansive | Sonnet | ~58 min | |
| cantor_xi_measure | Sonnet | ~4 hr | |
| sylvester_gallai | Sonnet / Opus | 4h16min / 2h48min | Kelly 1948、Freek-100、mathlib 沒有 |
| sl2_v_n_irreducible | — | — | (見 git history) |
| residue_thm | Sonnet+Opus mix | ~6 hr | Cauchy Residue Theorem、PhD-level mathlib gap、Strategist Phase 2 第一個 stress test、8 個 framework 修 |
| pi1_circle | Sonnet+Opus mix | 140 min | π₁(S¹) ≅ ℤ、24 個 sub-goals、0 framework 修（soft signal）|

進行中：`Topology.brouwer_fixed_point`（singular homology spine、Phase 2 stress on G1/G2/Curry-Howard/parallel-Forward 等改動）。
