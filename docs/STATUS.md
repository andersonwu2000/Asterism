# Asterism v2 — Current Status

更新於 **2026-05-11 00:30 local**、HEAD `0e279fe`、**717 unit tests green / 1 skipped**。

## ⚠️ Compact-time handoff — 兩個 SG daemon 還在跑

**Run #13** (D:/Asterism, current HEAD with thinking cap restored)：
- daemon pid **98852**、background task `bhdx1656o`
- log `D:/Asterism/.asterism/logs/multi_claude-sonnet-4-6_20260510-155421.log`
- cron `c405caae` :19/:39/:59
- cadence log `runs/sg_run_13.md`
- budget 16200s = 4h30、+12 min cadence 觀察、即將 +18 min watchdog wall_cap
- **驗證 hypothesis**：thinking cap restoration（commit `0e279fe`）能否消除 trap event

**9d05d19 並行**：
- workspace `C:/Users/ander/Downloads/Asterism_sonnet_9d05d19/`、daemon pid **11820**、task `bg9qk954s`
- log `Downloads/Asterism_sonnet_9d05d19/.asterism/logs/sylvester_gallai_claude-sonnet-4-6_20260510-134321.log`
- cron `df5e3837` :03/:23/:43
- cadence log `runs/sg_run_9d05d19.md`
- @+150 min: 17 proved / 23 goals / 3 shelved、Goal=23 trap loop（kelly_ordinary deeper layer）
- 預估 2-3 hr 內自然失敗（cascade-shelve up）

**雙 daemon 跑 = API 雙倍 burn**、撞 5h rate limit 風險。

## 本 session 核心發現

**root cause = `bdbe7a7` (5/8 14:33) 移除了 `MAX_THINKING_TOKENS` + `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` env vars**。

證據鏈：
1. **9d05d19 引入 commit `8f0d2b3`** (5/5 11:39) 含經驗數據：148 個 SG Backward body spawns
   - dive (0 writes timeout): median 9097 tokens
   - partial (1-2 writes): median 10250
   - complete (3+ writes ok): median 3729、max 14545
   - sweet spot 7-10K cap、`max(1000, (timeout_sec // 60) * 1000)` = 1K/min proportional
2. **`bdbe7a7` 移除動機**（commit body）：
   - 「cap rarely hit (1 of 5 stuck cases)」← 但這是 cap 工作中的觀察、被 misjudge 為 cap 沒效
   - 「real anti-pattern is tool_use silence」← silence 是症狀、cap 從入口 prevent
   - 「cap had collateral damage on legit deep thinking」← cap 是 per-turn、跨 turn 累積不受限
   - **真正動機（user 修正、未在 commit body）**：「錯誤 decomposition 撐 cap 強制 ship 後 bad shape 往下傳染整棵樹」
3. **run #11/#12 (5/10) 觀察 trap 行為復現**：Goal=292 4 attempts 全 trap、never proved
4. **9d05d19 baseline replay**：14-17 proved depth 4、0 trap event、cross-pipeline retry 救回 lake_build_error

**論證強度**：commit `0e279fe` 加回 cap 用同 1K/min formula、run #13 驗證中。

## ⚠️ User flagged 未完任務

User 提到「**後續還有更細緻的數值設定的討論**」我沒挖到。compact 後的 session 應該：
1. 找 `8f0d2b3..bdbe7a7` 之間（5/5-5/8）關於 cap 數值 tune 的進一步討論
2. session jsonl 對應在 `C:/Users/ander/.claude/projects/D--Asterism/`（5/5-5/8 jsonls）
3. 可能調整過 1K/min 比率、或加 per-kind 區分（Backward vs Builder）、或 floor/ceiling 細節

當前 commit `0e279fe` 用 1K/min（同 9d05d19）、可能略寬（900s spawn → 15K vs 9d05d19's 600s → 10K）。run #13 數據如顯示仍有 trap 事件、就需要用更細緻設定 tighten。

## 本 session commits (chronological)

| commit | content |
|---|---|
| `0028d60` | stream_parser: real-time Anthropic SSE state machine |
| `07fa2e7` | claude_cli: stream-json + watchdog single-trigger trap detection |
| `013c718` | _retry: TIMEOUT trap branch + extract fresh-sid takeover helper |
| `40e37c6` | yaml + STATUS: retire idle_window_sec |
| `c872311` | watchdog v4: trap_check_sec + AND condition + combined STUCK_THINKING takeover |
| `61d3421` | fresh-sid prompts: explicit attempts_dir paths |
| `adde5aa` | Backward: revert to lake-build verification (disable LSP MCP) |
| `8d7c001` | **Revert** adde5aa（user 結論 LSP off Backward 不是兇手）|
| `0e279fe` | **claude_cli: restore MAX_THINKING_TOKENS cap (revert bdbe7a7)** ← 主要修復 |

## SG run 對照表（all sessions）

| Run | Wall | Proved | Trap events | Notes |
|---|---|---|---|---|
| #4 baseline (pre-LSP) | 270min | 4 | n/a (no detection) | early dispatcher |
| #8 (v1 fresh-rescue) | 270min | 1 + 1 shelved | 4 stuck_thinking | v1 design failure |
| #9 (v2 two-stage) | 36min cut | 0 (cut) | n/a | s219 root cause investigation |
| #10 (v3 stream-json) | 30min cut | 1 main + 1 sub | 3 traps + path BUG | path BUG observed |
| #11 (v4 + path fix) | 108min cut | 1 main + 1 sub + 2 sub-leaves | many | Goal=289 trap loop |
| #12 (LSP off Backward) | 110min cut | 4 | 8+ | LSP not the culprit |
| **#13 (cap restored, in flight)** | +12min | 1 main | 0 so far | **hypothesis test** |
| **9d05d19 (replay, in flight)** | +150min | 17 + 3 shelved | **0** | baseline data |

## v4 機制清單（cap restoration 後預期變 vestigial）

當 cap 工作如預期、watchdog v3/v4 + fresh-sid takeover machinery 大部分成 dead code（trap 不該 manifest）。但**先不清理**、避免 regression bundle：

- watchdog single-trigger AND condition (commit `c872311`)
- stream-json + parser (commit `07fa2e7`、`0028d60`)
- TIMEOUT-trap branch + `_run_fresh_sid_takeover` (commit `013c718`)
- combined-takeover variant for STUCK_THINKING (`c872311`)
- fresh-sid stage 2/3 prompts with explicit attempts_dir (`61d3421`)
- `_parser_state.json` forensic file (`07fa2e7`)
- `[detector verdict: ...]` in failure_detail (`013c718`)

cleanup 排程：等 SG run #13 + 1-2 個後續 SG run 確認 trap 不再 manifest、再考慮移除 v3/v4 backstop。如果 cap 在 production 有 edge case 漏網、留 backstop 救命。

## 已知未解 / 觀察中

- **cap 數值精緻調整**：user 提及 5/5-5/8 期間有更細討論、本 session 沒挖到（jsonl 沒 grep 到）。下個 session 重新搜
- **kelly_ordinary class 仍 hard**：9d05d19 也卡 Goal=9/14/16/23、SG run 即使有 cap 也不見得能 end-to-end prove。STATUS 已記錄為長期未解的「Sonnet 對 hard math 的 deep thinking」、framework 不可修。考慮 (a) Strategist agent 重新規劃、(b) 換 model（user 拒絕走捷徑）、(c) prompt 改寫降低 thinking 誘因
- **post-LSP 累積架構成本**：watchdog v3/v4 + fresh-sid takeover + stream parser 約 700 行代碼。如 cap 證實有效、cleanup 釋出技術債

## 提醒下個 session 操作

1. **先讀 `runs/sg_run_13.md` + `runs/sg_run_9d05d19.md`** 看兩個 daemon 進度
2. **如果 daemon 還活著**：cron 還會 fire、自主 cadence 即可
3. **如果 daemon 自然結束**：兩個 cron 本應自己看到、應該 final summary 並 CronDelete
4. **cap 數值**：當前 1K/min（900s body → 15K）。run #13 數據如顯 trap、考慮 tighten 到 constant 10K body / 3K rescue (option A) 或 0.7K/min (option B)
5. **挖 5/5-5/8 jsonls** 找 cap 細緻討論（user 確認有、需找出）
6. user 紀律：framework 強化 > problem prove、不接受換 model 的 escape

## 重要參考

- `Tooling/llm/claude_cli.py` — cap 設定 + watchdog v4 + stream parser 整合
- `Tooling/llm/stream_parser.py` — 即時 SSE event state machine
- `Tooling/pipeline/_retry.py` — STUCK_THINKING + TIMEOUT-trap branch + takeover helpers
- `runs/sg_run_11.md`、`runs/sg_run_12.md`、`runs/sg_run_13.md`、`runs/sg_run_9d05d19.md` — 本 session 數據
- 9d05d19 引入 commit `8f0d2b3` body — 經驗 cap 數值來源
- 9d05d19 移除 commit `bdbe7a7` body — 移除理由（user 認為部分理由有問題）

## 用戶 preferences

- 操作 SG/cantor/PN 等 problem run 是 **framework stress test**、不是「證它」
- 「換 opus」「換 problem」等 escape 不接受、應提框架側修改
- 路徑寫死 / hardcoded 警惕、但確認 dynamic substitution 仍 portable 後可接受
- backward.md / 其他 prompt 改動先討論再動
