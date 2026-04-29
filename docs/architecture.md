# Asterism — 架構文件 v2.5

寫於 2026-04-30。前次設計診斷見 `D:/Hadamard/docs/asterism_postmortem.md` 與 `asterism_factor_analysis.md`，前次完整 v3 架構（一次設計 8 pipeline kind）存於 `D:/Hadamard/docs/asterism_archive/`。

本檔反映 commit `b69a4ba` 後的實作現況。Milestone 1 已通過（wilson + compactness 兩題 from-scratch proved）；核心架構穩定、後續按 §13 排序加 feature。

---

## 0. Status

| 項目 | 狀態 |
|------|------|
| Wilson (Freek 100 #51) | proved end-to-end、commit 6b0cf3b、~15 min |
| Compactness (propositional, custom Defs) | proved end-to-end、commit 46c8941、~60 min、~2.5x faster than Hadamard 2.5h |
| Pipeline kinds | Builder + Backward + **Verify**（3 種、每 kind 有固定 target_kind） |
| OR parallelism | 開、`ASTERISM_OR_FANOUT=3` 預設 |
| Unit tests | 53 passing |
| Tooling LOC | ~1490 lines Python |
| Axioms whitelist | `[propext, Classical.choice, Quot.sound]`（兩題均通過） |

---

## 1. AND/OR graph

二分圖、兩種節點交替：

```
Goal      = OR    : 任一 Strategy 成功 → Goal 成功
Strategy  = AND   : 所有 sub-Goal 成功 → Strategy 成功
```

整個推理樹由 `goals` × `strategies` × `strategy_subgoals` 三表表達。

葉子 Goal 不靠 Strategy 證明、靠 Builder 直接 closure（tactic_try → tactic_llm）。Strategy 必有 ≥ 1 個 sub-goal、否則無法被 `strategies_ready_for_verify` 撈到。

OR 並行（§9）：同 Goal 可同時掛 N 條 Strategy；首個通過 Verify 的勝出、其餘標 `superseded`。

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
    running: set[tuple[str, str, str]] = set()  # (target_id, kind, pipeline_id)

    while True:
        # Cascade 永遠主 loop sequential、不在 worker thread
        for fut in done(futures):
            cascade_one(...)
            running.discard((target_id, kind, pipeline_id))

        if root_proved(): return 0

        bfs_refill(running, or_fanout=or_fanout)

        while len(futures) < pool_size:
            row = pop_queue()
            if row is None: break
            # 不再做 (target_id, kind) dedup — bfs_refill 已 cap-aware
            running.add((target_id, kind, pipeline_id))
            futures[pool.submit(_run_pipeline, ...)] = ...

        wait_one_or_timeout(futures, TICK_TIMEOUT=30)

        if elapsed > budget_sec:
            pool.shutdown(cancel_futures=True); return 1
```

**設計紀律**：
- Cascade 永遠主 loop sequential（避免 v1 race 災難）
- worker thread 只做：跑 pipeline、寫 staging、INSERT pipeline finished row
- `running` 含 pipeline_id 作為 key 第三元素 → 多個 Backward 同 (target_id, kind) 不互相覆蓋
- BFS dedup 改成 cap-aware count：`in_flight = len(running matches) + queue_count`、`slot = cap - in_flight`、enqueue 數 = max(0, slot)
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
def bfs_refill(running, *, or_fanout):
    def in_flight(tid, kind):
        return sum(1 for (t,k,_) in running if t==tid and k==kind) + queue_count(tid, kind)

    # Verify 派遣（cap=1 per strategy）
    for s in strategies_ready_for_verify():       # filters g.status != 'proved' (W6)
        if in_flight(s.id, 'Verify') == 0:
            enqueue('Verify', s.id, priority=10)

    # 對 open goals: orphan filter 跳過 dead/superseded ancestor
    for g in open_goals():                        # joins strategy_subgoals + strategies
        kind = next_worker_kind(g)                # difficulty>=4 → Backward;
                                                  # else attempts<=2 → Builder; else Backward
        cap = or_fanout if kind == 'Backward' else 1
        slots = cap - in_flight(g.id, kind)
        for _ in range(max(0, slots)):
            enqueue(kind, g.id, priority=5 if kind=='Builder' else 2)
```

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

## 9. OR parallelism

**動機**：wilson smoke 第 2 輪實證 Context.md 注入 prior_failures 在重試上有過深 reasoning 病態（agent 越來越遠離 simple solution、最後 timeout）。OR 下、N 條 Strategy 用 spawn 時 snapshot 的 Context、不會遞迴病態化、且能 hedge 風險。

**核心設計**：每條 Strategy 有獨立的「scratch lean module + namespaced sub-goals」、parent 的 lean_path 直到 Verify 勝出才被改。

| 隔離維度 | 實作 |
|---------|------|
| 檔案命名 | sub-goal lean = `proofs/L_s<sid>_<parent>_sub_<N>.lean`、scratch = `proofs/_strategy_s<sid>.lean` |
| theorem 命名 | sub-goal `s<sid>_<parent>_sub_<N>`、scratch 內 `s<sid>_<parent>` |
| DB slug | sub-goal slug 含 `s<sid>_` 前綴、滿足 `goals.UNIQUE(problem, slug)` |
| 父 lean_path | Backward **不寫**、只在 Verify 勝出時 alias-import scratch |

**勝出與清理**：
- Verify outcome='proved' → strategy='succeeded'、goal='proved'、`mark_other_strategies_superseded` 把同 goal 其他 'proposed' 全標 'superseded'
- 落敗 strategies 的 sub-goals 變 orphan、`open_goals` SQL filter 自動排除
- 落敗 strategies 的檔不主動清（forensics 用、`asterism prune` deferred）

**Race window 與防禦**：
- 多個 Verify 同時改 parent.lean_path → 用 `os.replace` 原子 rename、last-write-wins、cascade 入口 no-op 接住第二波
- `strategies_ready_for_verify` 加 `g.status != 'proved'` 過濾、防 W6 無窮 verify-thrashing 迴圈

**Trade-off**：
- 收益：抗 Context 累積病態、抗 timeout、整體 wall-clock 加速（compactness 約 2.5x）
- 成本：Token 多 N 倍（每 OR Backward 都呼叫 LLM）；落敗 strategies 留 orphan files；DAG 在深層題目展開為原 fanout × OR_FANOUT

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
  └─ 啟動 dispatcher。env 可控：
       ASTERISM_POOL          worker pool size (default 4)
       ASTERISM_OR_FANOUT     per-goal Backward concurrency (default 3)
       ASTERISM_BUDGET_SEC    daemon wall-clock budget (default 1800)
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

每條都在 wilson + compactness smoke 跑過、行為符合預期：

1. **finished-only pipelines table**：daemon 死 → 重啟見乾淨表面、不需要 zombie sweep（W1）
2. **ephemeral `.attempts/<pid>/`**：pipeline 結束 unconditional rmtree、藉 `WorkArea` context manager（W2）
3. **`dead_attempts.artifacts` JSON**：所有 agent 輸出檔保留 in-DB、`.attempts/` rmtree 後仍可 forensics（W1）
4. **WAL mode**：4-12 個 worker 並發寫不互鎖（W2）
5. **`os.replace` atomic rename**：Verify 多 parent 改寫不 race（W5/C）
6. **W4 stuck-attempting 修正**：goal 在 Verify 失敗 + 無剩餘 strategy 時自動回 'open'
7. **W4 cross-strategy dead_attempts**：goal 的下次 Backward 看得到上次 strategy 的 Verify 失敗（cross-pipeline learning）
8. **W6 thrashing fix**：`strategies_ready_for_verify` 過濾 proved-goal、cascade 入口轉 superseded、`superseded` 不寫 dead_attempt 噪音

---

## 13. 後續（按優先序、每條都先驗證需要再做）

| # | 項目 | 動機 / 觸發條件 |
|---|------|----------------|
| 1 | **`asterism prune`** | OR 後 proofs/ 檔暴增（compactness 98 個檔、winner chain 占 1/4）；GC 落敗 strategies 的 lean files |
| 2 | **Web dashboard / UI** | DAG 視覺化、dead_attempts artifacts 點擊展開；compactness 級多層深 + OR fanout 已超 CLI 可讀 |
| 3 | **第三題 smoke**（如 sylvester_gallai / cantor） | 驗證跨 problem parallelism + 對更多題型穩定性 |
| 4 | **多 problem 平行**（同一 daemon 多 problem） | 視 Library 跨題效益決定 |
| 5 | **Forward + Deduper** | 從 proved Node 推 lemma，跨 strategy 共用 sub-goal、減少 OR 浪費 |
| 6 | **Promotion Judge** | shelved goal 重審、自動跑 |
| 7 | **Strategist** | cross-pipeline meta-decision、用 DB 累積訊號 |
| 8 | **answer_data typed verdict** | conjecture / construction kind 啟用時必須 |
| 9 | **Refuter / conjecture kind** | 等 answer_data 落地 |
| 10 | **commit_state 兩段式** | OR_FANOUT 升到 ≥ 8 + 多 problem 並發時才有意義 |
| 11 | **Construction kind + ConstructionSearch** | continuous task framework |
| 12 | **Library 跨 problem promotion** | 等 Forward + 多題場景 |
| 13 | **events 表 + audit log** | 當前 dead_attempts.artifacts + print 夠、Strategist 啟用時可能升級 |

每條都需要先有兩題 smoke pass 為基準。**沒過不加新東西**。

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
| OR fanout | 預設 3、`ASTERISM_OR_FANOUT=N` env 覆蓋；Builder/Verify cap=1 不變 |
| Daemon budget | 預設 1800s、`ASTERISM_BUDGET_SEC=N` env 覆蓋 |
| Worker 單次 timeout | 10 min hardcoded（compactness 級才會超、那是 Backward 拆解的 signal） |
| `proofs/` 結構 | flat（含 winner chain + OR orphan files；`asterism prune` 後續） |
| Sub-goal 命名 | agent 端負責（Context.md 注入 sid_token、agent 寫 `s<sid>_` 前綴）；不做框架 post-substitute |
| cli init 自動 import | 若 `Problems/<p>/Defs.lean` 存在、自動加進 Root.lean（W6） |
| 'superseded' dead_attempt | 跳過寫入（OR race noise、不是 learnable failure） |
