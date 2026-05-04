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

1. **難度系統 binary 化** — 現況 Backward 估 1-10 difficulty，`≥4` 硬閘門跳過 Builder 進 Backward。問題：agent 估的是「概念複雜度」非「Builder 可不可破」，導致 g380（`ring`/`linear_combination` 一槍可破的多項式恆等式）被誤判 ≥4，5 次 Backward 全 timeout。改造：Backward 寫 sub-goal 時直接標 directive `kind: "Builder"|"Backward"`（或 `needs_decomposition: bool`）取代數字。安全網：Builder 試 N 次 fail 自動升 Backward；Backward 試 M 次 shelve（同現況）。先 grep `difficulty` 全棧用法確認沒其他依賴再動。
2. **SG with F55**（已跑、進行中）— postmortem 機制驗證有效（s215→s235 alternative-direction 收斂）；但 g380 暴露難度估錯結構性問題，見 (1)。
3. **F38 Gemini live smoke** — quota 恢復後跑
4. **第三方 deep problem** — cantor 是當前最深，再要更深場景才知道 dedupe / cascade 邊界
5. **Strategist** — 拆 Backward 為 Plan + Decompose；只有 SG 失敗到 F55 不夠才真的需要

## 重要參考

- `docs/data-flow.md` — agent 與框架資料流（F55 + F56 概念入口）
- `docs/architecture.md` — DB schema、cascade rules、pipeline 細節
- `docs/OPERATOR.md` — CLI subcommands、env vars、recurring traps

## 用戶 preferences

操作者全域 memory 在 `C:\Users\ander\.claude\projects\D--Hadamard\memory\`，本檔不重複。
