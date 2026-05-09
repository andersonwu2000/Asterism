# Asterism v2 — Current Status

更新於 **2026-05-10**、HEAD `87370bb`、**642 unit tests green / 1 skipped**。

## 下個 session 接手要做的事

**SG run #5（首次帶完整 decline directives 系統 + 累計修法跑）**：
- 配置：`pool=15, W=3, sonnet, budget 4hr30min, shelve=5, spawn_timeout=900`
- 起跑流程：`cli reset sylvester_gallai && rm -rf Problems/sylvester_gallai/.attempts/ && cli init sylvester_gallai && cli run`
- 監看 cadence：每 20 min 檢查 `/health`、`/health.acquires.hot_rate`、`goals-by-status`、最新 cascade events、`.asterism/logs/gateway.log`

**這次 run 主要驗證點**（按重要序）：

1. **decline directive 各條使用情況**：agent 用 `unprovable` / `return_to_parent` / `shelve` / `needs_decomposition` 的分布、特別是 `return_to_parent` 是否觸發 + parent 是否真的「保留 shape 補 hypothesis」
2. **leaf-bypass axiom probe at acceptance**：commit `968e4e7` 上次 run 沒驗（commit 在 daemon 啟動後）；本次 run 期待 sorryAx 偽證在接受階段就被擋、不再進 verify 階段觸發 race
3. **race fix 持續穩定**：`5bded83` 的 has_live guard、上 run 觸發 ≥3 次都正確處理
4. **rescue prompt 三選項繼續工作**：上 run 救援成功率 8/14 = 57%，看本 run 是否再升

**異常觸發 cut**：gateway crash loop、`hot_rate < 30%` 持續、`agent_rc_nonzero` 連續 burst、`shelved%` > 50%。

跑完後待做：commit 中記 baseline（wall / proved / shelved / agent_infeasible 數 / parent_needs_fix 數）；對比 SG run #4（270min wall, 4 proved, 5 shelved, 0 parent_needs_fix）。

## 2026-05-09 ~ 05-10 session 落地

### Decline directives 統合系統（commits `dd3e905..87370bb`）

把分散的 `decline:` directive 收斂成 4-token 詞彙、跨 Builder/Backward 共用。設計細節 `docs/dev/decline_directives.md`、failure_reason mapping `docs/failure_modes.md` §2。

| directive | failure_reason | 路由 |
|---|---|---|
| `unprovable` | `agent_infeasible` | shelve + cascade up |
| `return_to_parent` | `parent_needs_fix`（新）| shelve + cascade up + description 投 parent fix hint section |
| `shelve` | `agent_shelved`（新）| shelve + cascade up |
| `needs_decomposition` | `agent_declined`（沿用、舊 token `too_hard`）| `entry_kind='Backward'` 切換 |

實作：`Tooling/pipeline/__init__.py` 新 `DECLINE_*` 常數 + `DECLINE_TO_FAILURE_REASON` map；`builder.py` / `backward.py` parse 改用 map；`dispatcher.py:cascade_one` 對稱處理 Builder + Backward 三條 shelve+propagate 路徑；`pipeline/_retry.py:_TERMINAL_DECLINE_REASONS` 跟 `_maybe_reflect` trigger 補上新 reasons；`pipeline/events.py` `_NON_AGENT_REASONS` + `infeasible_subs` SQL 都擴；`context.py` 渲染加 directive tag + 三類別 preamble；4 個 prompt 檔（builder.md / builder_singleshot.md / backward.md / backward_singleshot.md）`## Decline` 章節統一改寫。

### Cascade-vs-verify race fix（commit `5bded83`）

leaf-bypass 提交 strategy 後 `WorkArea.__exit__` 釋放 gateway session 可能花 30s（高並發 release_session timeout）、worker 還沒回來時 main thread 跑了 verify_housekeeping 殺策略並 reopen goal、worker 終於回來 cascade(success) 又把 status 改 `attempting`。bfs_refill 排除 'attempting'、dispatcher idle exit、root 還有 budget 沒用就停。

修：`cascade_one` Backward success 加 `has_live` guard、無活策略不轉 'attempting'。Run #4 證觸發 ≥3 次都正確。

### Leaf-bypass acceptance axiom probe（commit `968e4e7`）

sonnet 偷塞 sorryAx 的 leaf-bypass：patch.lean 字面無 `sorry`、LSP `errors_at` 回 0、`goal_at` 回 "no goals"、agent 信任地 ship；但 Lean elaborator 對某些 unification 失敗塞 synthetic sorry、`#print axioms` 抓得到。原來 verify 階段才抓、走完 promote_to_alias + parent build 約 5-10s。修法：leaf-bypass 接受階段直接帶 `axioms_for=fq_name`、見 sorryAx → `axiom_violation` reject、scratch 清掉、不進 ready_for_verify queue。Run #4 沒驗（commit 在 daemon 啟動後）、Run #5 看效果。

### Rescue prompt 三選項 + 動態時限（commit `c24263e`）

rescue spawn 用 `--resume` 進入「force-ship」注意力收窄、若原 rescue prompt 只列「ship patch + sorry stubs」兩條、agent 看不到 `decline:` 出口、silent thinking 等死（SG run #2 g224 4× 全 rc=124）。修：rescue prompt 列 (a) ship stubs (b) leaf-bypass 直推 (c) `decline: unprovable` + counterexample 三條 + `<N> minutes left, act now` 動態時限（從 `dispatch.rescue_timeout_sec` 讀）。

對照 SG run 統計：

| Run | rescue 成功率 |
|---|---|
| #2（修前）| 0/9 = 0% |
| #3（snapshot fix） | 2/6 = 33% |
| #4（race fix 補完）| 8/14 = 57% |

### Snapshot-once goal_lean（commit `15f54b2`）

`backward.py` / `builder.py` 原本 worker 每次 spawn 都 re-snapshot `goal_lean.backup`、retry 時等於用「上次 contaminated 狀態」當基準、agent 看到上次的爛 partial 繼續加碼。修：snapshot 一次（pipeline 入場）、每次 spawn entry restore 從 pristine、parse exit 再 restore、outer finally 收尾 unlink。Run #4 全程驗 backup 都 pristine。

## 累計 framework 機制清單（給下次 session 對齊）

| 機制 | commit | 觸發 | 健康 metric |
|---|---|---|---|
| snapshot-once goal_lean | `15f54b2` | 每次 Backward / Builder pipeline | backup 跨 retry 全 pristine |
| rescue 3-option prompt | `c24263e` | watchdog wall_cap 720s 後 | rescue rc=0 比率 |
| cascade-vs-verify race fix | `5bded83` | leaf-bypass + verify 殺策略 + cascade 後到 | 不出現「shelved goal but bfs filter excludes」idle exit |
| leaf-bypass acceptance axiom probe | `968e4e7` | leaf-bypass 提交時 | `axiom_violation` 在 acceptance 階段抓、不進 verify |
| Decline directives 4-token | `54ed9fb..87370bb` | agent 寫 `decline: <token>` | `dead_attempts.failure_reason` 分布、`parent_needs_fix` 數 > 0 |
| Singleton daemon lock | `e9d3bbd` | daemon 啟動 | `.asterism/daemon.pid` 不重複 |
| Gateway 專屬 log + 30s release timeout | `f6d838f, 1765311` | gateway 跑 | crash 留 traceback、release 不 spurious 警告 |
| `release_session` 30s | `1765311` | WorkArea exit | 高並發不 timeout |
| Verify unification + `lean-asterism-server` | `7f7e443..9188f9c` | 所有 verify path | cascade level 3-5s（vs lake build 25-50s）|
| `waitForDiagnostics` LSP fix | `40ad9cb` | apply_edit / validate_file | 從 3.26s 降到 0.22s |

## 信號監控（每次 run 後檢查）

| 信號 | 期望 |
|---|---|
| `naming_violation` / `patch_signature_mismatch` | 0 |
| Mathlib Grep denied / Cross-Problem read | 0 |
| `spawn_fast_fail` | 0（quota 才會非 0）|
| `quota_exhausted` / `missing_dep` | 0 |
| `hot_rate` | > 50%（< 30% 持續 = 該 cut）|
| `n_cold_evicted` | < 15% of total acquires（pool > W 設計內、PN baseline 4.1%）|
| dispatcher idle exit | 必伴隨 `roots_proved=True` 或所有 root shelved |

## 已知未解 / 觀察中

- **opus 23s outliers in single agent**: Lean elaborate substantial content 真實成本、非 framework
- **gateway 偶發 silent exit**: `02:47 crash 一次無 traceback、後續未復現、`gateway.log` 有保險、再現有可看
- **Backward 是否在收到 fix hint 時 incremental fix**：commit `54ed9fb` 寫進 context.md 提示但 backward.md prompt 沒明文鼓勵；下次 SG run 看 agent 行為再決定 prompt 補一段
- **Strategist / Forward / Generalizer**：留給 v2、Decline directive 系統先看能 cover 多少場景

## Proved problems（已驗）

| Problem | Prover | Wall-clock | Axioms |
|---|---|---|---|
| compactness | Opus | ~25 min | std 3 |
| compactness | Sonnet | ~60 min | std 3 |
| gen_generates | Sonnet | ~30 min | propext, Quot.sound |
| inner_zero_iff_smul | Sonnet | ~21 min | std 3 |
| proj_nonexpansive | Opus 4.7 (1M) | 30 min depth-3 | std 3 |
| cantor_xi_measure | Sonnet | ~4 hr | std 3 |

SG / cantor 是當前最大樣本（50+ goals、4hr+ wall、有 Kelly minimizer 類型困難 sub-goal）。SG 在 Asterism 過去有以 sonnet 證過記錄（操作人提供）；本 session 多次 SG run 是 framework stress test、不是「證 SG」目的。

## 重要參考

- `docs/dev/decline_directives.md` — 4-token decline directive 系統設計
- `docs/dev/bridge_lemma_layer.md` — 長期方向：把 cross-product algebra 集中成 bridge lemma
- `docs/data-flow.md` — agent 與框架資料流
- `docs/architecture.md` — DB schema、cascade rules、pipeline 細節
- `docs/failure_modes.md` — failure_reason / event_type single SoT
- `docs/OPERATOR.md` — CLI subcommands、env vars、recurring traps

## 用戶 preferences

操作者全域 memory 在 `C:\Users\ander\.claude\projects\D--Asterism\memory\`、本檔不重複。
