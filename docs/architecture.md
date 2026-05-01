# Asterism — 架構文件 v2.5

寫於 2026-04-30。前次設計診斷見 `D:/Hadamard/docs/asterism_postmortem.md` 與 `asterism_factor_analysis.md`，前次完整 v3 架構（一次設計 8 pipeline kind）存於 `D:/Hadamard/docs/asterism_archive/`。

本檔反映 commit `39df821` 後的實作現況。三題 from-scratch proved（wilson / compactness / cantor）；核心架構穩定 + Deduper 上線、後續按 §13 排序加 feature。

---

## 0. Status

| 項目 | 狀態 |
|------|------|
| Wilson (Freek 100 #51) | proved、commit 6b0cf3b、~15 min |
| Compactness (propositional, custom Defs) | proved、commit 46c8941、~60 min、~2.5x faster than Hadamard 2.5h |
| Cantor (Freek 100 #63 reformulated) | proved、commit 6bd6c15、~5 min、單 Builder one-shot、axioms = `[]` |
| Pipeline kinds | Builder + Backward + **Verify**（3 種、每 kind 有固定 target_kind） |
| OR parallelism | F37 起 passive (cap=1)；同 goal 多策略走序列觸發、不再並行 fanout |
| Deduper | 開（whitespace-norm 字串等價、§9.5）、無 schema 改動 |
| Unit tests | 79 passing |
| Tooling LOC | ~1700 lines Python |
| Axioms whitelist | `[propext, Classical.choice, Quot.sound]`（題級、cantor 為 `[]`） |

---

## 1. AND/OR graph

二分圖、兩種節點交替：

```
Goal      = OR    : 任一 Strategy 成功 → Goal 成功
Strategy  = AND   : 所有 sub-Goal 成功 → Strategy 成功
```

整個推理樹由 `goals` × `strategies` × `strategy_subgoals` 三表表達。

葉子 Goal 不靠 Strategy 證明、靠 Builder 直接 closure（tactic_try → tactic_llm）。Strategy 必有 ≥ 1 個 sub-goal、否則無法被 `strategies_ready_for_verify` 撈到。

OR 順序展開（§9）：同 Goal 至多一條 active Strategy；當前 strategy 死亡（sub-goal cascade-shelve / Verify 失敗）後才觸發新一輪 Backward 產 next strategy。F37 之前為 eager OR fanout、現為 passive trigger。

---

## 2. 目錄結構

```
Asterism/
├── asterism.db                 # ★ Single source of truth (sqlite + WAL)
├── Tooling/                    # 純 Python dispatcher / pipeline / agent / cli
├── tests/                      # pytest（純函數 + cascade 狀態機）
├── docs/architecture.md        # 本檔
└── Problems/<problem>/
    ├── Manifest.md             # 唯一人手檔
    ├── Defs.lean               # problem-specific definitions（cli init 自動 import）
    ├── Root.lean               # 自動生成；Verify 勝者 alias 寫入此檔
    └── proofs/
        ├── _strategy_s<sid>.lean      # 每條 Strategy 的 patch lean module
        └── L_<slug>.lean              # 每個 sub-goal lean
                                       # winner chain + OR loser orphans 共存
                                       # （`asterism prune` 是後續 task）
```

對照 Hadamard 砍掉：META / HINTS / STATUS / OPEN / SHELVED / LOG / POSTMORTEM / TWIN_SIGNALS / Dead/ — 7 個 markdown + 1 子樹合進 DB + Manifest.md。

---

## 3. Manifest.md（唯一人手 metadata）

```markdown
---
problem: wilson
axioms_whitelist: [propext, Quot.sound, Classical.choice]
forbidden_lemmas:
  - ZMod.wilsons_lemma
  - Nat.Prime.wilsons_lemma
---

# wilson — Freek 100 #51 reformulated on Nat

## Statement
∀ p : ℕ, p.Prime → Nat.factorial (p - 1) % p = p - 1

## Difficulty
4

## Mathlib hints
- ZMod.val_natCast (Data/ZMod/Basic.lean:89)
- Nat.Prime.two_le

## Strategic notes
此題 reformulated 過、ZMod 形式直接用會被擋；要走 Mathlib bridge。
```

YAML frontmatter 是結構化必填；body 自由 markdown，由 `init` 解析 statement + difficulty 進 DB、hints + notes 在 worker spawn 時注入 Context.md。

`manifest.parse` 寬解：缺欄位給 default + warning，不 crash。

---

## 3.5 Root.lean lifecycle (F15)

`Root.lean` 是框架管理的檔，**不是** user-written sketch。三個生命週期狀態：

**狀態 A — 初始（`asterism init <p>` 寫入）**
```lean
import Mathlib
import Problems.<p>.Defs

namespace Problems.<p>

theorem main : <stmt> := by sorry

end Problems.<p>
```

`init` 在 Root.lean 不存在時自動寫入這個 sorry-stub 形態。`<stmt>` 取自 Manifest.md 的 `## Statement`。

**狀態 B — 過程（Asterism 執行中）**
框架在 `proofs/` 下產生 `_strategy_s<NN>.lean`（每個 Backward 候選 strategy 一份）跟 `L_<slug>.lean`（每個 sub-goal 一份），**Root.lean 本身不動**。

**狀態 C — 證完（`prune.reconcile_proved_goals` 自動寫回）**
當 `dispatcher.run` 偵測 root proved，cleanup 階段把 Root.lean 改寫成 wrap form：
```lean
import Mathlib
import Problems.<p>.Defs
import Problems.<p>.proofs._strategy_s<NN>

namespace Problems.<p>

theorem main : <stmt> := s<NN>

end Problems.<p>
```
其中 `s<NN>` 是 Verify 通過的 winning strategy。完整證明 body 留在 `_strategy_s<NN>.lean`，Root.lean 是薄 indirection 層。

**Init guard（F15）**
為防止操作者誤改 Root.lean 後重 init 造成靜默 wrap，`init` 偵測現有 Root.lean 的 `theorem main := <body>` 形態：
- `:= by sorry` → 狀態 A，OK
- `:= s<digits>` → 狀態 C，視為已證（noop）
- 其他 → reject，要求 `--force` 才能繼續

`--force` 適用於使用者**故意**手寫 sketch 給 Backward 起手提示的情況（不常見）。

**這個生命週期意味著**：
- 永遠不要手動編 Root.lean — 從 `:= by sorry` 開始，讓框架接管
- `_strategy_s<NN>.lean` 才是「真實證明所在」；Root.lean 只是 entry point
- 多個 strategy 並存於 `proofs/` 是正常的；root_proved 後 `prune` 會清掉 loser orphans

---

## 4. DB Schema

```sql
CREATE TABLE problems (
    name           TEXT PRIMARY KEY,
    manifest_path  TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem     TEXT    NOT NULL REFERENCES problems(name),
    slug        TEXT    NOT NULL,
    lean_path   TEXT    NOT NULL UNIQUE,
    statement   TEXT    NOT NULL,
    difficulty  INTEGER NOT NULL DEFAULT 4,
    -- kind / origin enums kept minimal; extend in a migration when
    -- forward / generalizer / refuter / conjecture / construction land.
    kind        TEXT    NOT NULL DEFAULT 'theorem'
                    CHECK(kind IN ('theorem')),
    origin      TEXT    NOT NULL
                    CHECK(origin IN ('root','backward')),
    status      TEXT    NOT NULL
                    CHECK(status IN ('open','attempting','proved','shelved')),
    depth       INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(problem, slug)
);

-- lean_path: 此 strategy 的「目標」(parent goal 的 lean_path)。NOT UNIQUE
--   — 同 goal 多 strategies 共享 target。Verify 勝者 alias 寫入此 path。
-- scratch_path: 此 strategy 獨佔的 patch lean module
--   (Problems/<p>/proofs/_strategy_s<sid>.lean)。Verify 之前 lake build 此檔。
-- 'superseded': 同 goal 另一 strategy 已贏 Verify;
--   此 strategy 工作作廢、orphan-filter 跳過其 sub-goals。
CREATE TABLE strategies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id      INTEGER NOT NULL REFERENCES goals(id),
    lean_path    TEXT    NOT NULL,
    scratch_path TEXT    NOT NULL DEFAULT '',
    status       TEXT    NOT NULL
                     CHECK(status IN ('proposed','succeeded','dead','superseded')),
    proposal_md  TEXT    NOT NULL DEFAULT '',  -- Backward's PROPOSAL.md verbatim
    created_by   TEXT    NOT NULL REFERENCES pipelines(id),
    created_at   TEXT    NOT NULL
);

CREATE TABLE strategy_subgoals (
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    subgoal_id  INTEGER NOT NULL REFERENCES goals(id),
    position    INTEGER NOT NULL,
    PRIMARY KEY (strategy_id, subgoal_id)
);

-- 只存 finished rows、無 'running' state；daemon 死掉重啟見乾淨表面。
CREATE TABLE pipelines (
    id          TEXT PRIMARY KEY,                 -- UUID
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK(target_kind IN ('Goal','Strategy')),
    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    outcome     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

-- artifacts: JSON dict {filename: text} 含 PROPOSAL/patch/Context 全文。
-- .attempts/<pid>/ 純 ephemeral、pipeline 結束 rmtree、DB 是 SoT。
CREATE TABLE dead_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id       INTEGER NOT NULL,
    target_kind     TEXT NOT NULL,
    pipeline_id     TEXT NOT NULL REFERENCES pipelines(id),
    failure_reason  TEXT NOT NULL,                -- enum, see §6
    failure_detail  TEXT,
    proposal_md     TEXT,
    artifacts       TEXT,                         -- JSON dict
    ts              TEXT NOT NULL
);

CREATE TABLE queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    -- worker_kind 決定 target_kind: Builder/Backward → Goal、Verify → Strategy。
    -- 不需要單獨 target_kind 欄位。
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
```

**Index**：`idx_goals_status`、`idx_pipelines_status`、`idx_queue_priority`（priority DESC, id ASC）。

**WAL mode**：`db.connect()` 開 `PRAGMA journal_mode=WAL`，多 worker 並發寫 dead_attempts/pipelines 不互鎖。

**Schema 留洞策略**：CHECK 只接受目前實作中的值；新增 origin（forward / generalizer / refuter）時做 migration 加 enum、不預先放 unreachable 字串。

**Atomicity 改用 Hadamard backup-restore**：integrator 跑完 lake build 前先備份、build fail 還原。run_verify 改用 `os.replace` 原子 rename + backup 檔。沒 commit_state 兩段式。

---

## 5. Pipeline kinds（3 種）

每 kind 有固定 target_kind、不需要 dispatcher 推斷。

### 5.1 Builder（target_kind='Goal'）

對 fresh sorry-stub goal 嘗試直接 closure。

**Phase 1 — `tactic_try`（無 agent、純 script）**：
觸發條件：`goal.attempts == 0` AND `_is_sorry_stub(source)`。

跑 `[rfl, simp, decide, trivial, omega, linarith, nlinarith, norm_num, simp_all, aesop]` 10 條、第一條 lake-build 過就 outcome='proved'。

`_is_sorry_stub` regex 嚴格匹配 `:= by sorry` 結尾、保護結構化 patch 不被 textual 替換 corrupt（W2 防禦）。

**Phase 2 — `tactic_llm`（spawn agent）**：
```
1. compile_context → Context.md
2. spawn claude --add-dir Problems/<p>/ --add-dir attempts_dir
3. agent 寫 PROPOSAL.md + patch.lean
4. forbidden_lemmas grep on patch
5. backup parent.lean_path → copy patch over → lake build
6. pass: 留 patch、outcome='proved'
   fail: 還原 backup、record dead_attempt(reason='lake_build_error')
```

**Outcome**：`proved` / `exhausted`（Phase 1 全敗、attempts==0 + non-stub 跳過 Phase 1 也算）/ `failed`（forbidden / agent_no_response）。

### 5.2 Backward（target_kind='Goal'、OR-aware）

OR 並行下、同 goal 可同時跑多條 Backward。每條獨立寫 strategy-isolated 檔。

```
1. INSERT strategy 取得 sid（placeholder paths、status='proposed'）
2. compile_context with strategy_id=sid → Context.md（含 ## Naming convention 區）
3. spawn claude --agent backward
4. agent 必輸出（命名遵守 Context.md 約定）：
   - PROPOSAL.md
   - patch_<parent_slug>.lean
       theorem <sid_token>_<parent_slug> : <statement> := by ...
       (NOT theorem <parent_slug> — 與 parent's Root.lean 衝突)
   - new_<sid_token>_<parent_slug>_sub_<N>.lean × N
5. 驗證 slug 格式（不符 → naming_violation、strategy='dead'）
6. forbidden_lemmas grep 全文件
7. 寫檔到永久路徑：
   - sub-goals: Problems/<p>/proofs/L_<full_slug>.lean
   - scratch:   Problems/<p>/proofs/_strategy_s<sid>.lean
8. lake build sub-goals + scratch
9. pass: INSERT N 個 sub-goals + N 個 strategy_subgoals + UPDATE strategy.scratch_path
   fail: unlink 此 strategy 的所有檔、strategy='dead'、record dead_attempt
```

parent 的 lean_path **不被 Backward 改動**（保持 sorry）、由 Verify 在勝出時改寫。

**Outcome**：`success` / `exhausted`（agent 不回 valid output）/ `failed`（forbidden / lake_build / naming_violation / agent_no_response）。

### 5.3 Verify（target_kind='Strategy'、無 agent、純 script）

觸發條件：strategy 的全部 sub-goals 都 proved AND 自己 status='proposed' AND 自己 goal_id 對應的 goal 未被 sibling 證掉。

```
1. 早期退出: 若 strategy='superseded' 或 goal='proved' → outcome='failed' reason='superseded'
2. lake build scratch_path（重編譯、確認 patch 對 now-real sub-goal proofs 仍 elaborate）
3. backup parent.lean_path → 寫 alias 到 parent.lean_path（atomic os.replace）
   alias 內容:
       <orig imports>
       import Problems.<p>.proofs._strategy_s<sid>
       namespace Problems.<p>
       theorem <parent_slug> : <statement> := s<sid>_<parent_slug>
       end Problems.<p>
4. lake build parent.lean_path
5. pass: outcome='proved'、刪 backup
   fail: 還原 parent.lean_path、record dead_attempt(reason='lake_build_error')
```

**Outcome**：`proved` / `failed`。

---

## 6. Context.md（Asterism 對 Hadamard 唯一真實改進）

每次 worker spawn 前、dispatcher 從 DB 編譯一份 Context.md 寫進 attempts_dir。Sections（順序固定）：

```markdown
# Context for goal <slug>

## Goal statement
<statement>

## Naming convention (REQUIRED)            ← only when strategy_id given (Backward)
This Backward attempt has been allocated strategy id `s<sid>`.
- Sub-goal slugs: `s<sid>_<parent>_sub_1`, ...
- Sub-goal filenames: `new_s<sid>_<parent>_sub_<N>.lean`
- Patch filename: `patch_<parent>.lean`
- Patch theorem name: `s<sid>_<parent>` (NOT `<parent>`)
- Patch imports: `import Problems.<p>.proofs.L_s<sid>_<parent>_sub_<N>`

## Parent goal & strategy                  ← only when goal.origin='backward'
This goal `<sub_slug>` is a sub-goal of `<parent_slug>`:
> <parent_statement>
Strategy that produced this sub-goal (parent's PROPOSAL.md excerpt):
```<parent strategy proposal_md, ≤ 2000 chars>```

## Mathlib hints (from Manifest.md)
- ...

## FORBIDDEN_LEMMAS (from Manifest.md)
- ...

## Strategic notes (from Manifest.md)
<text>

## Previous attempts on THIS goal           ← K=5 most recent dead_attempts where target=goal
### Attempt N (<pid prefix>): <failure_reason>
```<failure_detail>```
Strategy summary (from PROPOSAL.md):
```<proposal_md, ≤ 2000 chars>```

## Past decompositions that failed Verify   ← strategies of this goal whose Verify fail (W4 #200)
### Strategy N (<pid prefix>): <failure_reason>
Decomposition (from strategies.proposal_md):
```<strategy.proposal_md>```
```

**`failure_reason` enum**（dead_attempts column）：

| reason | 來源 |
|--------|------|
| `forbidden_lemma` | patch 命中 Manifest.forbidden_lemmas |
| `lake_build_error` | lake stderr |
| `parse_proposal_fail` | Backward agent 結構錯（缺 PROPOSAL/patch/new_*） |
| `naming_violation` | Backward sub-goal slug 不符 `s<sid>_<parent>_` 格式（W5/C） |
| `agent_no_response` | claude CLI rc != 0 |
| `tactic_try_exhausted` | Phase 1 全 deterministic tactic 失敗 |
| `superseded` | run_verify 早期退出（goal 已 proved 或 strategy superseded）；**不寫 dead_attempt**（W6 noise filter） |

**Hadamard 對照**：`Dead/` 只 rename 檔、無 reason metadata、agent 看不出失敗原因。Asterism 結構化 reason + 完整 narrative 注入下次 worker，是 Asterism 唯一真實增量。

---

## 7. Dispatcher 主迴圈

```python
def run(workspace, *, once=False) -> int:
    pool_size  = int(os.environ.get('ASTERISM_POOL', '4'))
    budget_sec = int(os.environ.get('ASTERISM_BUDGET_SEC', '1800'))
    or_fanout  = int(os.environ.get('ASTERISM_OR_FANOUT', '3'))
    pool = ThreadPoolExecutor(max_workers=pool_size)
    futures: dict[Future, tuple[str, str, str, str]] = {}
    running: set[tuple[str, str]] = set()  # (target_id, kind)  F37

    while True:
        # Cascade 永遠主 loop sequential、不在 worker thread
        for fut in done(futures):
            cascade_one(...)
            running.discard((target_id, kind))

        if root_proved(): return 0

        bfs_refill(running)

        while len(futures) < pool_size:
            row = pop_queue()
            if row is None: break
            if (target_id, kind) in running: continue   # defensive
            running.add((target_id, kind))
            futures[pool.submit(_run_pipeline, ...)] = ...

        wait_one_or_timeout(futures, TICK_TIMEOUT=30)

        if elapsed > budget_sec:
            pool.shutdown(cancel_futures=True); return 1
```

**設計紀律**：
- Cascade 永遠主 loop sequential（避免 v1 race 災難）
- worker thread 只做：跑 pipeline、寫 staging、INSERT pipeline finished row
- F37 起 `running` 是 `(target_id, kind)` 二元組（passive cap=1、無需 pipeline_id 區分）
- BFS cap-aware：`in_flight(tid, kind) = ((tid,kind) in running) + queue_count`、cap=1 一律
- Daemon 死 → in-memory 全消失、pipelines 表只 finished、重啟見乾淨表面

---

## 8. Cascade rules

```python
def cascade_one(*, kind, target_id, target_kind, outcome):
    # === 入口 no-op（W6）===
    if target_kind == 'Strategy':
        s = SELECT s.status, g.status AS goal_status FROM strategies s
            JOIN goals g ON g.id = s.goal_id WHERE s.id = ?
        if s.status == 'superseded': return
        if s.goal_status == 'proved':
            if s.status == 'proposed':
                # late-arriving Verify on a goal won by sibling
                update_strategy_status(target_id, 'superseded')
            return
    elif target_kind == 'Goal':
        if get_goal_status(target_id) == 'proved': return

    # === Builder ===
    if kind == 'Builder':
        if outcome == 'proved':
            update_goal_status(target_id, 'proved')
        elif outcome in ('exhausted', 'failed'):
            n = increment_goal_attempts(target_id)
            if n >= SHELVE_THRESHOLD: update_goal_status(target_id, 'shelved')
        return

    # === Backward ===
    if kind == 'Backward':
        if outcome == 'success':
            update_goal_status(target_id, 'attempting')  # 還沒 proved、等 Verify
        else:
            n = increment_goal_attempts(target_id)
            if n >= SHELVE_THRESHOLD: update_goal_status(target_id, 'shelved')
        return

    # === Verify ===
    if kind == 'Verify':
        goal_id = SELECT goal_id FROM strategies WHERE id = target_id
        if outcome == 'proved':
            update_strategy_status(target_id, 'succeeded')
            update_goal_status(goal_id, 'proved')
            mark_other_strategies_superseded(goal_id, winner_id=target_id)  # OR
            return
        # failed
        update_strategy_status(target_id, 'dead')
        n = increment_goal_attempts(goal_id)
        if n >= SHELVE_THRESHOLD: update_goal_status(goal_id, 'shelved'); return
        # W4 #199: 若無 live strategy 剩、goal 回 'open' 才能再被 dispatch
        if not exists_proposed_strategy(goal_id):
            update_goal_status(goal_id, 'open')
```

```python
def bfs_refill(running):
    def in_flight(tid, kind):
        return (1 if (tid,kind) in running else 0) + queue_count(tid, kind)

    # Verify 派遣（cap=1 per strategy）
    for s in strategies_ready_for_verify():       # filters g.status != 'proved' (W6)
        if in_flight(s.id, 'Verify') == 0:
            enqueue('Verify', s.id, priority=10)

    # 對 open goals: orphan filter 跳過 dead/superseded ancestor
    # F37 — Builder 與 Backward 都 cap=1，一條 strategy 死掉才會經 cascade
    # 重新 reopen goal 進到下一輪 enqueue。
    for g in open_goals():                        # joins strategy_subgoals + strategies
        kind = next_worker_kind(g)                # difficulty>=4 → Backward;
                                                  # else attempts<BUILDER_THRESHOLD → Builder; else Backward
        if in_flight(g.id, kind) == 0:
            enqueue(kind, g.id, priority=5 if kind=='Builder' else 2)
```

**F37 — `_propagate_shelve` reopen 分支補增 attempts 計數**：sub-goal cascade-shelve 殺掉父 strategy 後，若父 goal 無 live strategy、attempts++ 並依 SHELVE_THRESHOLD 決定 'open'（再生新 strategy）或 'shelved'（自己也死掉、繼續上拋）。沒有這條 increment、passive 下父 goal 永不 shelve、Backward 會無限 retry。

`open_goals()` 的 orphan filter SQL（避免 supersede 後 dispatch 到 dead branch sub-goals）：

```sql
SELECT g.* FROM goals g
WHERE g.status = 'open'
  AND (g.origin = 'root' OR EXISTS (
      SELECT 1 FROM strategy_subgoals ss
      JOIN strategies s ON s.id = ss.strategy_id
      WHERE ss.subgoal_id = g.id AND s.status = 'proposed'
  ))
ORDER BY g.id
```

---

## 9. OR sequencing (F37 passive trigger)

**歷史**：v2.5 起初為 eager OR fanout（每 goal 同時派 N 條 Strategy 並行 race），動機是抗 Context 累積病態 + hedge 風險 + wall-clock 加速。F37 改成 passive：**每 goal 同一時間至多一條 active Strategy**；它死掉後才生下一條。

**動機**：eager 在強模型（Sonnet/Opus）下 token 浪費顯著（單一最快策略事後幾乎可預測唯一）、深層 fanout × depth 也加重多餘工作。passive 下總工 token 大致 = 真正成功的策略 + 失敗 retry 各一份、無並行多餘。

**改變的內容**：
- `OR_FANOUT_DEFAULT` 常數 + `ASTERISM_OR_FANOUT` env var 全砍
- `bfs_refill` 對 Builder/Backward 一律 cap=1
- `running` set 從 `(tid, kind, pid)` 簡化為 `(tid, kind)`
- `_propagate_shelve` reopen 分支補 `increment_goal_attempts`（防無限 retry）
- SHELVE_THRESHOLD 預設 7→8 (Sonnet) / 8→10 (Haiku)、給 passive 多探索預算
- agent.py 新增 `_section_dead_strategies`：Backward 重觸發時看見過往 dead strategies 的 sub-goal 列表、避免重提同樣分解

**保留的內容**（仍適用 passive）：
- 每條 Strategy 有獨立的「scratch lean module + namespaced sub-goals」、parent 的 lean_path 直到 Verify 勝出才被改
- sub-goal slug `s<sid>_` 前綴防 sequential strategies 之間檔案命名碰撞
- cascade 入口 no-op、`mark_other_strategies_superseded` 等防禦在 cascade timing race 下仍可能觸發

| 隔離維度 | 實作 |
|---------|------|
| 檔案命名 | sub-goal lean = `proofs/L_s<sid>_<parent>_sub_<N>.lean`、scratch = `proofs/_strategy_s<sid>.lean` |
| theorem 命名 | sub-goal `s<sid>_<parent>_sub_<N>`、scratch 內 `s<sid>_<parent>` |
| DB slug | sub-goal slug 含 `s<sid>_` 前綴、滿足 `goals.UNIQUE(problem, slug)` |
| 父 lean_path | Backward **不寫**、只在 Verify 勝出時 alias-import scratch |

**Trade-off**：
- 收益：token 浪費下降（強模型最有感）、tree shape 簡化、log 易讀
- 成本：first strategy 走錯方向時、wall-clock 比 eager 慢（要等全棵子樹 cascade-shelve 才轉向）；靠 SHELVE_THRESHOLD 拉高 + dead-strategies prompt hint 緩解

### 9.5 Deduper

**動機**：眼下主要場景是 ancestor / 跨深度的 sub-goal 重複（同 problem 內多條 strategy 的某層 sub-goal 與更上面的 ancestor 在 statement 上 def-equiv）。F37 passive 下、parallel sibling 重複已不存在；剩下的價值是跨 ancestor。

**設計核心**：alias-based 共享、零 schema 改動。

`Tooling/dedupe.py`：

```python
_normalize_statement(s)            # whitespace 折疊
_statements_equivalent(a, b)       # 單一 swap point（未來換 α-rename / Lean defeq）
find_canonical(conn, problem,
               statement) -> id | None
build_alias_content(...)
```

**Canonical 選擇規則**（deterministic）：
1. `status='proved'` 優先（alias 直通真實 proof）
2. reachable open/attempting（lineage 上每個 strategy 都 'proposed'/'succeeded'，由 recursive CTE `WITH RECURSIVE alive` 計算）
3. earliest id tie-break

**跳過**：`status` IN `('superseded','dead','shelved')` 或 lineage 含 dead 鏈（會留 stale alias）。

**整合進 `run_backward`**（forbidden grep 之後、檔案放置之前）：

```python
canonical_for: list[int | None] = [
    dedupe.find_canonical(conn, problem, _extract_statement(src))
    for slug, src in sub_meta
]

# 檔案放置：
for ..., canonical_id in zip(...):
    if canonical_id:
        canonical = db.get_goal(conn, canonical_id)
        dest.write_text(dedupe.build_alias_content(...))   # alias .lean
    else:
        shutil.copy2(src, dest)                            # 原生 sub-goal

# DB INSERT：dedupe-hits 不 insert 新 goal、直接 link_subgoal 到 canonical
```

**Alias 檔內容**：

```lean
import Mathlib
import Problems.<p>.Defs                      -- 若 Defs 存在
import Problems.<p>.proofs.L_<canonical_slug>

namespace Problems.<p>
theorem <new_slug> : <statement> := <canonical_slug>
end Problems.<p>
```

Lake-build 對 canonical 任何狀態都 OK（sorry stub 也 type-check）；canonical 真 proved 時 alias transitively 繼承 proof。

**用 `strategy_subgoals` 多對多支援共享**：dedupe-hit 時、新 strategy 的 `strategy_subgoals` 直接 link 到 canonical 的 goal_id；DAG 變 graph、不破壞既有 invariants（cascade no-op、orphan filter、reconcile、prune 全不受影響）。

**Fail-open**：dedupe 內部錯（statement 解析失敗等）→ `find_canonical` 回 None、Backward 走 non-dedupe 路徑、永不阻斷主流程。

**目前比對方法限制**：whitespace-only 命中率約 30-50%（catches identical agent output）。漏：α-renamed binders、reordered hypotheses、`Nat.add` vs `+` defeq。升級為 α-rename 或 Lean defeq 只需動 `_statements_equivalent`、不動 call site。

**對比 v3 archive 設計**（簡化幅度）：

| 項目 | v3 archive | v2.5 |
|------|-----------|------|
| 比對引擎 | Lean exec `tools/dedupe.lean`（subprocess + isDefEq + iff_lite） | 純 Python whitespace-norm |
| 配套 | `search_cache` 表 + mutation invalidation + 30s timeout | 0 |
| 模式 | strict + iff_lite | 1（pluggable） |
| 命中後動作 | mark dup + cache | alias .lean + link 到 canonical |
| LOC | ~300 估計 | ~70 + 25 整合 |

簡化由來：Asterism v2 的 AND/OR graph schema 把「兩 strategies 共用同一 sub-goal」變 schema-native（`strategy_subgoals` 多對多）、不需要 v3 那套 cache + invalidation 基礎建設。

---

## 10. CLI

```
asterism init <problem>
  ├─ 讀 Problems/<p>/Manifest.md frontmatter + sections
  ├─ INSERT problems row
  ├─ INSERT goals row (origin='root', status='open', depth=0, difficulty=mfst.difficulty)
  ├─ 寫 Problems/<p>/Root.lean stub:
  │   import Mathlib
  │   import Problems.<p>.Defs        ← 自動加（若 Defs.lean 存在、W6）
  │   namespace Problems.<p>
  │   theorem main : <statement> := by sorry
  │   end Problems.<p>
  └─ idempotent：再次 init 同 problem 不覆蓋

asterism run [--once]
  └─ 啟動 dispatcher。設定一律走 Tooling/config.get 的 4 步解析鏈：
       1. env var (一次性 override / CI)
       2. Asterism.yaml at workspace root (per-project default)
       3. legacy env var (向後相容、舊 setup 不需要改)
       4. built-in default

     Asterism.yaml schema (所有欄位 optional)：
       dispatch:
         pool:               4       (env: ASTERISM_POOL)
         budget_sec:         1800    (env: ASTERISM_BUDGET_SEC)
         builder_threshold:  3       (env: ASTERISM_BUILDER_THRESHOLD)
         shelve_threshold:   8       (env: ASTERISM_SHELVE_THRESHOLD)
       builder:
         provider:  claude   (env: ASTERISM_BUILDER_PROVIDER →
                                   ASTERISM_LLM_PROVIDER)
         model:     <provider-default>
                    (env: ASTERISM_BUILDER_MODEL →
                          provider-specific legacy:
                            claude  → ASTERISM_AGENT_MODEL
                            gemini  → ASTERISM_GEMINI_MODEL
                            openai  → ASTERISM_LLM_MODEL)
       backward:
         provider:  claude   (same chain as builder.provider)
         model:     <provider-default>
                    (same chain as builder.model)

     Built-in defaults assume Sonnet/Opus tier. Weak-tier models
     (haiku / flash / mini) want roughly (5, 10) for the threshold
     pair — set explicitly in Asterism.yaml; the framework no longer
     auto-detects from model-name substrings (was retired with this
     consolidation: substring matching couldn't survive vendor naming
     drift, see "Recent commits" in STATUS.md).

     Provider-specific knobs not in Asterism.yaml (env-only):
       ASTERISM_CLAUDE_TOOLS    claude --tools value (rare override)
       ASTERISM_GEMINI_MODEL    gemini provider-wide model fallback
       ASTERISM_LLM_MODEL       openai provider-wide model fallback
       ASTERISM_LLM_BASE_URL    openai HTTP base URL
```

status / stop 命令暫不寫，直接 sqlite 查 / Ctrl-C 終止。

---

## 11. 不做（v1 教訓 + v2.5 取捨）

| 不做 | 原因 |
|---|---|
| Solver 獨立 pipeline kind | Builder phase 1+2 已涵蓋 |
| Path A/B 分裂 | v1 死碼來源 |
| `commit_state` pending/live 兩段式 | backup-restore + os.replace 夠用 |
| `answer_data` typed JSON verdict | status='proved' + lean_path 已表達；conjecture/construction 來再說 |
| Stage 形式抽象 | 程式碼 inline、需要時 refactor |
| Active cancellation propagation 表 | cascade 入口 no-op 已被動接住 OR 落敗者 |
| Refuter / Counterexample / Forward / Generalizer / ConstructionSearch | schema 留洞、實作 deferred |
| Strategist round-robin demux | 等 dispatcher 穩定再加 |
| evidence / twin_of / trust_set 欄位 | conjecture/refuter/library 用、deferred |
| events 表 audit log | dead_attempts.artifacts JSON + 主 loop print 夠 |
| continuous tasks pool | 沒 ConstructionSearch 不需要 |
| Library 跨 problem promotion | 等多 problem 才有意義 |
| separate META/HINTS/STATUS/OPEN/SHELVED/LOG/POSTMORTEM | 整合進 Manifest + DB |
| asterism status / stop CLI | sqlite + Ctrl-C 夠 |
| 主動清 OR 落敗 strategies 檔 | 留 forensics、`asterism prune` 後續 |

---

## 12. 已驗證的 long-term cleanup design

每條都在 wilson + compactness + cantor smoke 跑過、行為符合預期：

1. **finished-only pipelines table**：daemon 死 → 重啟見乾淨表面、不需要 zombie sweep（W1）
2. **ephemeral `.attempts/<pid>/`**：pipeline 結束 unconditional rmtree、藉 `WorkArea` context manager（W2）
3. **`dead_attempts.artifacts` JSON**：所有 agent 輸出檔保留 in-DB、`.attempts/` rmtree 後仍可 forensics（W1）
4. **WAL mode**：4-12 個 worker 並發寫不互鎖（W2）
5. **`os.replace` atomic rename**：Verify 多 parent 改寫不 race（W5/C）
6. **W4 stuck-attempting 修正**：goal 在 Verify 失敗 + 無剩餘 strategy 時自動回 'open'
7. **W4 cross-strategy dead_attempts**：goal 的下次 Backward 看得到上次 strategy 的 Verify 失敗（cross-pipeline learning）
8. **W6 thrashing fix**：`strategies_ready_for_verify` 過濾 proved-goal、cascade 入口轉 superseded、`superseded` 不寫 dead_attempt 噪音
9. **W7 recursive orphan filter**：`open_goals` 用 recursive CTE 走完整 ancestor 鏈、catch depth-2+ orphan
10. **W8 startup recovery sweep**：daemon 啟動時清 queue + 殺 half-baked strategies + 重開 stuck-attempting goals、與 success-exit 的 reconcile+prune 對稱（startup self-healing + exit self-healing）
11. **E1-E7 reconcile + prune**：成功退出時自動 reconcile（修 OR Verify race 的 file/DB drift）+ prune（GC OR 落敗檔）；CLI fallback 給 partial state
12. **Deduper alias 共享**：OR 並行下 sub-goal overlap 透過 `strategy_subgoals` 多對多 + alias .lean 檔零 schema 共享（§9.5）

---

## 13. 後續（按優先序、每條都先驗證需要再做）

| # | 項目 | 動機 / 觸發條件 |
|---|------|----------------|
| 1 | **Web dashboard / UI** | DAG 視覺化、dead_attempts artifacts 點擊展開；compactness 級多層深 已超 CLI 可讀 |
| 2 | **Dedupe predicate 升級**（α-rename 或 Lean defeq） | 量到 whitespace-norm 命中率 < 30% 時觸發；單 swap point 換 `_statements_equivalent` |
| 3 | **第四題 smoke**（如 sylvester_gallai） | 驗證對更深 / 不同題型穩定性 |
| 4 | **多 problem 並行**（同一 daemon 多 problem） | 視 Library 跨題效益決定 |
| 5 | **Forward** | 從 proved Node 推 lemma；可與 Deduper 整合（找已存在的等價公式） |
| 6 | **Promotion Judge** | shelved goal 重審、自動跑 |
| 7 | **Strategist** | cross-pipeline meta-decision、用 DB 累積訊號 |
| 8 | **answer_data typed verdict** | conjecture / construction kind 啟用時必須 |
| 9 | **Refuter / conjecture kind** | 等 answer_data 落地 |
| 10 | **commit_state 兩段式** | OR_FANOUT 升到 ≥ 8 + 多 problem 並發時才有意義 |
| 11 | **Construction kind + ConstructionSearch** | continuous task framework |
| 12 | **Library 跨 problem promotion** | 等 Forward + 多題場景；Deduper 加 cross-problem scope |
| 13 | **events 表 + audit log** | 當前 dead_attempts.artifacts + print 夠、Strategist 啟用時可能升級 |

每條都需要先有 smoke pass 為基準。**沒過不加新東西**。

---

## 14. 不變 invariants（contributor checklist）

- Cascade 永遠主 loop sequential、不在 worker thread
- worker thread 只 INSERT finished pipeline row、不更新 goal/strategy 狀態
- pipelines 表只存 finished rows（無 'running' state）
- `.attempts/<pid>/` + `.attempts/_backup_<pid>/` 透過 `WorkArea` 統一管理、`__exit__` unconditional rmtree
- worker_kind 與 target_kind 一一對應：Builder/Backward → Goal、Verify → Strategy
- Strategy 的 `scratch_path` 一旦 UPDATE 後 immutable
- `goals.lean_path` UNIQUE、`strategies.lean_path` 不 UNIQUE（多 strategies 共享 parent target）
- Strategy 的 sub-goal slug **必須**含 `s<sid>_` 前綴（W5/C 命名約定）
- `compile_context` 的 prior failures 注入：goal 自身的 dead_attempts (K=5) + 同 goal 的 dead strategies' Verify 失敗
- WAL mode 開、所有 conn 經 `db.connect()`
- 修 schema → bump 版本、寫 migration（不能單純改 CHECK constraint）
- 加新的 `failure_reason` enum value → 記得更新 §6 表

---

## 15. Decisions（關鍵設計決策時間軸）

| 決策 | 結果 |
|------|------|
| Manifest.md hints | markdown only、`init` 時 parse 進 Context.md（不複製進 DB） |
| Manifest.md 格式 | 寬 best-effort parse、缺欄位給 default + print warning |
| Tooling/ 重寫 | 不借 Hadamard 代碼；純 Python、模組界線清楚 |
| Shelve 判斷 | cascade rule 內、不在 `next_worker_kind`（純函數） |
| Pool size | 預設 4、`ASTERISM_POOL=N` env 覆蓋 |
| OR sequencing | F37 起 passive (cap=1)；env var 已移除；同 goal 多策略走序列觸發 |
| Daemon budget | 預設 1800s、`ASTERISM_BUDGET_SEC=N` env 覆蓋 |
| Worker 單次 timeout | 10 min hardcoded（compactness 級才會超、那是 Backward 拆解的 signal） |
| `proofs/` 結構 | flat（success exit 自動 reconcile + prune 留 winner chain；CLI fallback 給 partial state） |
| Sub-goal 命名 | agent 端負責（Context.md 注入 sid_token、agent 寫 `s<sid>_` 前綴）；不做框架 post-substitute |
| cli init 自動 import | 若 `Problems/<p>/Defs.lean` 存在、自動加進 Root.lean（W6） |
| 'superseded' dead_attempt | 跳過寫入（OR race noise、不是 learnable failure） |
| Dedupe predicate | 起步 whitespace-norm；`_statements_equivalent` 是單一 swap point、未來升 α-rename / Lean defeq |
| Dedupe canonical 優先序 | `proved` > reachable open/attempting；orphan/superseded/shelved 跳過；earliest id tie-break |
| Dedupe schema | 0 改動；用 `strategy_subgoals` 多對多 + alias `.lean` 共享、不加 `equiv_to` 欄 |
| Dedupe scope | 同 problem 內；cross-problem 等 Library 階段 |
