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
| P3 | `SEARCH_MOCK` | `record_calls` / `force_miss` / `force_hit` | search subsystem 行為控制（cache acceptance 計次 / 強制 cache miss-hit 路徑） |
| P3 | `BACKWARD_FORCE` | `exhausted` / `unproductive` / `succeed` | Backward pipeline 強制走特定 outcome（給通用 N=5 trigger acceptance 用） |
| P4 | `COUNTEREXAMPLE_FORCE` | `silver` / `evidence_only` / `unproductive` | Counterexample 強制走特定 outcome（給 silver-skip race acceptance 用） |
| P4 | `CASCADE_FAULT` | `unique_violation` / `dual_proved` / `fk_invalid` | 強制 cascade SQL 失敗（給 fatal halt acceptance 用） |
| P4 | `REFUTER_FAST_PATH` | boolean | 模擬 Refuter→Builder 鏈快速通過（給 race acceptance #6 用） |
| P5 | `PROVIDER_MOCK_<NAME>` | `fail_after_<N>` / `fail_always` / `evil_write` | Provider 強制失敗 / scope-isolation 違規。**multi-env 風格、避免 colon+comma quote 問題**——例：`PROVIDER_MOCK_CLAUDE=fail_after_3 PROVIDER_MOCK_GEMINI=evil_write asterism run`；name ∈ {CLAUDE, GEMINI, CODEX} |
| P6 | `LIBRARY_BUILD_FAULT` | `1` / `0` | 強制 lake build Library 回 fail（給 promotion revert acceptance 用） |
| P6 | `--bypass-startup-check`（CLI flag、非 env hook）| flag | scheduler 啟動跳過 CLI 早期 single-instance 攔截、讓進到 liveness check 階段；liveness check 仍正常擋。給 acceptance #10 驗 liveness check 真有效 |

## P7 fixture CLI（不是 env hook）

P7 的 `asterism fixture <name>` 是 CLI 介面，非 env hook（fixture 是「注入預設 DB 狀態」、非「攔截行為」）。仍列於此檔以方便整體 test infrastructure 索引：

| Phase | Fixture | 用途 |
|---|---|---|
| P7 | `ih_trap` | 注入已 unproductive 兩次 + similarity ≥ threshold 的 Goal |
| P7 | `silver_stuck` | 注入 silver/witness 但無 active Refuter 的 Goal |
| P7 | `construction_plateau` | 注入連 20 代 best_score 不變的 ConstructionSearch task |
| P7 | `blocked_backward` | 注入 blocked_pipelines=['Backward'] 的 Goal |
