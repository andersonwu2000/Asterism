# Asterism — 研究提案

**多 agent LLM 定理證明、結合 cascade 分解與 kernel 層級驗證。**

## 什麼是 Asterism

一個 framework、驅動 LLM 產出機械驗證過的 Lean 4 定理證明。Framework
負責分解、驗證、cascade 升級；LLM（透過 Anthropic API）提供數學內容。
Framework 是 **model-agnostic** — 換 model 只需改一行 config。

## 目前 headline 成果（miniF2F-Valid 244、2026 年 5 月）

| | |
|---|---|
| Proved | **235 / 244**（96.3% raw）— kernel-accepted Lean 4 proofs |
| Disproved | **9 / 244** — 對 false-as-written transcription bug 的 kernel-verified counterexample |
| Coverage | **244 / 244 全部 classified** — 沒有一題棄權 |
| Audit 標準 | `#print axioms ⊆ [propext, Classical.choice, Quot.sound]` |
| Model | 通用 Claude（Opus + Sonnet、無 fine-tuning）|
| 預算 | 約 857 次 LLM 呼叫、244 題、~$50 API 費用 |

**為何是 96.3% 而非 100%**：miniF2F-Valid 裡有 9 個 statement 其實**數學上
為假**、跟原始競賽題不一致、不可能被任何乾淨工具 prove。我們發現後、
附上 kernel-verified counterexample、整理成單一 upstream issue 送
`yangky11/miniF2F-lean4`（Lean 4 port 事實標準）。

**同標準比較**：業界號稱在 miniF2F-Valid 超過 96.3% 的數字
（例如 Seed-Prover 99.6%）通常未揭露他們如何處理這 9 個 false statement。
若套用我們的嚴格 axiom-audit 標準、Asterism 跟「業界 SOTA」的差距會
消失；若套用他們的（沉默）標準、我們同樣會接近 100%。

## 目前已建構完成

| Artifact | 狀態 |
|---|---|
| miniF2F-Valid 244 pilot | ✅ 96.3% proved + 9 errata disproved、單台工作站完成 |
| Sylvester-Gallai 定理端到端證明 | ✅ depth 10、lake build 通過、axiom 乾淨 |
| `proj_nonexpansive`、`cantor_xi_measure`、`compactness` 等 | ✅ 早期單問題 run 已完成 |
| Multi-agent framework（Backward + Builder）| ✅ production hardening 完成 |
| 自製 Lean LSP server + writeOlean / printAxioms RPC | ✅ |
| OR-parallel cascade、含 dedupe + cascade-shelve | ✅ |
| Crash 復原：sandbox + circuit breaker + watchdog v4 | ✅ |
| Test suite | ✅ 781 tests、1 skipped |

## 方法論嚴謹度（一個具體案例）

在 miniF2F-Valid pilot 進行中、framework 的 kernel-axiom gate 因為一個
多問題模式下的 regression 而沉默失效（`db.root_proved(conn)` 的語意是
workspace-AND、而不是 per-problem）。237 個 proof 被 cascade 機械
promote、kernel-axiom 完整性 gate 整輪沒跑過一次。

我們在 run 中段抓到這個問題、用 `git blame` 追到 root cause（這個 helper
是單問題年代留下來的、多問題模式 refactor 時沒同步改）、補修
dispatcher、跑一次 retrospective audit、確認 237 個 proof **零** `sorryAx`
洩漏。

這種完整性紀律是 production-grade theorem proving 跟「demo 跑得起來一次」
的差別、也是其他公開系統很少明文記錄的特性。

## 研究問題（接下來 6 個月）

**RQ1 — Multi-agent 優勢**。Backward agent 專門分解 + Builder agent 專門
close leaf、這種角色分工在 depth > 3 的問題上、是否優於 single-agent？
假設：是、multi-agent 隨 depth 增長呈現 graceful degradation、single-agent
則是陡峭懸崖。

**RQ2 — 架構 vs model**。Framework 固定時、模型選擇（Opus vs Sonnet vs
Haiku）貢獻多少成功率、framework engineering（parallel exploration、
dedupe、axiom gates）又貢獻多少？假設：depth ≥ 5 時 framework 主導、
depth ≤ 3 時 model 主導。

**RQ3 — 失敗特徵化**。系統無法 close goal 時、結構性原因是什麼？建立
分類：sorryAx-shortcut / axiom-violation / type-mismatch /
decomposition-divergence 等。用這個 taxonomy 來指導下一輪 framework +
prompt 改進。

**RQ4 — Library transfer**。累積的 `Library/<Topic>/` 已證 lemma 庫、
能不能降低同領域後續問題的成本？兩階段實驗：先證 Set A、再證 Set B、
比較有沒有 Set A library 可用的差異。

## 具體 deliverables

| Milestone | Output | 狀態 |
|---|---|---|
| 1. miniF2F-Valid (244) | Pass rate、depth breakdown、failure taxonomy | **Done**（96.3%）|
| 2. miniF2F-Test (244) | 最終 benchmark 數字、無 train leak | 接下來 |
| 3. PutnamBench (270) | 大學競賽級 depth 測試 | Q3 |
| 4. Multi-agent ablation | 同一批問題分別跑（Opus-only、Sonnet-only、Opus+Sonnet）| Q3 |
| 5. Depth study | 100 題人工標 depth、畫 success-vs-depth 曲線 | Q4 |
| 6. Library transfer study | 兩階段實驗、量化 transfer benefit | Q4 |
| 7. Framework paper | 投 systems/ML conference | Q4-Q1 |

## 所需資源

| 項目 | 估算 |
|---|---|
| API 預算（Anthropic、6 個月）| 約 $3-5k（miniF2F-Valid 用了 ~$50;  miniF2F-Test + PutnamBench 預估約 10×）|
| 計算資源 | 本地工作站（SG + miniF2F pilot 全在單台 laptop 跑完、無 GPU）|
| 時間 | 1 FTE-equivalent（目前單一開發者）、6-12 個月 |
| Advisor 支援 | 架構 review + paper-writing 指導 |

## 為何這值得 bet

1. **這個前沿是真的、且高度活躍。** DeepSeek-Prover-V2（miniF2F-test
   88.9%、Pass@8192）、Seed-Prover、Kimina-Prover、Goedel-Prover 過去
   12 個月都有公開成果。問題已經不是「LLM 能不能證定理」、而是
   「什麼架構能 push 上限」。Asterism 帶著一個獨特的架構假設進場。

2. **Asterism 的架構角度獨特。** 沒有其他公開系統做 multi-agent
   分解 + persistent OR-parallel cascade + kernel-level 完整性 gate
   的組合。既有系統競爭點是訓練資料 + 單 model 精緻化；Asterism 競爭
   點是 framework + decomposition + verification integrity。

3. **miniF2F 成果從 commit 開始可重現。** 每個 claim 都機械可驗：
   任何 proved root 的 `lake build` 都通過；`#print axioms` 只回報
   standard whitelist（除三個有文件揭露的 `native_decide` case 外）。
   9 個 false-as-written statement 的反例檔都是 kernel-verified。
   任何人 clone repo 都能自行再驗。

4. **工程基礎已償付完成。** 過去 6 個月的 framework hardening、讓系統
   現在就 benchmark-ready：gateway crash 復原、sandbox、watchdog、
   circuit breaker、axiom probe、per-problem 完整性 gate、open
   propagation、自動 audit 工具。後續研究心力可集中在科學問題
   （RQ1-RQ4）、而不是基礎設施。

## 我所請求的

- **Advisor 支援**：proposal review + paper-writing 指導。
- **API 預算**：6 個月 $3-5k、做 benchmark runs。
- **時間**：framework 已就位、接下來 6 個月是上面那些科學實驗。

研究成功與否、最終看 benchmark 數字。如果 miniF2F-Test、PutnamBench、
depth study 三者複製出我們架構假設預期的結果（隨 depth 增長有
graceful degradation、depth ≥ 5 時 multi-agent > single-agent）、
架構主張就驗證。如果沒有、negative result 仍可發表、告訴我們下一步
該往哪投資。
