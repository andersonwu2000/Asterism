# Asterism 開發計畫總覽

7 個 phase，每個 phase 對應一個可獨立 demo 的 framework 能力切片。

## 配對文件

- 規格：`docs/architecture/architecture.md`、`architecture_pipelines.md`、`architecture_impl.md`
- Runtime 演習：`D:\Hadamard\docs\debug.md`（待搬入本 repo）
- 各 phase 細節：本目錄 `phaseN_<name>.md`

## Phase 表

| # | 名稱 | 新引入能力 | Demo |
|---|---|---|---|
| **P1** | Skeleton | Lake/Lean harness、DB schema 起手、commit 協議、Builder（無 agent） | CLI 餵手寫 Lean theorem → `proved` |
| **P2** | Decomposition | Backward agent、cascade、scheduler 雛型、validator | 2–3 層拆解的小 theorem 從零證完 |
| **P3** | Cache | Search/Dedupe subsystem、IH-trap 偵測、`blocked_pipelines` | 重複 sub-Goal 不重攻、IH-trap 提前抓到 |
| **P4** | Conjecture | Counterexample（Evolution atomic）、Refuter、`status`/`answer_data` 全線、cancellation 白名單、silver→gold 升級 | 一批 unknown 命題（含真/假各一）系統自證或自反 |
| **P5** | Construction | continuous task runtime、ConstructionSearch、Evolution continuous、checkpoint 協議、`T_pause_max` | 解 4×4 Hadamard 矩陣 construction |
| **P6** | Library + Multi-Problem | `library_index`、promotion（三類）、global reactor、META.md axiom basis、`trust_set` kind、cross-Problem import | 兩個 Problem，P1 lemma 在 P2 重用 |
| **P7** | Smarts | Forward、Strategist 升級（LLM 信號）、Generalizer Level 2 | 同 problem 啟用前後 search efficiency 對照、auto-generalize |

## Demo cut 原則

- 每 phase 必須能獨立跑通一個具體 demo，輸出可被人類肉眼判斷對錯
- 不在當前 phase 範圍的能力**用 stub**（明確標註）
- 跨 phase 的依賴只允許「後 phase 依賴前 phase」，禁止反向
- 規格中 `architecture_impl.md` §2.4、§6.5 等舊 phase 編號標示（P1–P3 / P2 / P4+），在 P3 時統一對齊本計畫編號

## Acceptance criteria 格式

每 phase 文件用統一節列出。每條 acceptance 必須：

- 可在當前 phase 結束後就執行的指令 / 測試驗證
- 不依賴未來 phase 的能力
- 量化（次數 / 通過率 / wall-clock 上限）優先於主觀判斷

## Spike 流程

跨 phase 共用 spike 集中在 `docs/spikes.md`（待建）。每 spike：

```
input          要餵的具體輸入
expected       預期觀察到的行為 / 數值
affects        哪個設計參數會被結果影響
phase          哪個 phase 開工前必須跑完
```

P1 開工前必跑 spike（`claude --add-dir` / Mathlib 三公理 audit / lake env lean 並發）見 `phase1_skeleton.md` §Spikes。

## Phase 文件結構

每個 phaseN 文件統一含：

1. **目標**——一段話說這 phase 要解什麼問題
2. **Scope**——in（本 phase 必做）/ out（明確不做）
3. **Demo**——一段具體 demo 描述
4. **Acceptance criteria**——可驗證列表
5. **依賴**——前置 phase + 必跑 spike
6. **引入元件**——新 pipeline / DB table / config / file 結構
7. **任務序列**——建議實作順序，後項依賴前項
8. **測試**——unit / integration / demo
9. **風險與 open questions**

## 跨 phase 規則

以下規則對所有 phase 通用、不重複寫進個別 phase 文件：

- **CI 迴歸 gate**：每 phase release 前 CI matrix 必須跑**所有已完成 phase** 的 pytest 全 pass。實作上 `pytest tests/test_phase{1..N}_*.py`，N = 當前 phase 編號。新 phase 不得引入任何前 phase test 的迴歸；發現迴歸 → 阻擋 release、回頭修
- **DB schema 一次到位**：P1 已建 v3 §9.1 全部 table 與欄位、未用欄位 nullable（codex review #12 決策）。後續 phase **不寫 schema migration**——只是「開始消費既有 nullable 欄位/表」。每 phase 文件 §引入元件 §DB table 段註明本 phase 開始消費哪些欄位
- **Fault injection env hook**：P1 引入 `COMMIT_FAULT`、後續 phase 視需要新增。**總清單見 `docs/dev/test_hooks.md`**——加新 hook 時必須同步更新該檔（避免 collision / 語意 drift）。命名統一 `*_FAULT=mode` 或 `*_MOCK=spec` 或 `*_FORCE=value`、各 phase §引入元件 §Test infrastructure 段列出本 phase 新增 hook
- **CLI forward-compat**：CLI flag 一旦 release 就視為公開介面，新 phase 變更需考慮舊 user / cron / CI 行為。P1→P2 例：`asterism run --once` 預設改 `--daemon`、舊 flag 仍可用

## 不跨 phase 處理的事項

- Lean 證明風格規範
- LLM provider 選型
- UI / dashboard
- Token 成本最佳化
- 部署（CI 迴歸 gate 已列在跨 phase 規則）

這些待框架第一次能跑通整段流程後再回來定。
