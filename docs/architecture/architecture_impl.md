# Asterism 實作細節（v3 配對文件）

## 0. 範圍

v3 講 **WHAT / WHY**：模型、不變量、組件契約。本文是「**動手前想細節時翻來看**」的補充——只覆蓋 v3 已決定的部分。

不放：

- spike 待辦清單（屬 dev/phase 文件）
- 未來 API stub（沒實作的別占位）
- v3 沒採的設計選項

v3 規格擴展時 → 同步補本文新章節。

---

## 1. Commit 協議實作

對應 v3 §5。

### 1.0 三步驟協議（INSERT / UPDATE 統一）

```
Step 1. BEGIN TX
        - INSERT case：INSERT row 含 commit_state='pending'、prior_state_snapshot=NULL
        - UPDATE case：把既有 (status, commit_state, ...) 序列化進 prior_state_snapshot,
                       UPDATE row commit_state='pending'（status 等業務欄位先別動）
        COMMIT
Step 2. mv staging .lean 到 lean_path（idempotent）
Step 3. BEGIN TX
        UPDATE row commit_state='live'、套用 final_fields（如 status='succeeded'）、
        清 prior_state_snapshot=NULL
        COMMIT
```

理由：DB row 當「我打算落地」的憑證，比反向掃 `Goals/` 找 orphan .lean 好——後者無法區分「commit 失敗的孤檔」與「人手放的檔」。snapshot column 讓 UPDATE case 能 deterministic 回滾，不必走「DELETE row」這條對 UPDATE 毀滅性的路徑（v2 原協議的 bug）。

### 1.1 CommitWriter

四個操作對應 v3 §5 commit 協議三步驟：

| 操作 | 對應 step | 行為 |
|---|---|---|
| `begin(table, op='insert', data)` | Step 1 | INSERT 新 row 含 `commit_state='pending'`、`prior_state_snapshot=NULL`；回傳新 ID |
| `begin(table, op='update', id)` | Step 1 | snapshot 既有 (status, commit_state, ...) 進 `prior_state_snapshot`、UPDATE row 為 pending；回傳同 ID |
| `stage_file(src, dst)` | Step 2 | mv staging 檔到 lean_path；idempotent（dst hash 已等於 src 則 skip） |
| `finalize(table, id, final_fields)` | Step 3 | UPDATE row 為 `commit_state='live'`、套用 final_fields（如 `status='succeeded'`）、清 `prior_state_snapshot=NULL` |

跨 row 的 multi-op commit（如 Refuter 同 TX 內 INSERT ¬G + UPDATE G.twin_of）走 `begin_batch`，把多筆 INSERT/UPDATE 串在一個 TX 裡。

### 1.2 各 pipeline commit 是 INSERT 或 UPDATE

| Pipeline | INSERT case | UPDATE case |
|---|---|---|
| Backward | 新 sub-Goals + 新 Strategy + strategy_subgoals | （無） |
| Builder | （無） | strategies.status: in_progress → succeeded |
| Refuter | 新 ¬G goals row | G.twin_of UPDATE（同 TX） |
| Forward | 新 Goal（origin='forward'） | （無） |
| Generalizer | 新 Goal（origin='generalizer', kind='theorem'） | （無） |
| Counterexample (refuted_with_witness) | Library/Counterexamples/<G>.json | G status='refuted' / answer_data={type:'witness',...} / trust_set / evidence patch witness |
| Counterexample (evidence_only) | （無）| G.evidence patch（merge `counterexample_tested_up_to`） |
| ConstructionSearch (proved_with_construction) | Library/Constructions/<G>.json + 新輔助 Goal `∃X, P(X)` + Strategy | G status='proved' / answer_data={type:'construction',...} / trust_set / evidence patch witness |
| ConstructionSearch (evidence_only) | （無）| G.evidence patch（merge `best_known + generations_completed`） |
| ConstructionSearch (checkpoint, 中間) | （無 INSERT 主表，但 INSERT construction_attempts row + UPDATE continuous_tasks）| best_score 改進時：G.evidence patch + Library/Constructions/<G>.json 同檔覆寫 |
| Refuted Silver → Gold 升級（cascade 處理）| （無 INSERT，原 json 改寫）| G answer_data={type:'classical',...} / trust_set 換 lean_axiom 全集 / Library/Counterexamples/<G>.json schema 改寫 |
| Construction Silver → Gold 升級（cascade 處理）| （無 INSERT，原 json 改寫）| G answer_data={type:'classical', lean_path} / trust_set 換 lean_axiom 全集 / Library/Constructions/<G>.json schema 改寫 |
| Strategist | strategist_decisions row | （無） |

Refuter 與 Counterexample (refuted_with_witness) 的多 op 用 `begin_batch`。

### 1.3 Recovery scan

掃 goals + strategies 兩表所有 `commit_state='pending'` row，逐筆判斷：

| 條件 | 動作 |
|---|---|
| staging 檔還在 | 重跑 mv（idempotent）+ UPDATE row 為 live、清 snapshot |
| staging 檔不在 + snapshot 為 NULL（INSERT case） | DELETE row |
| staging 檔不在 + snapshot 非 NULL（UPDATE case） | 從 snapshot 還原 (status, commit_state, ...)、清 snapshot |

觸發點：scheduler 啟動 / `asterism db recover` CLI / `asterism pipeline run` 開頭。

---

## 2. Cache 策略

對應 v3 §4.1。文件講原則，本節給數值與觸發 catalog。

### 2.1 TTL per scope

| scope / mode | TTL |
|---|---|
| `mathlib` | 3600 s |
| `library` | 3600 s |
| `local_goals` | 300 s |
| `inventory`（Strategist 用） | 30 s |
| `dedupe` | 走 mutation invalidation，**不靠 TTL** |

### 2.2 query_hash

```
key = SHA256(scope_tuple + "|" + mode + "|" + query + "|" + problem_or_empty)
```

`problem` 只在 scope 含 `local_goals` 時參與（避免 Problem A 的 INSERT 誤殺 Problem B 的 cache）。

### 2.3 Mutation invalidation 觸發 catalog

| 動作 | DELETE FROM search_cache 哪些 row |
|---|---|
| INSERT/UPDATE goals WHERE problem='X' | `WHERE problem_scope='X' AND scope LIKE '%local_goals%'` |
| INSERT/UPDATE goals (任意 problem) | `WHERE mode='dedupe'`（dedupe 跨 problem 比） |
| Library/Theorems/proved.lean append 或 Library/Counterexamples/ 寫入 | `WHERE scope LIKE '%library%'` |
| Mathlib upgrade（外部觸發） | `asterism cache invalidate --scope mathlib` 手動 |

### 2.4 何時上線

- P1–P3：cache 不啟用（每次實搜，慢但對）
- P4：Search subsystem 引入時一次到位

---

## 3. Library promotion 實作

對應 v3 §6。cascade 依 `status` + `answer_data.type` 分流。

### 3.1 Theorems/proved.lean（status='proved', answer_data.type='classical'）

```
1. file lock Library/Theorems/proved.lean（fcntl on Unix；Windows 走 sqlite advisory lock 跨 OS 一致）
2. compute lemma_name = "<problem>.<slug>"
3. SELECT 既有 library_index WHERE name=lemma_name
   - 命中：emit warning event、不 append（first-write-wins）、release lock
   - 未命中：INSERT library_index + append re-export 行
4. release lock
5. lake build Library 子模組
   pass：完成
   fail：revert（刪 append 行 + DELETE library_index + 把 root Goal 標 attempting + dead_attempts）
```

`library_index` table（v3 §9.1 schema 沒列；M3 加）：

| name TEXT PK | problem | source_root_id FK goals | layer enum (Theorems/Counterexamples) | committed_at ts |

re-export 行格式：

```lean
-- from <problem>: <root_id>
theorem <problem>.<slug> := <problem>.<slug>.theorem
```

### 3.2 Counterexamples/<problem>_<slug>.json（status='refuted'）

兩級皆寫此 json。無 file lock 衝突（每 Goal 唯一檔）。內容依 `answer_data.type` 變：

**type='classical'（formal proof exists）**：

```json
{
  "goal_id": "<G_id>",
  "statement": "<G stmt>",
  "type": "classical",
  "negation_goal_id": "<¬P(w) 或 ¬G 的 Goal id>",
  "negation_lean_path": "Problems/<n>/Goals/.../<slug>.lean",
  "ts": "..."
}
```

**type='witness'（computational only）**：

```json
{
  "goal_id": "<G_id>",
  "statement": "<G stmt>",
  "type": "witness",
  "witness": <serialized>,
  "evaluator_hash": "<sha256>",
  "range": "<domain>",
  "seed": <int>,
  "ts": "..."
}
```

INSERT `library_index (name=file_path, layer='Counterexamples', source_root_id=goal_id, ...)`。

無需 lake build verify（json 不入 Lean 編譯）。無需 PromotionJudge（自動 promote）。

**Silver → Gold 升級時**：原 RefutedWitness 寫的 json 直接覆寫成 RefutedClassical schema（同檔名、不重複 INSERT library_index row，只 UPDATE）。

### 3.3 Constructions/<problem>_<slug>.json（status='proved', answer_data.type ∈ {construction, classical}）

兩級皆寫此 json。無 file lock 衝突（每 Goal 唯一檔）。內容依 `answer_data.type` 變：

**type='construction'（computational silver verdict）**：

```json
{
  "goal_id": "<G_id>",
  "statement": "<G spec>",
  "type": "construction",
  "witness_lean_path": "Problems/<n>/Goals/.../candidates/<id>.lean",
  "score": 0.97,
  "evaluator_hash": "<sha256>",
  "generation": 47,
  "seed": <int>,
  "best_known_history": [{ "generation": N, "score": ... }, ...],
  "ts": "..."
}
```

**type='classical'（formal existence proof，silver→gold 升級後）**：

```json
{
  "goal_id": "<G_id>",
  "statement": "<G spec>",
  "type": "classical",
  "lean_path": "Problems/<n>/Goals/.../<slug>.lean",
  "constructed_witness_lean_path": "...",
  "ts": "..."
}
```

INSERT `library_index (name=file_path, layer='Constructions', source_root_id=goal_id, ...)`。

**checkpoint 期間 best_score 改進**：同檔覆寫 type='construction' schema（更新 score / generation / best_known_history），不重複 INSERT library_index。

**Silver → Gold 升級時**：原 type='construction' 寫的 json 覆寫成 type='classical' schema。

---

## 4. Validator 實作

對應 v3 §5.2 + §7.4。

### 4.1 為何禁 regex

Hadamard 前例：regex 處理 Lean 源碼曾被字串內 `:` 註解坑過、`deferred.md` 自己列為脆弱面。dedupe.lean 已有 Lean exe，validator 共用基礎建設邊際成本低。任何 PR 提交含 regex parse Lean 源碼 → review 直接 reject。

### 4.2 工具介面

```
tools/validator.lean

CLI: validator hypothesis_carry --parent <file> --subgoals <files...>

行為：
  Lean.Elab.Frontend parse parent + 每個 sub-Goal
  抽 binder list (name, type)
  輸出 JSON：
    [{ subgoal: <id>, missing_binders: [<name>...],
       type_mismatches: [(name, parent_type, subgoal_type)...] }]
```

Python 端 `runtime/stages/validator.py`：呼叫上述 + 整合 SQL UNIQUE check（slug collision）+ 純整數比（sub-Goal 數量 ≤ 8）。

---

## 5. Trust set 序列化 + Problem META.md

對應 v3 §7.1。

### 5.0 Problem META.md 格式

YAML frontmatter。`axioms` 欄位**強制宣告**（無框架預設繼承）；其餘欄位選擇性：

```yaml
---
problem_name: sylvester_gallai
axioms:                        # 強制：該 Problem 的完整 axiom 基礎宣告
  - propext
  - Quot.sound
  - Classical.choice
# 純構造研究 → 移除 Classical.choice
# 接受 Mathlib 常見 → 加 Classical.indefiniteDescription
# 條件性研究 → 加 riemann_hypothesis 等 mathematical 假設

models:                        # 選擇性：覆寫框架 agent.model_defaults
  backward.agent: opus         # 對該 Problem 的 Backward 用 opus（預設 sonnet）
  builder.tactic_llm: sonnet   # 對 Builder.tactic_llm 升 sonnet（預設 haiku）
# 未宣告 → 用框架預設（架 §8.3）
---
```

未宣告 `axioms` → META.md 解析失敗，scheduler 拒絕載入該 Problem。`models` 缺欄位純落框架預設、不報錯。

`Library.whitelist`（Library/Theorems/proved.lean 接受的 axiom）跟 Problem.axioms **完全獨立**——後者是 per-Problem 範圍、前者是框架全域 config。Library promotion 只查 `Library.whitelist`，不查 Problem.axioms。

### 5.1 JSON 形狀

```json
[
  { "name": "propext",         "kind": "lean_axiom",
    "provenance": "lean #print axioms", "confidence": 1.0 },
  { "name": "Quot.sound",      "kind": "lean_axiom",
    "provenance": "lean #print axioms", "confidence": 1.0 },
  { "name": "Classical.choice", "kind": "lean_axiom",
    "provenance": "lean #print axioms", "confidence": 1.0 }
]
```

`confidence` 對 lean_axiom 永遠 1.0，可省略。對未來 kind（cited / heuristic / computational）才有意義。v3 不啟用其他 kind。

### 5.2 從 #print axioms 構造

對 `<theorem>` 跑 `lake env lean -e '#print axioms <theorem>'`、parse 出 axiom name 列表，每個 name 包成一個 trust entry：`kind='lean_axiom'`、`provenance='lean #print axioms'`、`confidence` 省略（隱含 1.0）。subprocess timeout 60s。

### 5.3 Accept rule（依 status + answer_data.type 分流）

給定 `trust_set`、`allowed_axioms`（依呼叫方不同帶不同值）、`status`、`answer_data.type`：

- **status='proved'**（answer_data.type='classical'）：trust_set 全 entry 滿足 `kind='lean_axiom'` 且 `name ∈ allowed_axioms`
- **status='refuted', type='witness'**：每 entry 滿足
  - `kind='lean_axiom'` 且 `name ∈ allowed_axioms`，OR
  - `kind='computational'` 且 metadata 含 `evaluator_hash`、`range`、`seed`（reproducibility 必要）
- **status='refuted', type='classical'**：繼承 twin Goal 的 trust_set，不另構造
- 其他狀態（open / attempting / shelved）：不適用 accept rule（無 verdict 落 Library）

**呼叫方對應的 `allowed_axioms`**：

- Cascade verdict 檢查（§6 step 3）→ `allowed_axioms = Problem.axioms`
- Library/Theorems/ promotion → `allowed_axioms = Library.whitelist`（框架全域 config，跟 Problem.axioms 獨立）

兩個呼叫各自帶獨立 whitelist，不共用、不繼承。違反者 → 回傳 (false, rejected list)；全通過 → (true, [])。

Library/Counterexamples/ promotion 對 computational entry 額外檢 metadata 完整（evaluator_hash + range + seed 都在）。

---

## 6. Stage 實作補充

對應 v3 §3 與 §5.5 step 2。

### 6.1 failure_replay SQL

```sql
SELECT reason_summary, ts FROM dead_attempts
WHERE target_id = ? AND target_kind = ?
ORDER BY ts DESC LIMIT ?    -- ? = K_digest
```

### 6.2 self_verify lake 命令

```
single mode:  lake env lean <staging_file>
multi mode:   lake build <staging_dir>
```

兩者都用 `subprocess.run`，timeout = 600s。stderr / stdout parse 找 sorry / type error。

### 6.3 failure_archive SQL

```sql
INSERT INTO dead_attempts
  (target_id, target_kind, pipeline_id, pipeline_kind,
   outcome, reason_summary, ts)
VALUES (?, ?, ?, ?, ?, ?, datetime('now'));
```

之後 `rm -rf Goals/<G>/Staging/<p_uuid>/` + 刪該 pipeline 的 session jsonl。

### 6.4 Inventory metrics SQL

```sql
-- per Goal
SELECT g.id, g.status, g.depth, g.status_changed_at,
  (SELECT COUNT(*) FROM dead_attempts d
   WHERE d.target_id = g.id
     AND d.reason_summary LIKE 'bad sub-Goal%') AS bad_goal_count,
  (julianday('now') - julianday(g.status_changed_at)) * 24 * 60 AS attempting_age_min,
  (SELECT json_group_object(s.status, COUNT(*))
   FROM strategies s WHERE s.goal_id = g.id GROUP BY s.status) AS child_strategy_outcomes
FROM goals g
WHERE g.problem = ? AND g.commit_state = 'live';

-- per subtree（recursive CTE）
WITH RECURSIVE subtree(root_id, current_id, depth) AS (
  SELECT id, id, depth FROM goals
   WHERE origin = 'root' AND problem = ? AND commit_state = 'live'
  UNION ALL
  SELECT s.root_id, sg.subgoal_id, g.depth
  FROM subtree s
  JOIN strategies st ON st.goal_id = s.current_id
                     AND st.commit_state = 'live'
  JOIN strategy_subgoals sg ON sg.strategy_id = st.id
  JOIN goals g ON g.id = sg.subgoal_id AND g.commit_state = 'live'
)
SELECT root_id, depth, COUNT(*) AS goal_count
FROM subtree GROUP BY root_id, depth;

-- 全域 top-N（最多 bad_goal）
SELECT g.id, COUNT(d.id) AS bg_count
FROM goals g LEFT JOIN dead_attempts d
  ON d.target_id = g.id AND d.reason_summary LIKE 'bad sub-Goal%'
WHERE g.commit_state = 'live'
GROUP BY g.id ORDER BY bg_count DESC LIMIT 10;
```

### 6.5 Agent stage runtime（multi-provider）

對應架 §8.3。Agent stage 的 subprocess 執行包成 Provider 抽象，三家 provider（claude / gemini / codex）統一介面。

**Provider 介面**：

```
class Provider:
    name: str                # 'claude' / 'gemini' / 'codex'
    model_map: dict[str, str]  # tier 詞彙 → 該 provider 的 model id

    def invoke(model_tier, prompt, scope_dirs, session_id) -> AgentResponse
        # scope_dirs: 該 stage 的 staging dir + Problem dir + Mathlib + Library
        # 內部負責用該 provider 的 CLI flag 限制 fs 視野
        # session_id: pipeline 級唯一，pipeline 結束後 GC
```

**各 provider scope-isolation**：

| Provider | Scope flag | 不變量驗證 |
|---|---|---|
| `claude` | `claude --add-dir <path1> --add-dir <path2>` | 結束後 git status 檢查除 staging 外無檔案被改 |
| `gemini` | gemini CLI tool scope 限制 | 同上 git status 兜底 |
| `codex` | codex CLI sandbox / approval mode（auto-approve only for staging path） | 同上 git status 兜底 |

git status 等價檢查是統一的「最後防線」，不因 provider scope flag 而省略——provider 的 scope 是「希望 agent 不要動」、git status 是「事後驗 agent 真的沒動」。

**Fallback 流程**：

```
for provider in agent.fallback_chain:
    for retry in range(N_retry):
        try:
            response = provider.invoke(model, prompt, scope_dirs, session_id)
            if validate_scope(staging_dir):
                return response
        except (Timeout, ProviderError):
            continue
    # 該 provider 用盡 retry → 切下一家
return outcome=exhausted
```

**Model 解析**（解 model_tier → provider 的 model id）：

```
def resolve_model(pipeline_kind, agent_stage, problem_meta, strategist_payload):
    # 三層覆寫：strategist > problem > framework
    if strategist_payload and strategist_payload.get('model'):
        return strategist_payload['model']
    if problem_meta.models.get(f'{pipeline_kind}.{agent_stage}'):
        return problem_meta.models[f'{pipeline_kind}.{agent_stage}']
    return framework_config.agent.model_defaults[f'{pipeline_kind}.{agent_stage}']
```

provider 解析也三層（strategist payload `provider?` > 框架 active provider）；若 strategist 指定的 provider 不在 `agent.providers` → reject decision、log 警告。

**Prompt 共用**：`docs/prompts/<stage>.md` 一份 prompt 三家共吃。框架不主動為單家 provider 改寫；fallback 觸發時若 outcome 持續差，由人類觀察 outcome 統計後人工調 prompt。

### 6.6 Lake build 策略

```
1. compute_affected(changed_files):
     簡化版（P2）：直接回傳 [<problem>/Root.lean]
     精確版（P4+）：從 changed_files walk import graph
2. subprocess: lake build <targets>，timeout = 600s
3. parse build output → BuildResult { success, build_failures, sorry_remaining }
```

並發 lake build 安全性由 spike 003 結果決定；不安全則加全域 build lock（threading.Lock）。

---

## 7. Subsystem 實作補充

對應 v3 §4.2 Dedupe。

### 7.1 Dedupe Lean executable

```
tools/dedupe.lean

CLI: dedupe --candidate <stmt_file> --against <list_file> --mode <strict|iff_lite>

strict（預設）：
  先 elaborate candidate；若 elaborate 失敗 → 直接印 NOVEL（容錯，不報錯）
  否則逐筆對 candidate 與 entry 跑 Lean.Meta.isDefEq；hit → 印 entry id；miss → 印 NOVEL

iff_lite（opt-in）：
  strict miss 後額外跑：
    theorem _check : <candidate> ↔ <entry> := by simp; try decide; try norm_num; ring_nf
  在 timeout（預設 5s）內 elaborate 成功 → hit
```

呼叫方式：`lake env lean tools/dedupe.lean -- --candidate ... --against ... --mode strict`，subprocess timeout 30s。

**Elaborate 失敗 → NOVEL 容錯**：呼叫端可以在 candidate 還沒過外部 self_verify 時直接呼叫 dedupe（如 Backward 對 sub-Goal 用 sorry placeholder 的 statement），dedupe 內部處理。失敗會回 NOVEL 而非報錯。

Tooling 端只負責呼叫與整合 search cache（cache 對 dedupe 走 mutation invalidation，見 §2.3）。

### 7.2 Evolution subsystem

對應 v3 §4.3。共用基礎建設，被 Counterexample 與 ConstructionSearch 共用。

**核心介面**（Python module，所有 search-driven pipeline 都呼叫此）：

```
runtime.evolution.run(
    target_goal_id,
    candidate_generator,    # 給定 (parent_candidate, mutation_op) → list of candidates
    evaluator,              # 給 candidate → (compiles?, score, witness_lean_path)
    mutation_operators,     # list[Operator]，框架預設 + Goal override
    initial_population,     # 第一代
    budget,                 # generations 或 wall_clock
    runtime_mode,           # 'atomic' or 'continuous'
    checkpoint_interval,    # continuous 模式用
)
→ EvolutionResult
   { best_candidate, best_score, generation_reached,
     terminated_reason: 'target_reached' | 'budget_exhausted' | 'paused' }
```

**Per-iteration loop**（內部）：

```
for g in 0..budget:
    candidates = generator(top_K(population_g), mutation_ops)
    compiled = [evaluator.compile(c) for c in candidates]      # type-check
    scored = [evaluator.score(c) for c in compiled if c.ok]    # scorer
    population_{g+1} = top_K(population_g + scored)
    if best(population_{g+1}).score >= target:
        return EvolutionResult(target_reached, best=...)
    if continuous and (now - last_checkpoint) >= T_checkpoint:
        emit_checkpoint(g, population_{g+1}, best)
    if check_pause_signal():
        return EvolutionResult(paused, ...)
return EvolutionResult(budget_exhausted, ...)
```

**Mutation operators 預先註冊**（框架 default）：

| operator | 適用 candidate 型 | 行為 |
|---|---|---|
| `random_perturb` | 數值類（matrix / vector） | 隨機改動 k 個 entries |
| `column_swap` | 矩陣 | 交換兩 column |
| `crossover` | 任意 | 從兩 parent 各取一半 |
| `lean_synth` | 任意 | 呼叫 LLM agent 寫變異版本 |

Goal 可在 `goals.question.mutation_operators` 註冊客製 operator（Python module 路徑）。

**reproducibility metadata**：每次 EvolutionResult 帶 `evaluator_hash`（scorer code + spec hash）+ `seed`。

### 7.3 Counterexample atomic mode 在 Evolution 之上

Counterexample atomic 模式是 Evolution 的退化 case：

- mutation_operators = [enumerate_in_order]（純枚舉，不演化）
- candidate_generator = 純枚舉 domain 內元素
- evaluator.score(c) = if predicate(c) is False then 1.0 else 0.0
- target = 1.0（即任一 false 命中就停）

介面對齊，未來升級 continuous 模式只是換 mutation_operators 與 budget 設定，無需動 pipeline 結構。

---

## 8. Counterexample 實作（atomic 模式）

對應 v3 §5 與 pipelines.md §6。

### 8.1 evaluator 介面

```
tools/counterexample.lean

CLI: counterexample --predicate <file> --domain <expr> --seed <int> --budget-sec <int>

predicate 檔內容：Lean 寫一個 decidable predicate，例如
  def P : Nat → Bool := fun n => n.isPrime ∧ ¬ ((n+2).isPrime)

domain 表達式：列舉範圍，例如 "Fin 1000" 或 "List.range 10000"

輸出 JSON：
  { found: bool,
    witness?: <serialized witness>,    // found=true 時填
    tested_up_to: int,                  // 已測元素數
    elapsed_sec: float }
```

`found=true` → commit 走 refuted_with_witness 路徑（§8.2）；`found=false` → evidence_only 路徑。

### 8.2 commit 動作（silver-only）

找到 witness w 後 commit 一次寫入（同 TX）：

1. 構造 `kind=computational` trust entry：
   ```json
   { "name": "counterexample_<G_id>",
     "kind": "computational",
     "provenance": "tools/counterexample.lean, evaluator hash <sha256>",
     "metadata": { "evaluator_hash": "...", "range": "...", "seed": <int>, "elapsed_sec": <f> } }
   ```
2. UPDATE G：
   - `status='refuted'`
   - `answer_data={type:'witness', witness, evaluator_hash, range, seed}`
   - `trust_set=[<上述 computational entry>]`
3. UPDATE G.evidence patch：把 witness 紀錄為 `counterexample_witness: {witness, evaluator_hash, range, seed}`，**給後續 Refuter agent 撈來用 witness-based proof template**
4. 寫 `Library/Counterexamples/<G>.json`（type='witness' schema）
5. cancellation：見 §8.3

outcome = `refuted_with_witness`。

### 8.3 Cancellation 觸發

commit 後執行：

```
SELECT id FROM pipelines
WHERE target_id = <G_id>
  AND status = 'running'
  AND kind IN ('Backward', 'Builder', 'Counterexample')
  AND id != <self.id>
```

**注意：Refuter 不在 cancel list 內**——讓它有機會證 ¬G 把 G 從 silver 升級到 gold（§8.4）。對每個結果 SIGTERM subprocess。

### 8.4 Silver → Gold 升級（cascade-driven）

cascade 處理 Refuter / Builder 鏈成功證 ¬G 的 pipeline_finished 時，twin cascade 規則：

```
若 G.twin_of = <剛 proved 的 ¬G>:
  原 G.status ∈ {open, attempting} → UPDATE G status='refuted',
                                            answer_data={type:'classical', negation_lean_path, negation_goal_id}
  原 G.status='refuted', answer_data.type='witness' → UPDATE G answer_data={type:'classical', ...},
                                            trust_set 換成 ¬G 繼承的 lean_axiom 全集,
                                            Library/Counterexamples/<G>.json 改寫成 type='classical' schema
  原 G.status='refuted', answer_data.type='classical' → no-op（已 classical）
  原 G.status='proved'                              → fatal halt（dual-proved）
```

升級不可逆：classical → witness / NULL 一律拒絕。

### 8.5 Budget 解析

`counterexample_atomic_budget` 與 `counterexample_atomic_range_default` 從 Config 解析（per-Problem 可 override，見 v3 §8）。Strategist inject 時可在 decision payload 內覆寫 `budget` / `range`。

---

## 9. ConstructionSearch + Continuous task runtime 實作

對應 v3 §5（continuous runtime）+ pipelines.md §7（ConstructionSearch）。

### 9.1 evaluator 介面

ConstructionSearch 的 evaluator 是 **Python module + Lean type-checker** 配對：

- **scorer.py**（Goal 自帶，住 `Problems/<n>/Goals/<G>/scorer.py`）：純 Python，給 candidate（serialized）→ float score
- **spec.lean**（Goal.question.spec_lean_path 指向）：Lean predicate `def spec : <Type> → Prop`
- type-check 走 `lake env lean <candidate>.lean`（候選須含 `theorem _ : spec witness := ...`）

scorer 跑在 subprocess + resource limit（CPU / memory），基本沙箱化。

### 9.2 ConstructionSearch lifecycle

入池 → 進 continuous_tasks 表（lifecycle_state='running'）→ runtime.evolution.run 跑 evolution loop（見 §7.2）

**checkpoint 觸發**：
- 每 T_checkpoint=5 min
- 或 evolution 內 best_score 改進
- 流程：
  - INSERT construction_attempts row（該代每候選一筆）
  - UPDATE continuous_tasks.checkpoint_state（current generation, population, best）
  - 若 best_score 改進 → UPDATE goals.evidence + 同檔覆寫 Library/Constructions/<G>.json
  - emit `task_checkpoint` event

**終止**：
- `target_reached` → commit 成 silver verdict（同 §1.2 catalog ConstructionSearch (proved_with_construction) 行）
  - 還 spawn 輔助 Goal `∃ X, P(X)` + 候選 Strategy（給 Builder 試證升級 gold）
- `budget_exhausted` → evidence_only commit
- `paused` → continuous_tasks.lifecycle_state='paused'，working dir 保留，可 resume

### 9.3 Continuous task runtime 整合

**Pool**：scheduler 維護兩 pool（atomic + continuous），各自 cap、各自 dispatch loop。

**Crash recovery**：scheduler 啟動時：
- 對每個 `continuous_tasks` row lifecycle_state='running' 的 task：
  - 檢查 working dir 是否還在 + checkpoint_state 是否完整
  - 若完整 → 重啟 task，從 checkpoint_state 接續
  - 若殘缺 → mark lifecycle_state='killed'，emit alert

**Pause / Resume**：
- pause(scope=continuous_task_id) → SIGTERM subprocess + UPDATE lifecycle_state='paused'
- resume → 重啟 subprocess，從 checkpoint_state 接續

**Cancellation**：
- cascade 觸發 G 的 terminal verdict（除 silver 例外）→ kill 對應 ConstructionSearch task（SIGTERM + 5s SIGKILL fallback）+ UPDATE lifecycle_state='killed'

### 9.4 Builder 證 ¬¬X 升級路徑

ConstructionSearch silver commit 內 spawn 的輔助 Goal：

- statement: `theorem g_construct_ex : ∃ X, P(X)`
- origin: 'construction_witness'
- twin_of: NULL（不是 G 的 negation）
- **derived_from**: 原 G 的 id（goals 表 FK，cascade 用此回查升級對象）
- 帶現成 Strategy proof body 候選（`⟨witness, by decide⟩` / `⟨witness, by norm_num⟩` / `⟨witness, by Spec.satisfies_proof⟩`）

normal Builder 接手用標準 retry。Builder proved → cascade 偵測 origin='construction_witness' + 從 `derived_from` FK 找到原 G → UPDATE 原 G `answer_data={type:'classical', lean_path}`、trust_set 換成 lean_axiom 集、Library/Constructions/<G>.json 改寫 type='classical' schema。

**候選 list 全死的 fallback**：候選 proof body 全部 Builder exhausted（如大矩陣 `by decide` timeout）→ cascade 對輔助 Goal spawn 一個 Backward 走標準拆解路徑（不直接 fail）。輔助 Goal 從此被當 normal theorem-kind Goal 攻擊；Backward 拆出來的 sub-Goals 各自走 Builder + 可能的進一步 Backward；任一條 prove 鏈成功 → cascade 升原 G silver→gold。Backward 也 exhausted → 輔助 Goal status='attempting' + 留 evidence；Strategist 可介入 Shelve（P7）；原 G 仍 silver verdict（construction）、不退化。

---

## 10. Pack 擴展指南

每加新 pipeline / Goal kind / trust kind / Library 層 / event 都會撞到一群觸點。本節列觸點 checklist + 推薦設計模式，避免漏改與發散。

### 9.1 觸點 checklist

**加新 pipeline**：

- [ ] v3 §5 對照表加一行（觸發於 / 產出）
- [ ] v3 §6 structural refill 加 enqueue 條件（若有結構性觸發）
- [ ] v3 §6 cascade 加 outcome → effect 規則
- [ ] v3 §6 Strategist demux enum 加新值（若 Strategist-injectable）
- [ ] v3 §9.1 `pipelines.kind` enum + `queue.kind` enum 擴值
- [ ] pipelines.md 加新節（stages / outcome / 行為規則）
- [ ] impl §1.2 commit catalog 加新 row（INSERT / UPDATE 分流）
- [ ] impl 加新 §X 實作節（agent prompt / evaluator / cancellation 規則）

**加新 Goal kind**：

- [ ] v3 §2.2 metadata 表 `kind` 描述更新
- [ ] v3 §6 structural refill 加 kind-specific dispatch
- [ ] v3 §7.3 D_max[kind] 加值
- [ ] v3 §8 配置表加 D_max[kind] 一行
- [ ] v3 §9.1 `goals.kind` enum 擴值
- [ ] v3 §7.1 accept rule 若需區分 kind 則加分流
- [ ] pipelines.md / impl 對應 pipeline 的觸發條件加 kind 過濾

**加新 trust kind（如 cited / heuristic）**：

- [ ] v3 §7.1 trust_set entry 描述加 kind
- [ ] v3 §7.1 accept rule 加新 kind 的接受條件
- [ ] impl §5.3 accept rule 程式碼擴新 case
- [ ] producer pipeline（哪個 pipeline 寫此 kind）spec
- [ ] 對應 Library 落點 spec

**加新 Library 層**：

- [ ] v3 §6 Library promotion 加新 (status, answer_data.type) 條件 → 該層
- [ ] v3 §9.2 file layout 加新層
- [ ] impl §3 Library promotion 加新節（file 寫入流程、conflict 處理）
- [ ] `library_index.layer` enum 擴值
- [ ] search subsystem `library_typed` scope（若引入）加新層

**加新 event kind**：

- [ ] v3 §6 events 表加新 kind 描述
- [ ] v3 §9.1 `events.kind` enum 擴值
- [ ] scheduler 加新 event 的處理邏輯
- [ ] 哪個 stage / pipeline emit 此 event 要明確

### 9.2 設計模式（實作時採用）

**Cascade rules 中央 dispatch 表**：

cascade 規則不寫在 scheduler.cascade() 內 if-else 鏈，改成明確 dispatch 表：

```
cascade_table: dict[(pipeline_kind, outcome), list[CascadeAction]]
```

CascadeAction 列舉：UpdateGoal / UpdateStrategy / EmitEvent / CancelPipelines / TriggerLibraryPromotion / ...

優點：
- 加新 pipeline 只新增 entry，不動 scheduler 主迴圈
- 規則可被列表 / 視覺化 / 反查
- 除錯時看 table 就知道為何某 outcome 觸發某 effect

**Strategist decisions 從 pipeline registry 派生**：

不要硬編碼 `decisions enum = {Refuter, Forward, Backward, Counterexample, Shelve}`。改成：

```
pipeline_registry: list of pipeline metadata
  含 (kind, runtime, strategist_injectable, default_budget, ...)

Strategist agent prompt 動態列出所有 strategist_injectable=True 的 pipeline
demux 動態 dispatch
```

新 pipeline 註冊時自動進 Strategist 視野，不用改 prompt 模板與 demux code。

**Config 兩層獨立解析**：

框架配置（全域）與 per-Problem 配置（META.md）獨立查詢、無繼承（v3 §8）。新加的可配置項依層級加進對應位置：runtime 旋鈕進框架 config、Problem 範圍的設定進 META.md 強制宣告。

### 9.3 擴展規模估算

依上面 checklist，常見擴展類型規模：

| 類型 | 動的觸點 |
|---|---|
| 加 1 個 pipeline + 對應 Library 層 + trust kind 啟用 | ~15-20 觸點 |
| 加 Goal kind 系列（如 construction）| + continuous task runtime（基礎建設）+ ~10 觸點 |
| 純結構重構（如 typed relations）| ~20 觸點，但能力增量小 |

任一較大擴展**強烈建議先寫獨立計畫文件**（如 `docs/extension_<name>_plan.md`），用本節 checklist 對清單，避免漏改。

---

## 11. 決策日誌

時間序追加，不刪。季度合併穩定決策進前面 sections。

### 2026-04-27

- **Trust set 統一表達 answer 依賴**（取代 verification_level enum）。理由：evidence kinds 本質是廣義 axiom whitelist；統一概念簡化設計。Library 接受規則改 trust_set composition，不再 enum 列舉
- **Axiom whitelist 改 per-Problem 配置**（後來再演化為兩層獨立 whitelist，見後續決策）。理由：硬編碼三公理對純構造 / 用 declared axiom 的 Problem 不彈性
- **Validator 走 Lean.Elab，禁 regex parse Lean 源碼**。理由：歷史經驗 regex 被字串內 `:` 註解坑過。dedupe.lean 已有 Lean exe，validator 共用基礎建設邊際成本低
- **`parent_subgoal_max_similarity` 加進 strategies table**。理由：歷史撞過 IH-trap（sub-Goal 形狀同父、IH 不可呼叫），只能等 D_max 兜底。Strategist 用此值偵測 IH-trap pattern 提前出手。Cheapest path 先做（spike 後再決升級）
- **Commit 協議 INSERT / UPDATE 統一（snapshot column）**。理由：對 UPDATE case 走「DELETE row」recovery 有毀滅性風險。snapshot 讓 UPDATE 能 deterministic 回滾
- **延遲 hypothesis bundle 一級化**。理由：經驗速解 ~90% 覆蓋率。KPI gate：累計 ≥ 10 個 Problem 後 miss rate > 10% 才升級成 first-class bundle propagation
- **Counterexample = 純 silver 製造機，不嘗試 inline 形式驗證**。理由：inline gold 嘗試（不論 lake 直跑或建 ¬P(w) Goal 走 Builder）都會把 Counterexample 角色搞複雜。改成 Counterexample 找到 witness 直接 silver verdict（RefutedWitness + computational trust），witness 順手寫進 G.evidence。後續 Refuter agent 看 evidence 撈 witness 用 short proof template；Refuter 證 ¬G 成功 → cascade 把 G 從 silver 升級到 gold（RefutedClassical）。trust 強度只允許單向升級（gold → silver 不可逆）
- **Forward seed pool 含 negation Goals**。理由：Refuter 證的 ¬G、Counterexample 產的 ¬P(w) 邏輯上跟 positive proved Goal 等價，Forward agent 一視同仁從 negation seed 推 corollary
- **trust_set kind enum 收窄為 lean_axiom + computational**。理由：cited / heuristic 暫無 producer / consumer，YAGNI。list-of-entries 結構保留（computational entry 有 evaluator_hash / range / seed metadata，需要 list 形式）；未來引入 cited / heuristic 時擴 enum + accept rule 分支即可
- **取消 answer_kind 欄位，verdict 細節塞進 answer_data json**。理由：原本 status enum + answer_kind enum 兩 enum 蓋同一概念空間，靠 sync invariant 黏合。改成單一 status enum + answer_data 帶 `type` discriminator + verdict payload，沒跨欄位 invariant。SQL filter 用 `answer_data->>'type'` 表達 verdict 細節
- **取消 per-Problem override 機制，改成兩個獨立 whitelist**。理由：原本「框架預設 + Problem 可 override」概念糾結（讀 Problem 要查框架預設才完整、Library promotion 還要寫例外規則）。改成 Problem.axioms（per-Problem 強制宣告完整集合，無繼承）+ Library.whitelist（框架全域 config，獨立值），兩個各自獨立查詢、無 override 概念。Problem 自含、Library promotion 例外段消失、META.md 強制宣告反而強迫 Problem 作者思考 axiom 基礎
- **引入 construction kind + ConstructionSearch pipeline + continuous task runtime + Evolution subsystem**。理由：framework 從「證 / 反證 命題」擴張到「找滿足 spec 的具體 instance」這個 mission 核心問題類別（Hadamard / cap set 等）。連帶引入：(1) continuous task runtime 雙 pool 機制（Pack B 的真實基礎建設、未來 PatternMiner 等共享）；(2) Evolution subsystem 共用搜尋 / 評分 / mutation 內核給 Counterexample 與 ConstructionSearch；(3) silver/gold 升級 cascade 對稱複用至 construction（找到 H → silver → spawn `∃X,P(X)` 給 Builder 證 → gold）
- **Construction 設計題決策**：question 用 Lean predicate（type-safe）、evaluator 用 Python（scoring）+ Lean（type-check）配對、mutation operators 框架預設（4 個）+ Goal override、best-known 在 checkpoint 時 promote、Strategist signal 用 20 代 plateau / 0.95 target、不引入 ConstructionRefuter（impossibility proof 走一般 theorem 路徑）、construction kind 結構性派發為 Backward + ConstructionSearch 兩線（Builder 隨 Strategy 自動 enqueue）、Counterexample 順手重構走 Evolution subsystem 介面
- **加 Generalizer pipeline（無 cluster 版）**。理由：framework 自主探索能力的最便宜入口——pipeline 結構簡單（類似 Forward 簡化版），讓 Strategist 可獨立 inject「找 generalization」任務、prompt 比 Forward 多 mode 寫得清。**沒**做自動 cascade（G\* proved 不自動把原 G 標 proved）——這需要 Cluster typed relation 機制，留待後續 Pack。當前 Generalizer 純粹是「Goal seeder」
