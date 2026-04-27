# Phase 5 — Construction

## 目標

P1–P4 處理「證 / 反證 命題」。P5 引入第三類 mission：找滿足 spec 的具體 instance（Hadamard 矩陣、cap set、graph 屬性實例 等）。
新增 `kind=construction` Goal、ConstructionSearch pipeline（continuous mode）、continuous task runtime（雙 pool 的第二個 pool）、checkpoint 協議、Evolution subsystem 升級到 continuous mode 含真實 mutation operators。
**完成 silver→gold 升級對稱**：找到 instance H → silver verdict（type='construction'）→ spawn 輔助 Goal `∃X, P(X)` → Builder 證 → cascade 升 gold（type='classical'）。

## Scope

### In

- **`kind=construction` Goal 全展開**
  - `goals.kind` enum 含 'construction'（P2 schema 起就有 enum value，P5 才真實 dispatch）
  - `goals.question` json 強制（construction-only）：`{spec_lean_path, scorer_module, mutation_operators?}`（v3 §2.2）
  - structural refill 對 `kind=construction` 並排 enqueue Backward + ConstructionSearch（Backward 試結構性拆解；Builder 不直接派，由 Backward 後續產 Strategy 才走 leaf 規則）（v3 §6 task queue 段）
- **ConstructionSearch pipeline**（pipelines.md §7，continuous mode）：完整 stage 序列 + loop 控制
- **Continuous task runtime**（v3 §5「Continuous task runtime」段）
  - 第二個 pool（`P_continuous`，預設 P/4）
  - 跟 atomic pool 並列、queue 與 dispatch 分流
  - checkpoint 協議（v3 §5「Checkpoint 協議」段）：T_checkpoint=5 min 或 budget event 觸發
  - lifecycle_state ∈ {running, paused, done, killed}
  - Pause / Resume control_signal 支援
  - T_pause_max=7 days timeout 自動 killed
  - Crash recovery（impl §9.3）：scheduler 啟動掃 lifecycle_state='running' task、checkpoint_state 完整則重啟 + resume、殘缺則 killed + alert
- **Evolution subsystem 升級 continuous mode**（v3 §4.3、impl §7.2）
  - `runtime_mode='continuous'` 分支
  - `checkpoint_interval` 參數
  - per-iteration loop 含 checkpoint + pause check
  - Mutation operators 真實實作四個 default：`random_perturb` / `column_swap` / `crossover` / `lean_synth`（impl §7.2）
  - Goal 可在 question 註冊客製 operator（Python module 路徑）
  - reproducibility metadata：evaluator_hash + seed
- **Construction `answer_data.type='construction'` 啟用**（v3 §2.2）
  - silver verdict commit：UPDATE G `status='proved'` + `answer_data={type:'construction', witness_lean_path, score, evaluator_hash, generation, seed}` + trust_set computational
  - Library/Constructions/<G>.json 寫入（impl §3.3，type='construction' schema）
- **Silver → Gold 升級 cascade for construction**（v3 §6 cascade、impl §9.4）
  - silver commit 同時 spawn 輔助 Goal `∃X, P(X)` (origin='construction_witness', kind='theorem', derived_from=G)
  - **輔助 Goal statement 構造**：cascade 從 `goals.question.spec_lean_path` parse spec.lean、抓 single main predicate `def`（如 `def IsHadamard4 (M : Matrix ...) : Prop := ...`）、抽出 def name + arg type、自動產 `theorem g_construct_ex : ∃ x : <argtype>, <defname> x := sorry`。**spec.lean 必須有單一 main predicate def**（multi-def case P6 才支援、P5 直接 reject 並 emit alert）
  - **輔助 Goal Strategy 構造**：cascade 在 spawn 時直接寫 leaf Strategy 檔（**不走 Backward**），proof body 候選 list 框架預先定（`['by decide', 'by norm_num', '⟨witness, by decide⟩', 'by Spec.satisfies_proof']`，含 witness substitution）；後續 Builder 一個 Strategy 一個候選試（INSERT 多個 strategy row、Builder 跑 tactic_try-style 順序試）；**全死則 spawn 一個 Backward 對輔助 Goal 走 fallback** 拆解路徑
  - 輔助 Builder 證成功 → cascade 從 derived_from FK 找原 G → 升 gold（answer_data type 'construction' → 'classical', lean_path）
  - Library/Constructions json schema 改寫
- **`derived_from` FK 啟用**（v3 §9.1 goals.derived_from）
  - P2 schema 起就有欄位，P5 才真實寫入 + cascade 用
- **DB schema（啟用 P1 預留）**：
  - `continuous_tasks` table（v3 §9.1）：P1 schema 已建、P5 起真實寫入
  - `construction_attempts` table：P1 schema 已建、P5 起真實寫入
  - `events.kind: task_checkpoint`：P1 schema 預留 enum、P5 啟用
- **Cancellation 白名單擴**（v3 §6 cancellation 段）
  - 加 ConstructionSearch silver 觸發 source：cancel Backward / 其他 ConstructionSearch；Builder 留（升級用）
  - 加 Goal 進 terminal verdict 時對 continuous task 的 SIGTERM + 5s SIGKILL fallback（impl §9.3）
- **Library/Constructions json best-known 同檔覆寫**（v3 §6 Library promotion 段）
  - checkpoint 時若 best_score 改進 → 覆寫 json（無 INSERT library_index，P6 才有 table）
  - **best_known_history 累積保留**（impl §3.3 schema）：json 內 `best_known_history: [{generation, score, ...}, ...]` 紀錄歷代 best——每次改進 append 一行，不丟舊資料。同檔覆寫 = 覆寫 top-level fields（best score / generation）+ append history
  - 對 P4 已建的 Library/Counterexamples/ 行為一致
- **CLI 擴 / 修正**：
  - `--statement` flag 改名 `--spec`（P2/P3/P4 文件已同步追改 demo bash）。`--spec` 統一介面：
    - `kind=theorem|conjecture`：`--spec` 接 statement string
    - `kind=construction`：`--spec` 接 .lean 檔路徑
  - `--statement` 暫保留為 deprecated alias（P6 移除）+ CLI warn 訊息
  - `--print-id`（P5 新）：`goal add` 後 stdout 印 G_id 一行（取代預設 verbose summary，給 `G_ID=$(...)` shell 取值用）
  - `--defer-spec`（P5 新）：`goal add` 預設 validate 檔案存在；加此 flag → skip validation（demo / staged-write 流程用）。配 `asterism goal validate <G_id>` 後續補檢查
  - `asterism task list` 顯示 continuous task lifecycle / generation / best_score
  - `asterism task pause <task_id>` / `asterism task resume <task_id>` / `asterism task kill <task_id>`
- **Construction-specific D_max**：架構 §7.3 說 construction kind 不適用 D_max（depth 永遠 ≤ 1，由 evolution budget 限制壽命），P5 reactor 跳過 D_max check for construction
- **Multi-provider agent runtime backends（gemini / codex 備援）**（架 §8.3、impl §6.5）
  - P2 已建 Provider 抽象 + claude 唯一實作；P5 加 `gemini` / `codex` 兩個 provider 進 `Tooling/agent/providers/`
  - 各 provider 的 scope-isolation 機制對齊（gemini CLI tool scope / codex CLI sandbox + auto-approve only for staging）
  - `agent.fallback_chain` **P5 single chain schema**（簡化）：`[claude, gemini, codex]` 全 stage 共用同一 chain；claude 連 N 次失敗 → 切下一家 retry（prompt 不變、retry 計數歸零）
  - `model_map` per provider：tier 詞彙（haiku / sonnet / opus）→ 各家對應 model id
  - **理由放 P5**：ConstructionSearch.generate 是高頻 agent 呼叫（每代 N 候選），cost 壓力最大；P5 同時上 backend 提供經濟誘因
  - **未來方向**（不在 P5 scope）：spike-019 結果若顯示 per-stage 品質落差大、單 chain 浪費 token，P5.x patch 升 dict-of-list schema（如 `agent.fallback_chain.builder.tactic_llm = [claude, gemini]` 排除某 provider）；P5 不預先做

### Out

- Library promotion 完整（library_index、Library/Theorems/proved.lean）— P6
- Multi-Problem
- Forward / Generalizer / Strategist
- Construction Refuter（impossibility proof 走一般 theorem 路徑，無新 pipeline）
- Counterexample 升 continuous mode（架構保留可能性，但 P5 不做；只有 ConstructionSearch 是 continuous）

## Demo

```bash
asterism init --problem hadamard_4

# Step 1: 注入 Goal、拿到 G_id（用 --defer-spec 跳過 file validation）
G_ID=$(asterism goal add \
  --problem hadamard_4 --slug h4_existence --kind construction \
  --spec Problems/hadamard_4/Goals/_pending/spec.lean \
  --scorer Problems/hadamard_4/scorer.py \
  --defer-spec \
  --print-id)
# --defer-spec：跳過檔案存在 check（demo / staged-write 流程必需）
# 框架自動產 Problems/hadamard_4/Goals/<G_ID>_h4_existence/ 目錄

# Step 2: 寫 spec.lean 進對應 path
cat > Problems/hadamard_4/Goals/${G_ID}_h4_existence/spec.lean <<'EOF'
import Mathlib
def IsHadamard4 (M : Matrix (Fin 4) (Fin 4) (Fin 2)) : Prop :=
  ∀ i j, i ≠ j → (M i ⬝ᵥ M j : Int) = 0  -- 簡化版正交條件
EOF

# Step 3: 寫 Python scorer
cat > Problems/hadamard_4/scorer.py <<'EOF'
def score(matrix_serialized: str) -> float:
    M = parse(matrix_serialized)
    n_violations = count_orthogonality_violations(M)
    return 1.0 - n_violations / 6.0   # 6 = C(4,2) pairs
EOF

# Step 3.5: validate spec / scorer 確實存在（取代 add 時跳過的 check）
asterism goal validate ${G_ID}
# pass → spec.lean 與 scorer.py 都找得到 + spec.lean 含 single main predicate def

# Step 4: 跑
asterism run
# 預期：
#   structural refill 並排：Backward(G_h4) [atomic] + ConstructionSearch(G_h4) [continuous]
#   ConstructionSearch 跑 evolution（每 5 min checkpoint）
#   假設第 30 代產出 score=1.0 的 H → silver commit
#     UPDATE G status=proved/construction
#     寫 Library/Constructions/hadamard_4_h4.json (type='construction')
#     spawn 輔助 Goal ∃M, IsHadamard4 M (origin='construction_witness', derived_from=G_h4)
#     帶 candidate Strategy ⟨H, by decide⟩
#   structural refill 撈到輔助 Goal → Builder
#   Builder 跑 by decide pass → 輔助 Goal proved
#   cascade 找 derived_from FK → 升 G_h4 為 gold
#     UPDATE answer_data type=classical, lean_path=輔助 Goal lean_path
#     Library/Constructions json 改寫 type='classical'
```

## Acceptance criteria

### Milestone A demo gate

0a. **Demo Hadamard 4×4 end-to-end**：上面 §Demo bash（init → goal add --defer-spec → 寫 spec/scorer → goal validate → run）跑完、最終 G_h4.answer_data.type='classical'（silver→gold 升級鏈完成）OR `attempting + best_known`（4h budget evidence_only）。**Milestone A single sanity gate**

### Milestone A 行為

1. **Construction kind dispatch**：`kind=construction` Goal 入池後 30s 內 atomic queue 出現 Backward + continuous queue 出現 ConstructionSearch
2a. **Demo 場景驗 P_c=1 隔離**：預設 `P_continuous=1` 時 1 個 ConstructionSearch 跑、atomic pool 仍可滿載 P=4 個 atomic pipeline（demo Hadamard 跑時驗）
2b. **Stress 驗 P_c=4 並發**：獨立 stress test，4 個 construction Goal + `P_continuous=4` → 4 並發、atomic pool 不受影響（不在 demo 內、放 `tests/stress/test_phase5_continuous_pool.py`）
3. **Checkpoint 寫入**：ConstructionSearch 跑滿 5 min 後 `continuous_tasks.last_checkpoint_at` 更新、construction_attempts 新增 row、若 best_score 改進則 evidence + Library json 同步
4. **Pause / Resume**：跑中的 task 收到 `asterism task pause` → SIGTERM + lifecycle_state='paused' + working dir 保留；resume 後從 checkpoint_state 接續、不重跑既有代
5. **T_pause_max timeout**：手動把 last_checkpoint_at 改回 8 天前 + lifecycle_state='paused' → reactor 30s tick 內偵測 + 自動 killed + 清 working dir
6. **Crash recovery**：跑到一半 hard kill scheduler → 重啟 → 對 lifecycle_state='running' 但無 process 的 task：checkpoint_state 完整 → 自動 resume；殘缺（含 checkpoint_state=NULL 的「首次 checkpoint 前 crash」case）→ **killed + alert，user 需手動 re-add Goal**（對齊 impl §9.3——殘缺 task 自動 resume 不安全、partial state 一致性無保證）
7. **Silver → Gold 升級**：Demo 場景跑通完整鏈，最終 G_h4.answer_data.type='classical'、Library/Constructions json 改寫
8. **derived_from FK cascade**：手動構造 origin='construction_witness' Goal proved + derived_from 指 G → cascade 升原 G 到 gold
9. **Cancellation 對 continuous task**：人為觸發 cascade kill → SIGTERM 5s 後若 process 還在 → SIGKILL；UPDATE lifecycle_state='killed'
10. **Best-known promotion + history**：第 N 代產出比上代高的 score → Library json 同檔覆寫、`best_known_history` append 一行、top-level best 欄位更新；下次 checkpoint 若再改進再 append
11a. **Reproducibility（algorithmic-only operators）**：silver verdict 的 trust_set computational entry 含 evaluator_hash + seed + generation；排除 lean_synth、僅用 `random_perturb` / `column_swap` / `crossover` 重跑同 seed → 達相同 candidate
11b. **Reproducibility metadata（含 lean_synth）**：含 lean_synth 的 silver verdict trust_set 完整紀錄 evaluator_hash + seed + lean_synth model id；**結果不保 deterministic**（LLM 端 jitter）但 metadata 足夠 audit
12. **首次 checkpoint 前 crash → killed**：在 generation < 首檔 checkpoint 之前 hard kill scheduler → 重啟後 lifecycle_state='running' + checkpoint_state=NULL 的 task → recovery scan 標 killed + emit alert（**不 auto-resume from 0**，對齊 impl §9.3）。User 需手動 re-add Goal 重跑

### Milestone B demo gate

0b. **Demo Multi-provider fallback**：跑 P2 級 demo theorem（add_comm_demo 從 P2 複用）、設 `PROVIDER_MOCK_CLAUDE=fail_always` env → 觀察框架自動切 gemini、demo 仍能跑通 → status=proved。**Milestone B single sanity gate**

### Milestone B 行為

13. **Provider fallback chain**：`PROVIDER_MOCK_CLAUDE=fail_after_3` + `PROVIDER_MOCK_GEMINI=fail_after_3` → claude 連 3 次失敗 → 切 gemini → gemini 連 3 次失敗 → 切 codex；任一家成功則 outcome 正常；全失敗 → outcome=exhausted
14. **Provider scope-isolation**：對每個 provider 跑 evil prompt（`PROVIDER_MOCK_<NAME>=evil_write` env hook 強制 agent 在 staging 外 write）→ git status 兜底偵測到、該 stage failed、retry 切下一家

## 依賴

### 前置 phase

- P1–P4 完成

### 必跑 spike

spike 編號接 P4 後（P4 已用至 spike-015；spike 編號集中由 `docs/spikes.md` 配發，避免子編號分裂）。注意 evaluator_hash composition 已 P4 spike-015 涵蓋（construction 共用同 hash 規則），P5 不重複：

- **spike-016 lean_synth mutation operator 可行性**——LLM agent 對「給一個矩陣，產一個變異版」的 prompt response 品質。決定 lean_synth 是否做為 default operator 還是只當 fallback
- **spike-017 Python scorer subprocess sandboxing**——Python `subprocess.run` 加 `resource` limit（CPU / memory / wallclock）的跨平台行為。Windows 上 `resource` module 不可用，需找替代（`psutil` + manual kill）
- **spike-018 Lean type-check 速度 vs candidate 數**——對 4×4 矩陣 candidate `lake env lean <c>.lean`，量級多少（秒數 / 候選）？決定 generation 內 candidate 數上限
- **spike-019 gemini / codex CLI scope-isolation 對齊**——驗證 scope-isolation 機制：
  - gemini CLI 候選 flag：`gemini chat --tool-restrict <whitelist>` 或 `--workspace <staging>`
  - codex CLI 候選 flag：`codex run --sandbox=workspace-write --writable <staging>` 或 `--approval-mode=auto`
  - 驗證手段：evil prompt fixture（agent 嘗試在 staging 外寫檔），看是否真擋下；git status 兜底成本量級（每次 stage 跑 git status 的 wall-clock）
  - 決定 fallback chain 是否需 per-provider 額外驗證層
- **spike-020 per-provider 同 prompt 品質對照**——對 P2/P3/P4 已穩定的 Backward / Builder.tactic_llm / Counterexample agent，餵相同 prompt 比較三家 outcome（pass rate / token / wall-clock）。決定 fallback chain 順序與每家適合的 stage（影響 §風險 是否真的需要升 dict-of-list schema）

## 引入元件

### Pipeline

- **ConstructionSearch**（pipelines.md §7，continuous mode）

### Subsystem 升級

- **Evolution subsystem**：continuous mode + 4 個 default mutation operators（impl §7.2）

### DB schema（啟用 P1 預留）

P1 schema 已建全 schema（codex review #12 決策）。**P5 不擴 schema**——只是開始消費：

- `continuous_tasks` table：P1 schema 已建、P5 起真實寫入
- `construction_attempts` table：P1 schema 已建、P5 起真實寫入
- `pipelines.kind`：'ConstructionSearch' enum value 啟用
- `goals.question`：construction kind 強制 json schema 啟用
- `goals.derived_from`：P5 起真實寫入 + cascade 反向查
- `events.kind`：'task_checkpoint' enum value 啟用

### Tooling 新增

- `Tooling/pipelines/construction_search.py`
- `Tooling/runtime/continuous_pool.py`：第二個 pool dispatch
- `Tooling/runtime/checkpoint.py`：checkpoint 協議實作
- `Tooling/subsystems/evolution_continuous.py`：evolution continuous mode loop
- `Tooling/subsystems/mutation_operators.py`：4 個 default
- `Tooling/sandbox.py`：scorer subprocess + resource limit
- `Tooling/agent/providers/gemini.py`：gemini CLI 包裝
- `Tooling/agent/providers/codex.py`：codex CLI 包裝
- `Tooling/agent/fallback.py`：fallback chain dispatch loop（P2 留空骨架，P5 真實實作）
- 擴 `Tooling/cli.py`：`task` 子命令、`agent test --provider <name>`（手動驗 provider 可用性）、`goal validate <G_id>`（取代 add 時跳過的 file check）

### Test infrastructure

新增 env hook（對齊 P1 `COMMIT_FAULT` 風格、總清單見 `docs/dev/test_hooks.md`）：

- `PROVIDER_MOCK_<NAME>`（multi-env 風格、避免 colon+comma quote 問題）：name ∈ `{CLAUDE, GEMINI, CODEX}`，value ∈ `{fail_after_<N>, fail_always, evil_write}`。例 `PROVIDER_MOCK_CLAUDE=fail_after_3`、`PROVIDER_MOCK_GEMINI=evil_write`

### Cascade table 擴行

- ConstructionSearch silver verdict → spawn 輔助 Goal + cancel Backward / 其他 ConstructionSearch；Builder 留
- 輔助 Goal Builder proved → cascade 升 derived_from G 為 gold（construction → classical）
- 升 gold 不可逆

### Config

| key | P5 預設 |
|---|---|
| `P_continuous` | P/4（P=4 → P_c=1） |
| `T_checkpoint` | 5 min |
| `T_pause_max` | 7 days |
| `construction_atomic_budget_generations` | 100 |
| `construction_continuous_budget_wall_clock_sec` | 14400（4h） |
| `construction_score_plateau_generations` | 20（P5 算出來但 Strategist P7 才消費） |
| `D_max[construction]` | N/A（不適用） |
| `agent.providers` | `[claude, gemini, codex]`（從 P2 的 `[claude]` 擴張） |
| `agent.fallback_chain` | `[claude, gemini, codex]`（依 spike-017c 結果可調序） |
| `agent.model_defaults.construction_search.generate` | haiku |

## 任務序列

P5 兩個 milestone 獨立、明確分段：**Milestone A = ConstructionSearch + continuous runtime**；**Milestone B = Multi-provider backends**。A 完成後可獨立 demo Hadamard；B 是橫向能力升級。

### Milestone A（ConstructionSearch）

DB 端 P5 不需 schema migration（P1 已建全 schema）；任務序列只列實作動作：

1. **spike-016 / 017 / 018 跑完**——結果落 `docs/spikes.md`
2. **Continuous pool**（`Tooling/runtime/continuous_pool.py`）：與 atomic pool 並列、各自 dispatch loop
3. **Checkpoint 協議實作**（`Tooling/runtime/checkpoint.py`）：BEGIN TX → UPDATE checkpoint_state + INSERT events + 可選 evidence_update + 可選 Library json 覆寫（含 best_known_history append）
4. **Crash recovery for continuous task**：scheduler 啟動掃 lifecycle_state='running' / 'paused'；checkpoint_state=NULL 的 running task 標 killed + emit alert（不 auto-resume from 0）
5. **T_pause_max timeout 偵測**：reactor idle tick 內加掃描
6. **Mutation operators**（`Tooling/subsystems/mutation_operators.py`）：4 個 default + 介面
7. **Sandbox**（`Tooling/sandbox.py`）：scorer subprocess + resource limit（Windows 用 psutil fallback per spike-017）
8. **Evolution continuous mode**（`Tooling/subsystems/evolution_continuous.py`）：對齊 impl §7.2 loop
9. **ConstructionSearch pipeline runtime**（`Tooling/pipelines/construction_search.py`）：對齊 pipelines.md §7 stage 序列 + loop 控制
10. **ConstructionSearch agent prompt v1**（`docs/prompts/construction_generate.md`）
11. **structural refill 加 kind=construction dispatch**
12. **Cascade table 擴**：silver commit + 輔助 Goal spawn（含 statement 自動構造 + 候選 leaf Strategy 寫入）+ 升 gold
13. **`derived_from` FK 寫入 + cascade 反向查**
14. **Cancellation 白名單擴 + 對 continuous task SIGTERM/KILL 邏輯**
15. **CLI 擴**：`goal add --spec --scorer --print-id --defer-spec`、`goal validate <G_id>`、`task list/pause/resume/kill`；`--statement` deprecated alias（CLI warn）
16. **Demo Hadamard 4×4 跑通 + Milestone A acceptance test（含 #0a single sanity gate）**

### Milestone B（Multi-provider）

17. **spike-019 / 020 跑完**
18. **gemini provider**（`Tooling/agent/providers/gemini.py`）：CLI 呼叫 + tool scope 限制 + git status 兜底
19. **codex provider**（`Tooling/agent/providers/codex.py`）：CLI 呼叫 + sandbox + git status 兜底
20. **Fallback chain dispatch**（`Tooling/agent/fallback.py`）：依 impl §6.5 流程，P2 的單 provider 改成 chain loop（P5 single chain schema、未來方向 dict-of-list 留 P5.x patch）
21. **`PROVIDER_MOCK_<NAME>` env hook**（test-only）：multi-env 風格、避免 quote 問題
22. **CLI `agent test --provider <name>`**：手動驗 provider 可用性
23. **Demo Multi-provider fallback 跑通 + Milestone B acceptance test（含 #0b single sanity gate）**：跑 P2 級 demo theorem 配 `PROVIDER_MOCK_CLAUDE=fail_always`、驗自動切 gemini 完成

## 測試

- **Unit**：Mutation operators 對輸入 candidate 的不變量（如 column_swap 後仍是矩陣形）
- **Unit**：Sandbox 對超 CPU / memory / timeout 各 case 正確 kill
- **Unit**：Checkpoint 協議對 BEGIN TX 失敗 / 寫入中斷 各 case
- **Unit**：Cascade silver→gold derived_from 路徑
- **Integration**：Hadamard 4×4 demo end-to-end（wall-clock 上限取決於 evolution 收斂速度——4 hour budget 內若收斂則 silver+gold；不收斂則 evidence_only。pytest assertion 不寫死 wall-clock，只 assert `final_status ∈ {proved/classical, attempting+best_known}`）
- **Integration**：pause / resume 後對齊 checkpoint_state
- **Integration**：crash recovery for continuous task（kill scheduler mid-task → resume 接續）
- **Integration**：T_pause_max timeout
- **Stress**：4 個 construction Goal 並發（`P_continuous=4` config override，對齊 acceptance #2b），atomic pool 同時跑 Backward / Builder 不互相干擾；放 `tests/stress/test_phase5_continuous_pool.py`

## 風險與 open questions

- **Lean type-check 慢拖累 evolution**：spike-016 結果若顯示單 candidate type-check > 30s，每代 N 候選 = N×30s，evolution 速度太慢。應變：candidate 寫成「裸資料 + decide proof body」省 Lean 推導；或 batch type-check（一次 lake build 多檔案）
- **scorer Python sandboxing 在 Windows 弱**：spike-015 結果若 Windows 限不了 memory，hadamard demo 跑大矩陣可能 OOM。應變：CLI flag `--unsafe-scorer` 預設關、Linux 上跑生產用例
- **lean_synth operator 是 LLM call**：跑代多時很貴。應變：Strategist signal「token 使用率高」加 cost cap；或 lean_synth 預設 disabled by default、Goal 顯式 opt-in
- **derived_from FK cascade 與 silver→gold 不可逆**：要嚴格驗單向。p4 已驗 refuted classical→witness 拒絕；p5 補對 proved 同樣處理
- **continuous task working dir 跟 atomic staging 路徑命名衝突**：v3 §9.2 已分（Staging/<p_uuid>/ vs Tasks/<task_uuid>/），但 P5 才真實寫入。要驗無衝突
- **Best-known promotion 同檔覆寫的併發**：兩個 ConstructionSearch task 對不同 Goal 同時改進 → 各寫各的 json 不衝突；但 reactor cycle 處理 task_checkpoint event 順序 vs 實際寫入順序可能不一致 → 不影響正確性，只影響 dashboard 看到的中間狀態
- **`P_continuous=1` 時可能 starve**：P=4 → P_c=1，多個 construction Goal 排隊。P5 內可能感受不深，P6 multi-Problem 後會更明顯。應變：P_continuous tunable + Strategist signal 偵測 starvation（P7）
- **Builder 對輔助 Goal 的 by decide 對大矩陣可能 timeout**：4×4 還好，10×10 以上 by decide 爆炸。應變：輔助 Goal 帶多個候選 proof body（`by decide` / `by norm_num` / `by Spec.satisfies_proof`），Builder tactic_try 試
- **首次 checkpoint 前 crash → killed**：generation 1 至首次 checkpoint（T_checkpoint=5 min 或 best_score 改進）之間 hard kill scheduler → 重啟後 lifecycle_state='running' + checkpoint_state=NULL → recovery scan 標 killed + emit alert（**不 auto-resume from 0**，partial state 一致性無保證）。User 需手動 `asterism goal add` 重 spawn task。Acceptable trade-off：首檔 checkpoint 通常 5 min 內、代數損失上限可接受。應變：T_checkpoint 縮短會增 IO overhead，按實際跑 hadamard / cap_set 調
- **gemini / codex CLI scope-isolation 不對齊**：spike-019 結果若顯示某家 CLI 沒有等價 `--add-dir`、純靠 git status 兜底，agent 寫破壞性檔案後才發現會浪費整 stage retry。應變：該 provider 排在 fallback chain 末位、或乾脆從 chain 移除直到 CLI 成熟
- **git status 兜底成本過高**：spike-019 順帶量「每次 agent stage 結束跑 git status」的 wall-clock。若 > 1s（大 repo）→ demo wall-clock 受拖累。應變：(a) fallback 到「git stash before agent / git stash pop after」較粗暴的 isolation（agent 寫的 staging 外檔被 stash 掉、復原乾淨）；(b) 用 sparse checkout 縮小 git working tree；(c) 改用 inotify/FSEvents watch staging 以外路徑、agent 結束時直接看 events 列表
- **Per-provider prompt 品質落差**：spike-020 結果若顯示某家對某 stage 品質明顯差（pass rate < 50%），fallback 切過去 ≈ 浪費。應變：把 fallback chain 按 stage 分（dict-of-list schema、§In 「未來方向」段已寫）；P5.x patch 升級
- **Token 量級爆炸**：三 provider 同時 active 時，fallback 觸發前先付 N_retry × claude 的 token，再付 N_retry × gemini，最後 codex——最壞 case token = 3N。應變：fallback 計數沿用「整 stage 共用 N_retry」而非 per-provider，總 retry 數固定（即首家用 5、第二家剩 5、第三家無）。spike-020 順帶決定數值
- **Provider model_map 維護**：各家 model id 升級頻繁（claude-haiku-4-5、gemini-2.0-flash 等），map 過期 → CLI 直接報錯。應變：CLI 加 `asterism agent models list` 顯示當前 map、人類定期審視更新
