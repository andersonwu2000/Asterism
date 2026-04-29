# Asterism — 最小架構文件 v2

寫於 2026-04-29，第二次嘗試。前次失敗診斷見 `D:/Hadamard/docs/asterism_postmortem.md` 與 `asterism_factor_analysis.md`，前次完整 v3 架構（一次設計 8 pipeline kind）存於 `D:/Hadamard/docs/asterism_archive/`。

本檔是 **v3 的最小可執行子集** + Asterism 對 Hadamard 唯一真實改進（**A7 失敗 metadata**）。其他超越 Hadamard 的特性（commit_state 兩段式、stage 形式抽象、cancellation propagation、answer_data typed verdict）都 deferred — 等 Milestone 1 通過再考慮。

---

## 1. AND/OR graph

二分圖、兩種節點交替：

```
Goal      = OR    : 任一 Strategy 成功 → Goal 成功
Strategy  = AND   : 所有 sub-Goal 成功 → Strategy 成功
```

葉子 Strategy（`strategy_subgoals` 內無 row）= 直接證明嘗試。整個推理樹由 `goals` × `strategies` × `strategy_subgoals` 三表表達。

---

## 2. 目錄結構

```
Asterism/
├── asterism.db                 # ★ Single source of truth
├── Tooling/                    # Python + bash worker / dispatcher
├── docs/architecture.md        # 本檔
└── Problems/<problem>/
    ├── Manifest.md             # 唯一人手檔
    ├── Defs.lean               # problem-specific definitions
    ├── Root.lean               # 自動生成的 root goal lean
    └── proofs/                 # 已 commit 的 .lean
        └── L<id>_<slug>.lean
```

對照 Hadamard 砍掉：META / HINTS / STATUS / OPEN / SHELVED / LOG / POSTMORTEM / TWIN_SIGNALS / Dead/ — 7 個 markdown + 1 子樹合進 DB + Manifest.md。

**`proofs/` 只放 commit 成功的檔**：dead pipeline 整段（PROPOSAL.md narrative + lake stderr）保留在 `dead_attempts.proposal_md`（DB 字串），不留檔、避免 v1 死檔污染 lake build。

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
- ZMod.val_neg_one (Data/ZMod/Basic.lean:540)
- Nat.mod_eq_of_lt
- Nat.Prime.two_le

## Strategic notes
此題 reformulated 過、ZMod 形式直接用會被擋；要走 Mathlib bridge。
```

YAML frontmatter 是結構化必填；body 自由 markdown，由 `init` 解析 statement + difficulty 進 DB、hints + notes 在 worker spawn 時注入 Context.md。

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
    -- forward / generalizer / refuter / conjecture / construction are
    -- actually implemented (§12).
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

CREATE TABLE strategies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     INTEGER NOT NULL REFERENCES goals(id),
    lean_path   TEXT    NOT NULL UNIQUE,
    status      TEXT    NOT NULL CHECK(status IN ('proposed','succeeded','dead')),
    proposal_md TEXT    NOT NULL DEFAULT '',  -- Backward's PROPOSAL.md verbatim
    created_by  TEXT    NOT NULL REFERENCES pipelines(id),
    created_at  TEXT NOT NULL
);

CREATE TABLE strategy_subgoals (
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    subgoal_id  INTEGER NOT NULL REFERENCES goals(id),
    position    INTEGER NOT NULL,
    PRIMARY KEY (strategy_id, subgoal_id)
);

CREATE TABLE pipelines (
    id          TEXT PRIMARY KEY,                 -- UUID
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK(target_kind IN ('Goal','Strategy')),
    -- only finished rows stored; no 'running' state in DB
    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    outcome     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE dead_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id       INTEGER NOT NULL,
    target_kind     TEXT NOT NULL,
    pipeline_id     TEXT NOT NULL REFERENCES pipelines(id),
    failure_reason  TEXT NOT NULL,                -- enum, see §6
    failure_detail  TEXT,                         -- lake stderr / forbidden name
    proposal_md     TEXT,                         -- 整段 PROPOSAL.md 字面文字
    ts              TEXT NOT NULL
);

CREATE TABLE queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    -- worker_kind determines target_kind: Builder/Backward target Goal,
    -- Verify targets Strategy. No separate target_kind column needed.
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
```

**對 v3 schema 砍掉**：`commit_state`（用 backup-restore）、`answer_data` JSON（只看 status 夠）、`evidence` / `twin_of` / `trust_set`（conjecture/refuter/library 用、deferred）、`continuous_tasks` / `events` / `search_cache` / `forward_targets` / `strategist_decisions` 表（全 deferred）。

**Schema 留洞策略**：`goals.kind`/`origin` 只接受目前實作中的值；新增 origin（forward / generalizer / refuter）時做 migration 加 enum、不預先放未檢驗的字串。

**Atomicity 改用 Hadamard backup-restore**：integrator 跑完 lake build 前先 `cp -r proofs/ /tmp/backup/`，build fail 或 forbidden_lemma 命中就 mv backup 回 proofs/。沒 commit_state 兩段式。

---

## 5. Pipeline kinds（初期 2 種）

### 5.1 Builder

**輸入**：goal_id 或 strategy_id

**Phase 1 — `tactic_try`（無 agent、純 script）**：
跑 `[rfl, simp, decide, trivial, omega, linarith, nlinarith, norm_num, simp_all, aesop]` 10 條、第一條 lake-build 過就結束。Hadamard 證實對 d=1 sub-goal 命中率高、省 LLM call。

**Phase 2 — `tactic_llm`（spawn agent）**：
```
1. 從 dead_attempts 取最近 K=5 筆同 target → 寫 Context.md（§6）
2. spawn claude --agent builder --add-dir Problems/<p>/ --add-dir ATTEMPTS_DIR
3. agent 寫 ATTEMPTS_DIR/PROPOSAL.md + patch.lean
4. forbidden_lemmas grep on patch.lean
   if hit → INSERT dead_attempt(reason='forbidden_lemma'); pipeline=failed
5. lake env lean patch.lean
   if pass → mv staging → goal.lean_path; goal.status='proved'; pipeline=succeeded
   if fail → INSERT dead_attempt(reason='lake_build_error', detail=stderr, proposal_md=保留)
```

**Outcome**：`proved` / `exhausted`（phase 1 全敗或 phase 2 retry 用盡）/ `failed`（forbidden / agent 無回應）

### 5.2 Backward

**輸入**：goal_id

```
1. Context.md 編譯（同 Builder）
2. spawn claude --agent backward
3. agent 寫:
   - PROPOSAL.md (narrative)
   - patch_<goal_slug>.lean (parent goal lean，body 改成組合 tactic 引用 sub-goal)
   - new_<sub_slug>.lean × N (sub-goal placeholder := by sorry)
4. forbidden_lemmas grep on all output files
   if hit → INSERT dead_attempt(reason='forbidden_lemma'); pipeline=failed
5. integrator (backup-restore atomicity):
   a. backup proofs/
   b. mv staging files → proofs/
   c. lake build target modules
   d. if all pass:
        INSERT N 個 sub-goal goals row (origin='backward', status='open')
        INSERT 1 strategy + N 個 strategy_subgoals
        rm backup
        pipeline=succeeded
      else:
        mv backup → proofs/  (回退)
        INSERT dead_attempt
        pipeline=failed
6. goal.status 不變（仍 attempting，等所有 sub-goal proved + Builder 驗證 strategy lake build）
```

**Outcome**：`success` / `exhausted`（agent 回 unproductive）/ `failed`

---

## 6. Context.md（Asterism 對 Hadamard 唯一真實改進）

每次 worker spawn 前、dispatcher 從 DB 編譯一份 Context.md 寫進 ATTEMPTS_DIR：

```markdown
# Context for goal L0023_wilson_main_sub_1

## Goal statement
∀ p : ℕ, p.Prime → p ∣ Nat.factorial (p - 1) + 1

## Parent (if backward sub-goal)
L0001 wilson_main: ∀ p, p.Prime → (p-1)! % p = p - 1

## Sibling sub-goals (parent's strategy, status snapshot)
- L0024 wilson_main_sub_2: ∀ p n, p.Prime → p ∣ n+1 → n%p = p-1 (status: proved)

## Mathlib hints (from Manifest.md)
- ZMod.val_natCast (Data/ZMod/Basic.lean:89)
- ...

## FORBIDDEN_LEMMAS (from Manifest.md)
- ZMod.wilsons_lemma
- Nat.Prime.wilsons_lemma

## Previous attempts on THIS goal (from dead_attempts)

### Attempt 1 (Builder.tactic_try): tactic_try_exhausted
None of [rfl, simp, decide, ...] closed it.

### Attempt 2 (Builder.tactic_llm, w0123): forbidden_lemma
Detected: ZMod.wilsons_lemma in patch line 7
Strategy summary (from PROPOSAL.md):
"Use ZMod.wilsons_lemma to convert to ZMod form, then bridge via ZMod.val_natCast."
DO NOT use ZMod.wilsons_lemma. Find an alternative path.

### Attempt 3 ...
```

**`failure_reason` enum**（dead_attempts column）：

```
forbidden_lemma          patch 撞 Manifest.forbidden_lemmas
lake_build_error         lake 報錯
parse_proposal_fail      backward agent 結構錯
agent_no_response        claude CLI 無 output
agent_timeout            claude CLI 超時
tactic_try_exhausted     Phase 1 全 deterministic tactic 失敗
strategy_combination_failed   sub-goal 全 proved 但組合 lake-build 失敗
```

**這是 Hadamard 在 deferred.md A7 公認沒做的東西**：Hadamard `Dead/` 只 rename 檔、無 reason metadata。Asterism 結構化 reason + 完整 narrative 注入下次 worker，是 Asterism 唯一真實增量。

---

## 7. Dispatcher 主迴圈

```python
def main_loop():
    pool = ThreadPoolExecutor(max_workers=4)
    futures = {}
    while True:
        # Cascade（純 SQL、< 100ms、單 thread）
        for fut in done_futures(futures):
            cascade_one(futures.pop(fut))
        if root_proved():
            break

        # BFS 結構填充 queue
        bfs_refill_queue()

        # 派工
        while pool.has_slot() and queue_not_empty():
            task = pop_queue()
            if not is_already_dispatched(task):
                pipeline_id = create_pipeline_row(task)
                fut = pool.submit(run_pipeline, task, pipeline_id)
                futures[fut] = pipeline_id

        # 等任一 pipeline 完成或 30s tick
        wait_one_or_timeout(futures, 30)
```

**設計紀律：**
- Cascade 永遠主 loop sequential、不在 worker thread
- worker thread 只做：跑 pipeline、寫 staging + DB pipeline.status
- dedup 單一入口：`is_already_dispatched(target, kind)` 看 in-memory `_running` ∪ DB `pipelines.status='running'`，無 mode、無 sidecar

對 Hadamard `loop.sh` 的真正改進：Hadamard 是 batch + async sweep（B2 layer 1 done）、iter 邊界仍存在；Asterism 把 batch 邊界拿掉、cascade 在主 loop 連續跑。慢 worker 不阻塞快 worker 的 cascade。對 Asterism v1 的避坑：v1 把 cascade 也丟進 thread pool → race 災難；v2 cascade **永遠主 loop sequential**。

---

## 8. Cascade rules

```python
def cascade_one(pipeline_id):
    p = read_pipeline(pipeline_id)

    if p.kind == 'Builder' and p.outcome == 'proved':
        update_strategy_succeeded(p.target_id)        # if target_kind=Strategy
        update_goal_proved(p.goal_id)
        return

    if p.kind == 'Builder' and p.outcome in ('exhausted','failed'):
        if p.target_kind == 'Strategy':
            update_strategy_dead(p.target_id)
        increment_goal_attempts(p.goal_id)
        return

    if p.kind == 'Backward' and p.outcome == 'success':
        update_goal_attempting(p.target_id)
        return

    if p.kind == 'Backward' and p.outcome in ('exhausted','failed'):
        increment_goal_attempts(p.target_id)
        if goal_attempts(p.target_id) >= 7:
            update_goal_shelved(p.target_id)
        return

def bfs_refill_queue():
    # Strategy 全 sub-goal proved → enqueue Builder
    for s in strategies WHERE status='proposed'
                          AND ALL sub-goals' status='proved'
                          AND not is_already_dispatched(s.id, 'Builder'):
        enqueue('Builder', s.id, target_kind='Strategy')
    # Open goal → enqueue worker_kind 對應 phase
    for g in goals WHERE status='open':
        if not is_already_dispatched(g.id, _):
            enqueue(next_worker_kind(g), g.id, target_kind='Goal')

def next_worker_kind(goal):
    """純函數：input = goal、output = pipeline kind。不檢查 termination。
    BFS 只取 status='open' 的 goal、shelved goal 由 cascade 處理。"""
    if goal.difficulty >= 4:
        return 'Backward'
    if goal.attempts == 0:
        return 'Builder'   # phase 1
    if goal.attempts <= 2:
        return 'Builder'   # phase 2
    return 'Backward'
```

**Shelve 判斷在 cascade、不在 `next_worker_kind`**：cascade 是 state transition 的單一權威，所有 status flip（proved / dead / shelved）寫在同一處：
```python
def cascade_one(p):
    if p.outcome in ('exhausted','failed'):
        increment_goal_attempts(goal_id)
        if get_goal_attempts(goal_id) >= 7:
            update_goal_shelved(goal_id)
```

→ `next_worker_kind` 是純函數、好測；dispatcher 不處理 None / 不知道 policy。將來新增 shelve 條件（D_max depth、blocked_pipelines）都在 cascade 加一行 if。

---

## 9. CLI

```
asterism init <problem>
  ├─ 讀 Problems/<p>/Manifest.md frontmatter
  ├─ INSERT problems row
  ├─ 解析 # Statement / # Difficulty
  ├─ INSERT goals row (origin='root', status='open', depth=0)
  └─ 寫 Problems/<p>/Root.lean stub (theorem main : <statement> := by sorry)

asterism run [--once]
  └─ 啟動 dispatcher 主迴圈

# status / stop 等命令暫不寫，直接 sqlite 查 / Ctrl-C 終止
```

---

## 10. 不做（v1 教訓 + v3 取捨 + 二次審查精簡）

| 不做 | 原因 |
|---|---|
| Solver 獨立 pipeline kind | Builder phase 1+2 已涵蓋 |
| Path A/B 分裂 | v1 死碼來源 |
| `commit_state` pending/live 兩段式 | backup-restore 夠用 |
| `answer_data` typed JSON verdict | status='proved' + lean_path 已表達 |
| Stage 形式抽象 | 程式碼 inline、需要時 refactor |
| liveness check + cleanup_pending + cleanup_zombie | 單 wilson root 沒 sibling cancellation 場景 |
| Cancellation propagation 表 | 同上、`is_already_dispatched` 夠擋 |
| Refuter / Counterexample / Forward / Generalizer / ConstructionSearch | schema 留洞、實作 deferred |
| Strategist round-robin demux | 等 dispatcher 穩定再加 |
| evidence / twin_of / trust_set 欄位 | conjecture/refuter/library 用、deferred |
| events 表 audit log | dead_attempts + 主 loop print 夠 |
| continuous tasks pool | 沒 ConstructionSearch 不需要 |
| Library 跨 problem promotion | 等多 problem 才有意義 |
| separate META / HINTS / STATUS / OPEN / SHELVED / LOG / POSTMORTEM | 整合進 Manifest + DB |
| proved/dead 同 dir | dead 進 dead_attempts.proposal_md DB 字串 |
| asterism status / stop CLI 命令 | sqlite + Ctrl-C 夠 |

---

## 11. Milestone 1 通過條件

`asterism init wilson` + `asterism run`：
1. wilson_main goal 30 分鐘內 status='proved'
2. lake build proofs/L0001_wilson_main.lean，axioms 在 Manifest whitelist
3. 過程 0 個 fatal、< 3 個獨立 BUG
4. Tooling/ Python 行數 < 400（不含借自 Hadamard 的 spawn shell）
5. Manifest.forbidden_lemmas 含 ZMod.wilsons_lemma 下能透過 Backward 拆解走完

任一條沒過 → 停手分析、不繼續加 feature。

---

## 12. 後續（Milestone 1 過了再考慮、按優先序）

每條都先驗證需要再做、不一次塞進架構：

1. AND/OR 的 OR 開放 — 同 goal 多個 Strategy 並行嘗試、任一 success → goal proved。當前 dispatcher 對同 goal dedup（`bfs_refill` + `running` set）禁止並行。

   **動機**（wilson smoke 第 2 輪觀察 2026-04-29）：第 1 輪 fresh Context 一發 proved；第 2 輪 #1 fail 後 Context.md 累積 prior_failures 注入、agent reasoning 越來越深、#3/#4 連續 timeout。OR 並行下、N 條 Strategy 用 spawn 時 snapshot 的 Context、不會遞迴病態化、且能 hedge 風險。
2. 多 problem 平行
3. liveness check + cancellation propagation（兄弟 pipeline 多時才需要）
4. Strategist：cross-pipeline meta-decision、用 DB 累積判斷
5. answer_data typed verdict（conjecture / construction kind 啟用時必須）
6. Refuter / conjecture kind 啟用
7. commit_state 兩段式（多 worker 並發時才需要）
8. Deduper（Hadamard A2）+ Forward / Generalizer
9. Construction kind + ConstructionSearch（continuous task）
10. Library 跨 problem
11. events 表 + dashboard

每條都需要先有 wilson smoke pass。**沒 pass 不加新東西**。

---

## 13. 已決策事項

- **Manifest.md hints**：markdown only、`init` 時 parse 進 Context.md（不複製進 DB）
- **Manifest.md 格式**：寬 best-effort parse、缺欄位給 default + print warning
- **Tooling/ 重寫**：不借 Hadamard。Asterism Tooling/ 從零寫純 Python、要比 Hadamard 簡單 + 好。否則直接改 Hadamard 即可、不需 Asterism。
- **Shelve 判斷**：cascade rule 內、不在 `next_worker_kind`（見 §8）
- **Pool size**：預設 4、`ASTERISM_POOL=N` env 可覆蓋
- **`proofs/` 結構**：flat（≤30 個 L 檔；多了再分子 dir）
- **Worker 單次 timeout**：10 min（compactness 級才會超、那是 Backward 拆解的 signal）

### Tooling/ 重寫品質硬標

- 純 Python、不混 bash
- DB-backed、不用 .lean frontmatter 當第二份 source of truth
- 單 dispatcher process、不 nested shell scripts
- 模組界線清楚：dispatcher / pipeline / agent_spawn / commit / context_builder 各自 .py
- 每個 module < 200 行
- 總 Python 行數 < 400（見 §11 milestone 條件）

不達標 → 不如直接改 Hadamard。
