# Phase 1 — Skeleton

## 目標

把 Asterism 的「最小可跑迴路」打通：DB schema、commit 協議、Lake/Lean 子程序呼叫、Builder pipeline（無 agent 版）。
Phase 結束時，使用者可以手寫一個 .lean 檔加 leaf Strategy proof body，CLI 餵進去，框架跑 Builder 把它驗證並 cascade 出 `proved`。
**不**碰任何 LLM、不拆解 Goal、不跨 Goal cascade。純粹驗證 infra 的骨架對齊。

## Scope

### In

- **DB schema 一次列 v3 §9.1 全欄位**（codex review #12 決策）：未用欄位 nullable 留空，無後續 ALTER TABLE migration。十一個 table（goals / strategies / strategy_subgoals / pipelines / dead_attempts / queue / events / schedulers / continuous_tasks / construction_attempts / library_index / search_cache / strategist_decisions）schema 全建；P1 runtime 只消費前 8 個
- `commit_state` + `prior_state_snapshot` 兩段式 commit 協議（架 v3 §5）
- Recovery scan 完整版（impl §1.3）：掃 `goals` + `strategies` 兩表所有 `commit_state='pending'` row
- Lake harness：subprocess 呼叫 `lake env lean <file>` / `lake build <target>`、stdout/stderr 解析（含 sorry detection 走 spike-003 規範）、timeout
- **Builder pipeline 簡化版**：stages = `tactic_try` (pure) → `commit`。tactic_try 內部 single-tactic loop——每試一個 tactic 就寫 staging .lean 跑 `lake env lean` 驗（pass 即停、進 commit；fail → 試下一 tactic；全試完 → outcome=`exhausted`）。**self_verify 不獨立列為 stage**——tactic_try 內已 try-and-verify 合一（單 tactic 試完馬上 lake 驗）。**P2 引入 tactic_llm agent stage 後，self_verify 抽獨立 stage**（agent 寫整段 proof 後一次性 lake 驗、不能塞進 tactic_try loop）
- Atomic pipeline 用 `T_wall` 整條 timeout（config 注入、pytest 用 `T_wall=2s` 跑）；無 retry pattern（P1 沒 agent stage，沒 retry target stage 可餵錯訊息回去）
- 單檔 staging 流程（`Goals/<G>/Staging/<p_uuid>/`）
- CLI：
  - `asterism init --problem example` 建空 Problem（產 META.md / Defs.lean / Root.lean 範本）
  - `asterism goal add --problem example --slug add_zero --kind theorem --leaf-strategy <file>` 注入 root Goal + 同檔 leaf Strategy
    - `--leaf-strategy` flag 標 **testing-only**：P2 起 Backward 自動產 leaf Strategy，此 flag 移除（CLI help 明示）
  - `asterism run --once`（P1 預設）：拿 queue 一個 task → spawn Builder → 跑完 exit；`--daemon` flag 預留（P1 行為等同 `--once`、P2+ 才接 event_bus block）
  - `asterism db recover` 手動觸發 recovery scan
  - `asterism goal show <G_id>` 顯示 status / answer_data / lean_path
- 最簡 reactor cascade：單規則 `strategies.status='succeeded'` → 父 Goal `status='proved'`、寫 `answer_data={type:'classical', lean_path}`。**不寫 Library promotion code path**（codex #4 選 b：P6 在 cascade dispatch table 補 entry，不是改 if-else）
- `events.kind` enum 含 `pipeline_finished` / `cascade` / `fatal`——cascade SQL fail（unique constraint / FK / json 格式錯）→ emit `fatal` event + scheduler halt + 保留現場（架構 §6 step 3 失敗處理）
- File layout 對齊架 §9.2 的 `Asterism/asterism.db` + `Problems/<n>/{META.md, Root.lean, Defs.lean, Goals/<G>/...}`
- **Fault injection hook**（codex #6）：CommitWriter 讀 `COMMIT_FAULT=after_step1|after_step2|...` env var，每個 step 之間檢查並 raise，給 pytest reproducible kill；prod 路徑 env var 不設、零 overhead

### Out

- 任何 agent 呼叫（claude CLI 等待 P2）
- Backward / Refuter / Forward / Generalizer / Counterexample / ConstructionSearch / Strategist
- **Structural refill BFS**——P1 用 hard-coded enqueue：`asterism goal add` 直接寫 queue row，`asterism run` pop 一個就 exit。**這隱含防無限 retry**（exhausted Goal 沒人重派；要再試只能人類手動 add 同 Goal 一次）。**P2 引入 BFS structural refill 後此防線消失**——P2 必須補 hard-coded retry cap 兜底（per-Goal 累計 N 次跳過），正式 `blocked_pipelines` 機制留 P3
- Multi-Problem
- Library promotion（`Library/Theorems/proved.lean` 不寫；對應 cascade rule 在 P6 加進 dispatch table）
- Trust set 構造（P1 不跑 `#print axioms`，trust_set column 留 NULL；cascade 規則 §6 「proved + classical + root + trust_set 通過 Library.whitelist」自然 short-circuit fail，符合不 promote 期望）
- Search / Dedupe subsystem
- Cancellation propagation
- continuous task runtime
- 任何 cascade rule 牽涉 silver/gold、twin、`derived_from`、Library promotion
- IH-trap 偵測
- Provider 抽象（P2 才接 agent stage 才需要）
- Atomic pipeline retry pattern（架 §5「失敗訊息透過 context 餵回指定 retry target stage」是 agent stage 機制；P1 沒 agent stage 不適用）

## Demo

```bash
asterism init --problem example
# 產出 Problems/example/{META.md, Root.lean, Defs.lean}
# META.md 含 axioms 三公理範本

# 人類手寫 leaf Strategy 證明檔
cat > /tmp/strat.lean <<'EOF'
import Mathlib
theorem add_zero_simple (n : Nat) : n + 0 = n := by simp
EOF

asterism goal add \
  --problem example \
  --slug add_zero_simple \
  --kind theorem \
  --leaf-strategy /tmp/strat.lean
# (--leaf-strategy 是 P1 testing-only flag，P2 移除)

asterism run --once
# 預期 stdout：
#   spawn Builder for strategies.id=1 (Goal G_root)
#   Builder: tactic_try simp → pass
#   commit succeeded
#   cascade: G_root status proved
#   reactor exit (--once)

asterism goal show G_root
# 預期：status=proved, answer_data={"type":"classical","lean_path":"..."}
```

## Acceptance criteria

0. **Demo bash 一條龍 pass**——上面 §Demo 整段 bash 從 `init` 到 `goal show` 跑完、最後 status=proved。**這是 phase 完成的 single sanity gate**
1. **SQL schema 完整**：`sqlite3 asterism.db ".schema"` 列出 v3 §9.1 所有 table 與欄位（含 P1 不消費的 `continuous_tasks` / `library_index` 等），未用欄位 nullable
2. **Commit recovery（INSERT / strategies）**：用 `COMMIT_FAULT=after_step1` 跑 Builder commit 中斷 → 重啟 `asterism db recover` → strategies row 自動 DELETE、staging dir 清掉
3. **Commit recovery（INSERT / goals）**：用 `COMMIT_FAULT=after_step1` 跑 `asterism goal add` 中斷 → 重啟 recover → goals row 自動 DELETE、staging dir 清掉（驗 recovery 同時蓋 goals + strategies 兩表）
4. **Commit recovery（UPDATE / strategies）**：手動把 strategies row 設 commit_state='pending' + prior_state_snapshot 寫入舊 status，跑 recover → row 還原舊 status、staging 清掉
5. **Commit recovery（mv 後 kill）**：`COMMIT_FAULT=after_step2` 跑 → row 仍 pending、staging 已 mv → recover 偵測 lean_path hash 等於 source、idempotent skip mv → finalize → 變 live
6. **Lake 整合（pass）**：`asterism run --once` 對含 `by simp` 的 leaf Strategy 跑通、status=proved
7. **Lake 整合（sorry 偵測）**：對含 `sorry` 的 leaf Strategy 跑 → outcome=`exhausted`、寫 dead_attempts。**sorry detection 走 spike-003 規範的解析規則**（lake env lean 對 sorry exit code 通常 0 + warning，要解析 stdout/stderr）
8. **T_wall timeout**：用 `T_wall=2s` config + 注入慢 lake build → 2s 後 pipeline 直接 outcome=`exhausted`、寫 dead_attempts；驗無 retry loop
9. **CLI 串完**：`init → goal add → run → goal show` 一條龍跑得通，不需手動編 SQL
10. **idempotent**：對同一 Goal 重跑 `asterism run --once` 兩次，第二次 reactor pop queue empty → 直接 exit、無重複 commit
11. **Cascade fatal halt**：人為 inject 重複 lean_path 觸發 unique constraint → cascade emit `fatal` event + scheduler halt（exit code 非 0）+ working dir 保留 + DB 現場保留

## 依賴

### 前置 phase

無（這是第一個 phase）

### 必跑 spike

P1 開工前必跑（屬 `docs/spikes.md`）：

- **spike-001 lake env lean 並發**——多 subprocess 同時跑 `lake env lean` 是否會撞 lake cache lock？影響 P1 的全域 BUILD_LOCK 是否需要（**contingency**：若顯示 lake 完全無法並發 → P3+ 必須走 daemon 化 Lean executable + IPC，重排 P3 範圍與工期）
- **spike-002 Mathlib 三公理 audit**——Mathlib 哪些常用 namespace（`Nat`、`Mathlib.Algebra.Group.Basic` 等）的 lemma 走 #print axioms 真的只落在 `propext / Quot.sound / Classical.choice`？影響 P1 demo 用的 theorem 範本
- **spike-003 lake env lean error 解析**——type error / sorry remaining / timeout 三種失敗的 stdout/stderr 格式長怎樣？影響 Lake harness 的 parser、acceptance #7 的 sorry detection 規則

## 引入元件

### Pipeline

- **Builder（簡化版）**：stages = `tactic_try` (pure) + `commit`。`tactic_try` 內部 hardcoded list `[rfl, simp, decide, norm_num, ring]` 逐項替換 staging .lean 的 proof body 並跑 `lake env lean`，命中即 pass。`failure_replay` / `find_lemmas` / `tactic_llm` / `self_verify` 在 P1 都**不執行**（pipelines.md §1 的 `[pass → success]` 隱含 self_verify 已被 tactic_try 覆蓋）。Outcome 只有 `proved` / `exhausted`

### DB table（一次列 v3 §9.1 全欄位、未用欄位 nullable）

P1 runtime 消費的 table：

- `goals`：所有 v3 §9.1 欄位；P1 寫入 id / problem / slug / lean_path / statement_hash / origin / kind / status / answer_data / commit_state / prior_state_snapshot / created_at / updated_at；其餘（twin_of / derived_from / trust_set / depth / blocked_pipelines / status_changed_at / question / evidence）nullable 留 P2+ 寫入
- `strategies`：所有 v3 §9.1 欄位；P1 寫 id / goal_id / lean_path / status / commit_state / prior_state_snapshot / created_by / created_at；`parent_subgoal_max_similarity` / `session_id` nullable 留空
- `strategy_subgoals`：完整 schema（P1 用不到 multi-row，但 schema 在）
- `pipelines`：所有欄位；P1 寫 id / kind / runtime / target_id / target_kind / status / outcome / started_at / finished_at；`session_id` nullable 留空（**P1 schema 預留但 runtime 不消費**）
- `dead_attempts`：完整（P1 用得到，failure recording）
- `queue`：完整（P1 簡化版只放 Builder task）
- `events`：kind enum 含 `pipeline_finished` / `cascade` / `fatal`
- `schedulers`：完整 schema（**P1 schema 預留但 runtime 不消費**——P1 單實例不需 liveness check；P6 才啟用）

P1 schema 建好但 runtime 不寫的 table（**預留欄位 / 表，不消費**）：

- `continuous_tasks`、`construction_attempts`：P5 才用
- `library_index`：P6 才用
- `search_cache`：P3 才用
- `strategist_decisions`：P7 才用

### Config

框架 config 檔（Python module 或 toml）：

| key | P1 預設 |
|---|---|
| `T_wall` | 30 min（pytest 注入 2s） |
| `P` (atomic pool) | 1（P1 不需要並發） |
| lake subprocess timeout | 600s |
| `COMMIT_FAULT` env | 未設（fault injection 關閉） |

**P1 不啟用** `N_retry`（無 retry pattern，agent stage 才有；config 留 P2 起填值）。

### File layout

```
Asterism/
├── asterism.db
├── Tooling/                # CLI + runtime + tests
└── Problems/
    └── example/
        ├── META.md
        ├── Root.lean
        ├── Defs.lean
        └── Goals/
            └── <G_id>_<slug>/
                ├── <slug>.lean
                ├── Strategies/<S_id>_<slug>.lean
                └── Staging/<p_uuid>/
                    ├── context.json
                    └── *.lean
```

## 任務序列

1. **spike-001 / 002 / 003 跑完**——結果落 `docs/spikes.md`
2. **首日決策確認**：
   - schema 走 codex #12 的 (a) 路：一次列 v3 §9.1 全欄位
   - CLI 介面凍結：`--problem` flag、`--leaf-strategy` 標 testing-only、`--once` / `--daemon` 雙 flag forward-compat
   - spike-001 contingency 不踩到 → P3+ 維持原計畫
3. **Lake harness**（`Tooling/lake.py`）：subprocess 呼叫、stdout/stderr parse（依 spike-003，含 sorry detection 規則）、timeout、若 spike-001 顯示需鎖則加全域 `threading.Lock`
4. **DB schema migration v1**（`Tooling/db/schema_v1.sql`）：v3 §9.1 全 table 一次建好
5. **CommitWriter**（`Tooling/commit.py`）：4 個操作 `begin(insert)` / `begin(update)` / `stage_file` / `finalize` + `begin_batch`（跨 row TX）+ `recover_scan` + `COMMIT_FAULT` env hook，行為對齊 impl §1
6. **Builder runtime**（`Tooling/pipelines/builder.py`）：tactic_try（hardcoded list 試）+ commit（呼 CommitWriter UPDATE strategies）+ outcome dispatch + T_wall enforcement
7. **Reactor 雛型**（`Tooling/scheduler.py`）：
   - 啟動時呼 recover_scan
   - 從 queue table pop 一個 task → spawn Builder（單執行緒同步跑，P1 不需 thread pool）
   - Builder 完成 emit pipeline_finished → cascade（單規則：strategies.succeeded → 父 Goal proved + answer_data；無 Library promotion path）
   - cascade SQL fail → emit `fatal` event + halt（exit non-zero）
   - queue 空 → exit
8. **CLI**（`Tooling/cli.py`）：`init --problem` / `goal add --problem ... --leaf-strategy` / `run --once` / `db recover` / `goal show`
9. **Demo theorem**：手寫 `Problems/example/Goals/<G>/.../leaf_strat.lean` 含 `by simp` proof，跑通整條 demo
10. **Acceptance test 寫成 pytest**（`Tooling/tests/test_phase1_*.py`），加進 CI；`COMMIT_FAULT` env 串接 fixture

## 測試

- **Unit**：CommitWriter 的 6 個 recovery 子 case（interrupt at step 1/2/3 × INSERT/UPDATE）走 `COMMIT_FAULT` env
- **Unit**：Lake harness 對 simp pass / type error / sorry / timeout 四 case（sorry case 對齊 spike-003）
- **Unit**：Cascade fatal halt 對 unique constraint / FK fail 各 case
- **Integration**：Demo 場景 end-to-end pytest fixture（清 DB → init Problem → add Goal → run --once → assert status=proved）
- **Integration**：T_wall=2s + 慢 lake → exhausted（acceptance #8）
- **Manual**：人為 kill -9 在不同 step 觀察 recovery 是否乾淨（與 `COMMIT_FAULT` 對照）

## 風險與 open questions

- **Lake build cache lock**：spike-001 結果決定是否需全域 lock。**Contingency**：若 spike-001 顯示 lake 完全無法並發（彼此干擾、SQL-style cache lock 撞死）→ P3+ 必須走 daemon 化 Lean executable + IPC 路徑（成本大、重排 P3+ 工期、可能改變 P3 cache subsystem 的設計切點）。P1 本身不受影響（P=1）
- **subprocess lifecycle on Windows**：使用者環境是 Windows 11 + bash（Git Bash？）。Lake / Lean 是否有 Windows-specific 行為（路徑大小寫 / line ending）？P1 開工首日先驗
- **Sorry detection 易脆**：lake env lean 對 sorry 通常 exit 0 + warning，靠 stdout/stderr keyword 判斷。spike-003 規則必須涵蓋多 Lean 版本格式差異；prod 用 `lake env lean --json` 若可用會更穩
- **`tactic_try` 沒 self_verify 是否真的安全**：Builder 簡化版省 self_verify 的前提是「tactic_try 跑 lake env lean、pass 等於 type-check 通過」。若 tactic 寫進 staging 但 lake 對該檔有 cache 命中（沒真的重 elab）會誤判 pass——spike-001 順帶驗
- **`--leaf-strategy` 是 P1 必要 hack**：P1 沒 Backward 不能拆解，user 必須手動提供 leaf Strategy。P2 起 Backward 自動產 leaf Strategy 後此 flag 死掉、CLI help 明示 testing-only。Acceptance #0 demo 用此 flag 但接受「P2 移除」的事實
- **`asterism run --once` vs `--daemon` 雙 flag**：P1 兩個 flag 行為等同（都 exit-after-empty-queue），但 CLI 介面凍結 forward-compat——P2 改 `--daemon` 真實 daemon、`--once` 維持 P1 行為，user 寫 cron / CI 時用對 flag 就無 breaking change
- **Cascade fatal halt 對 P1 的觸發頻率**：P1 cascade 規則只有一條（strategies.succeeded → goal proved），SQL fail 機率低（除非人為 inject）。但 P1 就建 `fatal` event + halt 機制，避免 P2+ 加更多 cascade 規則時臨時補機制慌
