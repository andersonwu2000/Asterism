# Asterism v2 — Current Status

更新於 2026-05-04（F55 + F56 收尾後）。HEAD `919b1a8`，**569 unit tests + 24 lake-integration green**。

## 下個 session 接手要做的事

Daemon 已停。Operator 即將 /compact 後跑 **sylvester_gallai (Sonnet)** 驗證 F55 postmortem-spawn 機制。SG root id=292 已 reset + init。

```
ASTERISM_BUDGET_SEC=5400 python -m Tooling.cli run
```
（cwd `D:/Asterism`；daemon log 自動 tee 到 `.asterism/logs/`）

**SG 是 F55 的關鍵測試點**：先前 720s timeout 也撐不住、root 未產 PROPOSAL.md。F55 預期讓每次 timeout 留下 `Problems/sylvester_gallai/.drafts/backward_g292.md`（postmortem 寫的進度筆記），下次 spawn 從 sketch 開始而非 0。

健康訊號（要看的）：
- 第 1 次 timeout 後 `.drafts/backward_g292.md` 出現
- 第 2 次 spawn 的 Context.md 內聯「Your previous progress note」段
- 0 spawn_fast_fail / 0 naming_violation / 0 mathlib Grep denied

## 最近批次（2026-05-04）

按時間倒序，三批改動：

**F55 redesign + F56**（commit `27d46bb`）— 改框架對失敗 spawn 的處理：
- F55 棄「邊寫邊存 PROPOSAL.md」改用「timeout 後 postmortem spawn 寫 _progress.md」。主任務不再要 agent 維護 deliverable，partial 從 deliverable 解耦成獨立側通道。
- F56 砍 worker_kind="Verify"。strategy 驗證改成 dispatcher tick 末端的 housekeeping 步驟（純框架、無 LLM、不佔 worker pool）。F41 LLM 修復同步取消（26 verify 0 觸發）。
- 兩件事一起做，因為 timeout 處理 + verify 收尾都是「失敗/收尾路徑的清理」性質的工作。

**M3**（commit `d045e15`）— `--add-dir <packages>` 修復 mathlib Grep 被拒問題。M1 加寬 allowlist 但仍有 75 次 Grep 拒絕，根因是 F44 narrowing cwd 後，claude permission 把 cwd subtree ∪ --add-dir 當隱式信任邊界，allowlist 被忽略。加 packages 進 add-dir 修。

**docs**（commit `919b1a8`）— `docs/data-flow.md` 新檔（概念敘事、agent 與框架資料流）；`architecture.md` v2.5 → v2.6 反映 F55+F56。

## Proved problems

| Problem | Prover | Wall-clock | Axioms |
|---|---|---|---|
| compactness | Opus | ~25 min | propext, Classical.choice, Quot.sound |
| compactness | Sonnet | ~60 min | 同上 |
| gen_generates | Sonnet | ~30 min | propext, Quot.sound |
| inner_zero_iff_smul | Sonnet | ~21 min | std 3 |
| proj_nonexpansive | Sonnet | ~58 min | std 3 |
| **cantor_xi_measure** | Sonnet | **~4 hr**（含 90min budget exit + 重啟）| std 3 |

cantor 是當前最大 sample（50 goals、depth 4、18 verify）。F55+F56 改動後尚未跑過完整題目 — SG 是首次驗證。

## 信號監控（每次 run 後檢查）

| 信號 | 期望 | 觸發來源 |
|---|---|---|
| `naming_violation` | 0 | F52 + F53/A |
| `patch_signature_mismatch` | 0 | F52 |
| Mathlib Grep denied | 0 | M1 + M3 |
| Cross-Problem read | 0 | F44 sandbox |
| `spawn_fast_fail` | 0（除非 quota）| F46 |
| 新訊號：postmortem `_progress.md` 寫入 | timeout 時寫一次、success 時清掉 | F55 |
| 新訊號：verify housekeeping promote | 每 strategy 一次、可鏈式 | F56 |

## 砍掉但留參考的舊機制

- **F40** Two-phase Builder（commit `2b6ff1a` revert at `232a3e0`）— Phase A 寫 PROPOSAL、Phase B 寫 patch。Haiku 實證證明瓶頸在 patch 品質不在 deliverable miss。除非新 model 失敗模式換成 deliverable miss，不重做。
- **F31** `if "haiku" in model:` substring tier — Asterism.yaml 化後退役，weak-tier 改顯式寫 `(builder.threshold, dispatch.shelve_threshold) = (5, 10)`。
- **F41** Verify-time LLM patch retry — 26 verify 0 觸發，F56 一起取消。實證 Step 1 開始失敗才回頭加。
- **F55 邊寫邊存版**（commit `cdb03b5`，被 `27d46bb` 取代）— 讓 agent 邊寫 PROPOSAL.md 邊 save。實作出來但用戶指出污染主任務注意力，改成 postmortem spawn 設計。

## 待辦（按優先序）

1. **(已做) entry_kind 直接 directive，刪掉 difficulty** — Backward 在每個 `new_<slug>.lean` 標 `-- entry_kind: Builder | Backward`；framework parse 進 `goals.entry_kind`；`next_worker_kind` 第一次 honor directive，attempts ≥ BUILDER_THRESHOLD 強制升 Backward 兜底。Root entry_kind 由 cli init 直接從 Manifest `## Entry kind` 段讀取。Manifest 改為直接寫 binary directive，數字 `## Difficulty` 整個從 schema / 程式 / 測試 / 文件移除（87 個 reference 全清）。

2. **(已做) TACTIC_TRY_LIST 補 `assumption` / `tauto` / `exact?`** — `A → B → A`-shaped 廢題型 Phase 1 直接收工。`linear_combination`（需係數）/ `polyrith`（需 Sage）暫不做。
3. **(已做) Infeasibility escape channel** — `decline_reason: parent_type_infeasible` PROPOSAL.md frontmatter；Builder + Backward 都可 escape；cascade 直接 shelve goal + propagate 上層重拆，不燒 attempts。SG 實證 g363 一次 spawn 內構造反例 + escape 成功。
4. **SG with new framework**（已跑驗證部分機制）— F55 postmortem alternative-direction 確認有效；entry_kind 修補後 root 直接 Backward；尚未跑出完整 root proved。
4. **F38 Gemini live smoke** — quota 恢復後跑
5. **第三方 deep problem** — cantor 是當前最深，再要更深場景才知道 dedupe / cascade 邊界
6. **Strategist** — 拆 Backward 為 Plan + Decompose；只有 SG 在 entry_kind directive 後仍卡住才真的需要

## 重要參考

- `docs/data-flow.md` — agent 與框架資料流（F55 + F56 概念入口）
- `docs/architecture.md` — DB schema、cascade rules、pipeline 細節
- `docs/OPERATOR.md` — CLI subcommands、env vars、recurring traps

## 用戶 preferences

操作者全域 memory 在 `C:\Users\ander\.claude\projects\D--Hadamard\memory\`，本檔不重複。
