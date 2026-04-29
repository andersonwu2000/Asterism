# Test hooks 總清單

跨 phase test-only env hook 集中追蹤。每加新 hook → 更新本檔 + 該 phase 文件 §引入元件 §Test infrastructure 段。

命名慣例：`*_FAULT=mode`（強制模擬失敗）或 `*_MOCK=spec`（替換真實行為）或 `*_FORCE=value`（強制走特定 outcome）。

## 規則

- **只在 pytest / debug 路徑用**：prod 環境 env 不設、零 overhead
- **語意凍結**：一旦 hook release，後續 phase 不得改其行為（避免回頭 break 既有 test）
- **collision 防範**：新 hook 加入前 grep 全 phase 文件確認名稱不衝突
- 各 phase 文件 §引入元件 §Test infrastructure 段列本 phase 新增 hook + 用途；本檔保持總清單

## Hook 清單

| Phase | Env hook | Mode / value | 用途 |
|---|---|---|---|
| P1 | `COMMIT_FAULT` | `after_step1` / `after_step2` / `after_step3` | CommitWriter 在指定 step 後 raise，給 recovery scan acceptance 用 |
| P1 | `LAKE_MOCK` | `proved` / `sorry` | run_lean 入口跳過真實 `lake env lean --json`、直接返 LakeResult；給 AC#0 subprocess test + CI 不需 lean toolchain 用 |
| P2 | `PRINT_AXIOMS_MOCK` | `none` / `<axiom>,<axiom>...` | trust.print_axioms 跳過真實 `lake env lean -e '#print axioms ...'`、直接返指定 axiom name list；給 unit test + CI 不需 lean toolchain 用 |
| P2 | `BACKWARD_MOCK` | `success_leaf` | Backward.run 入口替換真實 agent；寫 trivial leaf strategy `theorem ... := by sorry` + INSERT strategies row。配合 LAKE_MOCK=proved 給 AC#0 demo subprocess test 跑 init→spec→run→show 端到端 |
| P2 | `BACKWARD_FORCE` | `exhausted` / `unproductive` | Backward pipeline 強制走特定 outcome（C18 引入；語意凍結） |
| P3 | `SEARCH_MOCK` | `record_calls` / `force_miss` / `force_hit` | search subsystem 行為控制（cache acceptance 計次 / 強制 cache miss-hit 路徑） |
| P3 | `DEDUPE_MOCK` | `force_hit` / `force_miss` / `force_timeout` | dedupe subsystem 行為控制（C20 引入；`force_hit` 回 entry list 第一筆 id；`force_miss` 回 NOVEL；`force_timeout` 回 timeout outcome）。bypass cache + subprocess |
| P3 | `BACKWARD_FORCE` | `succeed` (extended) | P2 `BACKWARD_FORCE` 擴 `succeed` 值；用於通用 N=5 trigger acceptance（與 `BACKWARD_MOCK=success_leaf` 不同：force succeed 不寫 strategy row，只回 outcome=success 殼；test 自己造 fixture rows） |
| P4 | `REFUTER_MOCK` | `success_negation` | Refuter.run 入口替換真實 agent；INSERT 一筆 ¬G goal (origin='refuter_negation') + 雙向 twin_of UPDATE + 寫 placeholder .lean。給 acceptance #1 三線並排 enqueue 驗 / 任何不需 agent 真跑的 Refuter 上游 wiring 測試（C29 引入；語意凍結） |
| P4 | `REFUTER_FORCE` | `exhausted` / `succeed` | Refuter pipeline 強制走特定 outcome（與 `REFUTER_MOCK=success_negation` 不同：force succeed 不寫 ¬G goal、只回 outcome=success 殼；test fixture 自管 rows）。C29 引入；語意凍結 |
| P4 | `COUNTEREXAMPLE_FORCE` | `silver` / `evidence_only` / `unproductive` | Counterexample 強制走特定 outcome（給 silver-skip race acceptance 用）—— **延後**（Counterexample 整段延後、見 task.md ## 延後 cycles） |
| P4 | `CASCADE_FAULT` | `unique_violation` / `dual_proved` / `fk_invalid` | 強制 cascade SQL 失敗（給 fatal halt acceptance 用） |
| P4 | `REFUTER_FAST_PATH` | boolean | 模擬 Refuter→Builder 鏈快速通過（給 race acceptance #6 用）—— C29 reserve 名稱、實作 C30 cascade 上線連帶 |
| P5 | `PROVIDER_MOCK_<NAME>` | `fail_after_<N>` / `fail_always` / `evil_write` | Provider 強制失敗 / scope-isolation 違規。**multi-env 風格、避免 colon+comma quote 問題**——例：`PROVIDER_MOCK_CLAUDE=fail_after_3 PROVIDER_MOCK_GEMINI=evil_write asterism run`；name ∈ {CLAUDE, GEMINI, CODEX} |
| P6 | `LIBRARY_BUILD_FAULT` | `1` / `0` | 強制 lake build Library 回 fail（給 promotion revert acceptance 用） |
| P6 | `--bypass-startup-check`（CLI flag、非 env hook）| flag | scheduler 啟動跳過 CLI 早期 single-instance 攔截、讓進到 liveness check 階段；liveness check 仍正常擋。給 acceptance #10 驗 liveness check 真有效 |
| P7 | `STRATEGIST_FORCE` | `exhausted` / `empty` | Strategist.run() 強制走特定 outcome、不呼叫 agent；給 demux/round_robin acceptance 用 |
| P7 | `FORWARD_FORCE` | `exhausted` / `no_novel` | Forward.run() 強制 outcome（未走 self_verify / dedupe）；給 cascade integration test 用 |
| P7 | `GENERALIZER_FORCE` | `exhausted` / `no_novel` / `unproductive` | Generalizer.run() 強制 outcome；同上 |
| P7 | `STRATEGIST_DISABLED` | `1` | scheduler step 5 trigger 整段跳過、不 enqueue Strategist 任務；給 D-baseline 對照 demo + 演習選擇性關 Strategist 用 |
| P7 | `K_STRATEGIST` | int (預設 8) | 覆寫 round_robin K 閾值；給 acceptance test 用較小 K 加速 |
| P7 | `STRATEGIST_STALE_SEC` | int (預設 4h) | 覆寫 is_strategist_running 認定 stale 的 cutoff；給 acceptance test 模擬 stale running row 不需等真實 4h |
| ops | `ASTERISM_POOL_SIZE` | int (預設 4) | 覆寫 ReactorConfig.pool_size — `asterism run` daemon/--once atomic pool 上限。演習 / token-cheap-time-expensive 場景開大（user 建議 12~15）|
| P7 | `ASTERISM_NOW` | ISO8601 timestamp | 強制 `cancel_running_for_goal` 寫入指定 finished_at 而非 wall-clock now；給 demux Shelve cancel test 確定性比對用 |

## P7 fixture CLI（不是 env hook）

P7 的 `asterism fixture <name>` 是 CLI 介面，非 env hook（fixture 是「注入預設 DB 狀態」、非「攔截行為」）。仍列於此檔以方便整體 test infrastructure 索引：

| Phase | Fixture | 用途 |
|---|---|---|
| P7 | `ih_trap` | 注入已 unproductive 兩次 + similarity ≥ threshold 的 Goal |
| P7 | `silver_stuck` | 注入 silver/witness 但無 active Refuter 的 Goal |
| P7 | `construction_plateau` | 注入連 20 代 best_score 不變的 ConstructionSearch task |
| P7 | `blocked_backward` | 注入 blocked_pipelines=['Backward'] 的 Goal |
