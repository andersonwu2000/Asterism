# Asterism v2 — Current Status

更新於 **2026-05-10**、HEAD `b4308ec` + WIP（stream-json watchdog redesign）、**707 unit tests green / 1 skipped**。

## 下個 session 接手要做的事

**watchdog stream-json redesign 已寫完待 commit + SG run #10 驗收**。本 session 在 SG run #9 觀察到 s219 的 TIMEOUT-path postmortem `--resume` 撞 thinking trap 失敗（agent 180s 內 0 events）→ 觸發兩條 path 對齊 + watchdog 機制重寫。

修復計畫摘要（已實作、未 commit）：
1. claude CLI 切到 `--output-format stream-json --verbose --include-partial-messages`（只在 watchdog_eligible 時用）
2. 新 `Tooling/llm/stream_parser.py`：解 stream events、維護 idle/mid-thinking/mid-tool/mid-text/finalized state + last_stop_reason
3. watchdog 改成 single-trigger at wall_cap、sample `parser.is_thinking_trap()`（state==mid-thinking OR finalized+max_tokens）
4. TIMEOUT path 加 parser final state 檢查、trap → fresh-sid stage 2/3 takeover（與 STUCK_THINKING path 對齊）
5. 拿掉 `idle_window_sec` config + watchdog jsonl polling
6. dead_attempts.failure_detail 加 detector verdict forensic 標記
7. `_run_fresh_sid_takeover` helper 抽 STUCK_THINKING / TIMEOUT-trap 兩 path 共用

**SG run #10 驗收重點**：
1. `[watchdog] sid=... wall cap ...; trap (state=... last_stop_reason=...); killing for rescue` log 出現
2. `[timeout-trap] sid=... parser detected trap...; running fresh-sid takeover` log 出現（s219-class case）
3. 沒被 watchdog 抓的 active spawn → `--resume` postmortem 寫得出 `_progress.md`、`.drafts/` 有檔
4. dead_attempts.failure_detail 含 `[detector verdict: ...]`
5. 整體 thinking trap 處理 wall < 7 min/event

**異常 cut**：gateway crash loop / hot_rate < 30% 持續 / 連續 ≥3 個 thinking trap 都 stage2+3 都不出 deliverable / shelved% > 60%。

## 2026-05-10 session 落地（11 commits）

### Watchdog idle-window guard + Backward bail option（commit `b6ece82`）

**Watchdog idle-window guard**：原 watchdog 在 wall_cap（spawn-rescue=720s）unconditional 殺。改成 wall_cap 那刻檢「過去 8 min 內有 tool_use 嗎」、無→殺（rc=128 STUCK_THINKING）、有→defer（讓 spawn 跑到自然 subprocess timeout、走 TIMEOUT path）。idle_window_sec 進 yaml（預設 480）。

**Backward bail (option d)**：原 rescue prompt 3 選項（ship stubs / leaf-bypass / decline unprovable）加第 4 選項：「沒把握就寫 `_progress.md` exit、無 patch.lean」。Backward parse 偵測 `_progress.md` + skeleton patch + 無 new_*.lean → 新 failure_reason `agent_bailed`、加進 `_TERMINAL_DECLINE_REASONS`。outer wrapper 把 `_progress.md` persist 到 `.drafts/`、下輪 cold dispatch 看到。設計動機：Backward 強硬 ship 爛 split fan-out 比 Builder 爛 leaf 嚴重多（cascade up parent_needs_fix）、給 honest exit。

### TIMEOUT salvage + bail discriminator strict（commit `2504650`）

g266 anomaly：agent finished work（patch + sub-lemmas + validate pass）但繼續做 `ls` self-check + 寫 `_progress.md`、**過 900s subprocess timeout 才 exit**。原 TIMEOUT path 走 postmortem + forced exhaust、丟掉所有 disk output。修：rc=124 先 try `parse_fn()`、success/decline 直接 attach；非 terminal fall through 走 postmortem + 把 parse outcome fold 進 detail（forensic 透明）。同時 bail discriminator 加嚴：不能光看 `_progress.md` 存在、要四件齊（progress + 無 leading + 無 new_* + sorry body）才算 bail、避免 cargo-cult 寫 `_progress.md` 的 agent 被誤判 bail。

### Forensic bug fix（commit `55e38f6`）

`_spawn_failure` 讀 `attempts_dir/_spawn.stderr` 拼進 detail。原 TIMEOUT path 先 `postmortem_fn(sid)` 再 `_spawn_failure`、postmortem spawn 自己若 timeout 寫的 stderr 會覆蓋 main 的、operator 看 dead_attempts.failure_detail 看到 "TimeoutExpired after 180s"（postmortem budget）而非 "after 900s"（main budget）。修：swap 順序、`_spawn_failure` 先讀。

### Fresh-rescue v1 → v2（commits `722472d` → `bf44bc5` → `8277c3c`）

**v1（722472d）**：當 watchdog 殺 STUCK_THINKING、抽 broken jsonl 的 thinking blocks 寫 `_prior_analysis.md`、cold spawn fresh sid + cold prompt 含「MUST Read prior_analysis」directive。Probe（16176de5 → 236ced1d）4 min ship 完整 Backward 結構成功。但 v1 用 **full spawn_timeout_sec budget（900s）**、且 fresh-rescue 失敗會在同 pipeline 內遞迴觸發 fresh-rescue。

**v1 + TIMEOUT salvage（bf44bc5）**：fresh-rescue rc=124 也加 salvage parse、跟主 spawn TIMEOUT 對齊。

**SG run #8 暴露 v1 設計問題**：4 個 fresh-rescue 全失敗（rc=128/124）、累計燒 ~50 min wall、0 useful deliverable。Pattern：Sonnet 對 hard sub-lemma（kelly_smaller_triple class）的 deep thinking 是 **goal-content driven**、不是 session-state driven。Probe 成功的 case（kelly_min_ordinary）prior thinking 完整、production hard goals prior thinking 本身就在 deadlock 中。

**v2（8277c3c）**：完全 redesign 為 **two-stage takeover**：
- **概念**：原 session 廢了、由新 session **接手原 session 該做的事**（rescue + postmortem stages）、保留原 budget 結構、不是「重做整個 task」
- **Stage 2** (`rescue_timeout_sec` ~180-240s)：fresh sid + 拷 broken jsonl 到 `attempts_dir/_broken_session.jsonl` + ship-or-bail prompt（agent 自己 Read 看）
- **Stage 3** (`postmortem_timeout_sec` ~180s)：stage 2 fail / parse 非 terminal → fresh sid + postmortem prompt、agent 寫 `_progress.md`
- **Worst-case cost / stuck event**：~6 min（vs v1 15-30+ min、含遞迴）
- **不抽 thinking、不寫 `_prior_analysis.md`**：agent 用 Read 工具直接看 jsonl
- 拿掉 `is_fresh_rescue` 旗標、用 `inline_prompt` + `budget_override` SpawnCtx 欄位代替

**Prompt tightening（b4308ec）**：stage 2/3 prompts 收緊 — 短 Read hint（不全拿掉、jsonl 可達 400KB）、拿掉「no deep analysis」（math 本來需要深思考、矯枉過正）、拿掉「'none — direction sound'」hedge。

## SG runs 對照（this session）

| Run | wall | proved | shelved | 主驗證 | 結論 |
|---|---|---|---|---|---|
| #4 | 270min | 4 | 5 | baseline、無新修 | 對照基準 |
| #5 | 270min（cut）| 3 | - | snapshot+race+axiom+decline | g263 卡 stuck-rescue 4/5 |
| #6 | 中止 | 0 | - | 加 idle-window+bail | max_tokens deadlock × 多次 |
| #7 | 中止 | 0 | - | 加 2-phase rescue（已廢）| STOP-then-rescue 在 production fail |
| #8 | 270min | **1** | 1 | 加 fresh-rescue v1 | v1 0 success rate、~50 min 浪費 |
| #9 | in-flight | ? | ? | fresh-rescue v2 + tighter prompt | **看 cadence log** |

## 累計 framework 機制清單（v2 後更新）

| 機制 | commit | 觸發 / 健康 metric |
|---|---|---|
| snapshot-once goal_lean | `15f54b2` | backup 跨 retry 全 pristine |
| cascade-vs-verify race fix | `5bded83` | 不出現「shelved goal but bfs filter excludes」idle exit |
| leaf-bypass acceptance axiom probe | `968e4e7` | `axiom_violation` 在 acceptance 階段抓、不進 verify |
| Decline directives 4-token | `54ed9fb..87370bb` | dead_attempts 含 `parent_needs_fix` / `agent_shelved` 行 |
| ~~Watchdog idle-window guard~~ | ~~`b6ece82`~~ | **2026-05-10 retired** — silence-only 抓不到 mid-thinking before silence 累積（s219 case 2 silence 468s 擦邊 480s threshold）。改用 stream-json 即時偵測 |
| **Backward bail option (d)** | `b6ece82` | `agent_bailed` failure_reason、`_progress.md` 進 .drafts/ |
| **TIMEOUT salvage** | `2504650` | rc=124 先 parse 救起 success / decline、不直接走 postmortem |
| **Bail discriminator strict** | `2504650` | progress + skeleton patch + 無 leading + 無 new_* 才算 bail |
| **Forensic bug fix** | `55e38f6` | dead_attempts.failure_detail 是 main spawn 的 stderr、不被 postmortem 覆寫 |
| **Fresh-rescue v2 two-stage** | `8277c3c` | STUCK_THINKING → stage 2 fresh ship-or-bail + stage 3 fresh postmortem、各 ~3 min budget |
| **Fresh-rescue prompts tightened** | `b4308ec` | stage 2/3 prompt 短 Read hint、無「no deep analysis」過度抑制 |
| **Watchdog stream-json + thinking-trap detector** | _pending commit_ | `--output-format stream-json --include-partial-messages` + StreamParser；watchdog single-trigger at wall_cap → `state == mid-thinking OR last_stop_reason == max_tokens` 即時偵測 |
| **TIMEOUT path trap branch** | _pending commit_ | rc=124 + salvage fail + parser final state == trap → fresh-sid takeover（同 STUCK_THINKING）；active → 保留 `--resume` postmortem |
| **Forensic detector verdict** | _pending commit_ | dead_attempts.failure_detail 加 `[detector verdict: ...]` 段、累積數據後 tune threshold |

（其餘穩定機制如 daemon lock / gateway log / waitForDiagnostics 仍同前、不重列）

## 信號監控

| 信號 | 期望 |
|---|---|
| `naming_violation` / `patch_signature_mismatch` | 0 |
| Mathlib Grep denied / Cross-Problem read | 0 |
| `spawn_fast_fail` | 0（quota 才會非 0）|
| `quota_exhausted` / `missing_dep` | 0 |
| `hot_rate` | > 50%（< 30% 持續 = 該 cut）|
| `n_cold_evicted` | < 15% of total acquires |
| dispatcher idle exit | 必伴隨 `roots_proved=True` 或所有 root shelved |
| **`[fresh-rescue stage2]` 出現** | stuck-thinking 觸發、看 dur < 4 min |
| **`[fresh-rescue stage3]` 出現** | stage 2 沒收口、看 dur < 4 min |
| **`agent_bailed` dead_attempts 出現** | stage 2 (d) 或 stage 3 寫 `_progress.md` 成功 |

## 已知未解 / 觀察中

- **Sonnet 對 hard sub-lemma class 的 deep thinking 不可框架修**：goal_content driven、撞 max_tokens 32K、framework 任何 post-hoc rescue 不解 root cause。Long-term：考慮 (a) Anthropic API thinking budget cap（已 deprecated 但可能仍有用）、(b) `--effort medium`（推 docs 有用、但官方說「不保證」）、(c) Strategist / 換 model
- **fresh-rescue v2 的 production transferability**：probe 成功 vs run #8 v1 production 全失敗、原因之一是 MCP overhead + concurrent pipelines。v2 的 stage 2/3 budget 縮短後是否仍能 ship、待 run #9 驗
- **Cut criterion 設計缺陷（cron 端、非框架）**：「same sid ≥3 fresh-rescue fails」設計上不會觸發（每次 fresh-rescue 換新 sid）。下次設 cron 用「across-sid 累計」criterion
- **opus 23s outliers / gateway 偶發 silent exit**：仍未解、低優先

## Proved problems（已驗）

| Problem | Prover | Wall | Axioms |
|---|---|---|---|
| compactness | Opus / Sonnet | ~25 / ~60 min | std 3 |
| gen_generates | Sonnet | ~30 min | propext, Quot.sound |
| inner_zero_iff_smul | Sonnet | ~21 min | std 3 |
| proj_nonexpansive | Opus 4.7 (1M) | 30 min depth-3 | std 3 |
| cantor_xi_measure | Sonnet | ~4 hr | std 3 |

SG 在 Asterism 過去有以 sonnet 證過記錄（操作人提供）；本 session 多次 SG run 是 framework stress test、不是「證 SG」目的。

## 重要參考

- `docs/dev/decline_directives.md` — 4-token decline directive 系統設計
- `docs/dev/bridge_lemma_layer.md` — 長期方向：把 cross-product algebra 集中成 bridge lemma
- `docs/data-flow.md` — agent 與框架資料流
- `docs/architecture.md` — DB schema、cascade rules、pipeline 細節
- `docs/failure_modes.md` — failure_reason / event_type single SoT
- `docs/OPERATOR.md` — CLI subcommands、env vars、recurring traps
- `runs/sg_run_8.md` — fresh-rescue v1 production failure 完整觀察（13 cadence + final summary）
- `runs/sg_run_9.md` — fresh-rescue v2 production validation（in-flight）

## 用戶 preferences

操作者全域 memory 在 `C:\Users\ander\.claude\projects\D--Asterism\memory\`、本檔不重複。
