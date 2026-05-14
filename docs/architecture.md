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

## 2. 兩個 worker、一個 housekeeping

**Worker 是 LLM 介入點，純框架操作不佔 worker slot。** 這條原則決定下面三個角色的位置。

| 角色 | 對誰 | 做什麼 | 有 LLM 嗎 |
|---|---|---|---|
| **Builder** | Goal | 試一輪 deterministic tactic、不行就請 LLM 寫一份 patch 收尾 | 第二階段有 |
| **Backward** | Goal | 請 LLM 把這個 Goal 拆成一條 Strategy + N 個 sub-Goal | 有 |
| **Verify housekeeping** | Strategy | sub-Goal 全 proved 後，把 Strategy 組裝起來編譯、寫進 parent 的 `.lean` 檔 | 沒有 |

Verify 早期是第三種 worker_kind；後來砍成 dispatcher 主迴圈末端的步驟，因為它既無 LLM 也不該佔 pool 格子。

每個 Goal 最多同時一條 Builder 或一條 Backward 在跑（passive OR、cap=1）。死掉之後才生下一條。早期是 eager fanout（同 Goal 並行多條 Strategy），實證在強模型下純粹浪費 token。

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

DB schema 見 `Tooling/db.py`（程式碼即文件）；7 張表的意義：

- `problems` — 註冊表
- `goals` — graph 的 OR 節點，含 `entry_kind`（Builder/Backward 第一手怎麼派、可被 cascade `agent_declined` 改寫成 `Backward`）、`status`（open/attempting/proved/shelved）、`alias_target_id`（dedupe）。Phase 7 後 retry 在 pipeline 內共用同一 claude session、不再用 DB column 跨 pipeline 攜帶 sid
- `strategies` — graph 的 AND 節點，含 `lean_path`（parent 的目標檔，**Verify 勝出才會被改**）、`scratch_path`（這條 Strategy 獨佔的組裝檔）
- `strategy_subgoals` — 多對多，dedupe 把重複 sub-Goal 收成同一個 row
- `pipelines` — 只放 finished rows，沒有 'running' 狀態（daemon 死了重啟見乾淨表面）
- `dead_attempts` — 失敗的 forensic（所有 agent 輸出 artifact 全留在 JSON 欄）
- `queue` — dispatch ready 的 (kind, target_id) 排隊

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

## Entry kind          ← Builder | Backward；root Goal 第一手怎麼派
Backward

## Lemma hints
- <hint 1>
- ...

## Strategic notes
<自由 markdown，注入給 agent 看>
```

`init` 寬解：缺欄位給 default + warning，不 crash。

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

每個 tick 做四件事，順序固定：

```
1. cascade — 收割上一輪完成的 worker，更新 goal/strategy 狀態
2. verify housekeeping — 撈所有 sub-goal 全 proved 的 strategy、組裝、編譯、寫 alias 進 parent
                         （遞迴最多 8 圈，深度 4 的題一輪可以連帶 4 層）
3. 若 root proved → reconcile + prune + library promote + tree refresh，退出
4. bfs_refill + spawn — 把 open Goal 排進 queue、有空格就 spawn
```

**紀律**：cascade 永遠在主線程 sequential（worker thread 只 INSERT finished pipeline row、絕不直接改 goal/strategy 狀態）。這條規則消除了所有 OR-race 災難。

---

## 7. Cascade 規則（概念）

對 worker 完成事件做的狀態轉移：

- **Builder proved** → goal `proved`
- **Builder failed** → `attempts++`；若達 SHELVE_THRESHOLD → `shelved` 並上拋
- **Backward success** → goal `attempting`（還沒 proved，等 Verify）
- **Backward failed** → 同 Builder 的 attempts 處理

Verify 的 `succeeded`/`dead` 轉移在 `verify_housekeeping` 內套，不走 cascade（因為它根本不是 worker）。

**Shelve 上拋**：goal `shelved` 會殺掉所有「依賴它做 sub-goal」的 parent strategy；parent goal 若無 live strategy → attempts++ → 視情況自己也 shelve、繼續上拋。

`open_goals` 用 recursive CTE 過濾掉 dead/superseded 分支下的 orphan sub-goal，所以 dispatcher 不會浪費 spawn 在死樹枝上。

---

## 8. OR 順序展開（passive）

每個 Goal 同時只跑一條 Strategy。這一條死了（sub-goal cascade-shelve 或 Verify 失敗）才生下一條。

- 收益：強模型下 token 不浪費、tree 簡單
- 成本：第一條走錯方向時 wall-clock 比 eager 慢
- 緩解：SHELVE_THRESHOLD 拉高 + 給 Backward agent 看「過去死掉的 Strategy 已經試過什麼分解」的提示

每條 Strategy 對 parent goal 都用 strategy-isolated 的檔名（`_strategy_s<sid>.lean` + sub-goal slug 含 `s<sid>_` 前綴），parent 的 `lean_path` 只在 Verify 勝出時被改。

---

## 9. Dedupe（同 problem 內 sub-goal 共享）

Backward 拆出新 sub-goal 時，框架查 DB 看是否有 statement 等價的 ancestor 或 orphan-proved 的 sibling。命中就：
- 不 INSERT 新 goal、`strategy_subgoals` link 到 canonical
- sub-goal 的檔寫成 alias，body 是 `apply <canonical> <;> assumption`

等價判定用 Lean kernel `isDefEq`（單一 batch lake-env 呼叫、所有候選一次比完）。Schema 零改動，靠 `strategy_subgoals` 多對多就把 DAG 變成 graph。命中失敗（statement 解析爛）一律 fail-open，不阻斷主流程。

候選池：
1. 嚴格 ancestor chain（lifetime 對齊、無 import cycle 風險）
2. 同一 parent 的 orphan-proved sub-goal（sibling Strategy 死了但 sub-goal 留下）
3. 跨 branch 的任何 `proved` goal（最近開放，proved goal 沒下游依賴所以無 cycle 風險）

---

## 10. Library promotion

Root proved 後框架把這個 problem 的 goal tree 重新組裝、promote 進 `Library/<Topic>/`，下次別的 problem 就能在 `Lemma hints` 寫 `Library.<Topic>.<problem>` 引用。Axiom-gated（白名單外的軸不 promote）、idempotent。跨 problem 的 dedupe / lemma reuse 走這條路。

---

## 11. Pipeline 分檔（程式碼結構）

```
Tooling/pipeline/
  __init__.py    — shared helpers + DTO + re-export
  builder.py     — run_builder + Phase 1/2
  backward.py    — run_backward + decomposition + sub-goal placement
  _lake.py       — lake build invocation
  _skeleton.py   — strategy skeleton + alias promotion
  _drafts.py     — partial-output 持久化
```

`compile_context` 在 `Tooling/agent/context.py`、`Tooling/agent/runtime.py` 只剩 WorkArea + spawn。pipeline 分檔已完成（commit `9638eed`）。

---

## 12. Context.md：agent 唯一介面

每次 spawn 之前，框架從 DB 編一份 Context.md 寫進 `.attempts/<pid>/`。**agent 看到的所有訊息都從這裡來**（companion file 是備援、agent 經常不主動讀）。

當前 sections（順序固定）：

```
Goal statement
Sandbox（讀寫權限邊界 + 框架預寫的檔名約定）
Strategy naming                   ← Backward 才有；agent 自選 sub-goal 描述性 slug
Parent goal & strategy            ← origin='backward' 才有
Mathlib hints
FORBIDDEN_LEMMAS
Strategic notes
Library available
Proved goals on this problem      ← grep 入口指針，0 個則整段省略
Your previous progress note       ← timeout 後留下的進度筆記
Goal history (umbrella):
  ### Direct attempts on this goal           (kind-agnostic；含 agent_declined 子類)
  ### Sibling decompositions that failed Verify (kind=Backward/None gate)
  ### Strategies whose decomposition died     (kind-agnostic)
  ### Sub-goals reported infeasible           (cross-goal、kind=Backward/None gate)
```

`Goal history` umbrella 來自 v1（C1 + C2 + C3、commit 8712ce5 onward）— 舊版四個獨立 `##` section 合併、event 投影邏輯抽到 `Tooling/pipeline/events.py` 的 4 個函數。`infeasible_sub` 是 cross-goal 投影：sub-goal 的 `agent_infeasible` 反向投到 parent goal 的 next Backward。完整設計見 `docs/archive/goal_history_unified.md`、reason→event 對照見 `docs/failure_modes.md` §3。

`Proved goals on this problem` 是 Phase 4 加的入口指針 — 只給 count + path，不 push candidate list。agent 用 grep + Read 自食其力（同 mathlib 的 grep + loogle 模式）。每個 proved goal 的 `.lean` 檔頂被 Builder / Verify 寫上 `-- <slug>: <summary>` annotation block（goal_naming_annotation Phase 2，cc934ff），grep 時這就是索引。playbook 機制 + `## Past wins on this problem (playbook)` section 在 Phase 3 退役（5be9a33）— 被這條取代。

---

## 13. 不做（什麼東西在這個系統不存在、為什麼）

| 不做 | 原因 |
|---|---|
| 'running' state 在 pipelines 表 | 只放 finished rows，daemon 死了不留 zombie |
| Active cancellation propagation 表 | cascade 入口 no-op 已被動接住 OR 落敗者 |
| 額外 worker_kind（Forward / Generalizer / Refuter / ConstructionSearch / Strategist） | schema 留洞、實作 deferred；先把 Builder/Backward 跑穩 |
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
- Worker_kind ↔ target_kind 只一一對應 Goal；Verify 不是 worker_kind
- Strategy 的 `scratch_path` 一旦被 INSERT 後 immutable
- `goals.lean_path` UNIQUE；`strategies.lean_path` 不 UNIQUE（多 strategies 共享 parent target）
- Backward sub-goal slug 必含 `s<sid>_` 前綴（防 sequential strategies 命名碰撞）
- Schema 修改要 bump 版本 + 寫 migration（不能光改 CHECK constraint）

---

## 15. 已證題目

| Problem | Prover | Wall-clock |
|---|---|---|
| compactness | Opus / Sonnet | ~25 / ~60 min |
| gen_generates | Sonnet | ~30 min |
| inner_zero_iff_smul | Sonnet | ~21 min |
| proj_nonexpansive | Sonnet | ~58 min |
| cantor_xi_measure | Sonnet | ~4 hr |
| sylvester_gallai | Sonnet / Opus | 4h16min / 2h48min |

SG 是當前最深 sample（Kelly 1948 證法、Freek-100、不在 Mathlib 內）。
`docs/STATUS.md` 是 canonical 狀態。
