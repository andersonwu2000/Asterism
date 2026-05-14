# Asterism — long-bet strategy

**Status**：living document、月更。
**Horizon**：2-3 年（到 ICLR 2028 / NeurIPS 2028 那一輪）。
**最新更新**：2026-05-14、HEAD `c462e3f`。
**這份文件不是**：對外提案（→ `docs/proposal/`）、handoff（→ `docs/STATUS.md`）、
方法論（→ `docs/CLAUDE.md`）。
**這份文件是**：給未來自己對齊用 — 「2-3 年後 Asterism 還能不能算 SOTA 一員、
靠什麼撐」。

---

## §0. 當前位置（2026-05-14）

一句概括：**LSP-shipped、miniF2F-Valid 96.3%（+9 kernel-verified errata）、proposal 已
寫給教授、framework 自我修復過一次重大 correctness gap、bridge lemma layer 是
唯一 in-design item**。

關鍵 artifact：

| Artifact | 證據 |
|---|---|
| LSP gateway 4 worker、Mathlib-warm | `Tooling/lsp/gateway.py`、`Tooling/lsp/lifecycle.py` |
| miniF2F-Valid pilot | `docs/internal_report_minif2f_pilot.md`、commit `ba786e9` |
| 9 個 upstream errata（ready-to-post）| `docs/errata/minif2f/upstream_issue.md` |
| Multi-agent（Backward Opus 4.7 + Builder Sonnet 4.6）| `Tooling/pipeline/{backward,builder}.py` |
| Framework correctness 自發現 + 修復 | `147bec5` |
| Test 規模 | 781 unit tests green |
| Proposal 全套（中英）| `docs/proposal/{proposal,proposal_zh-tw,comparison,demo_script,sg_cascade}.md` |

---

## §1. 2-3 年領域預測（給戰略推論用、不是事實）

從 2025-10 到 2026-05 觀察到的領域 trajectory、外推到 2028：

| 趨勢 | 已發生 | 2027-2028 預測 |
|---|---|---|
| Multi-agent orchestration | HILBERT、Ax-Prover、Prover Agent、Seed-1.5、MA-LoT 全在做 | 變成 default、單模型 baseline 退出主流 |
| RL from Lean feedback | Seed-1.5、Leanabell-V2 啟動 | 主流訓練手段、新 paper 不做 RL 不敢發 |
| Verifier-in-the-loop（不是 post-hoc） | Leanabell-V2 開始 | 標準配備、像 today 的 Pass@N |
| Tool-use 接 Lean via MCP | Ax-Prover 用 MCP-Lean | MCP-Lean 變 protocol standard、跨團隊互通 |
| miniF2F 飽和 | HILBERT 99.2%、miniF2F-v2 出 | miniF2F 完全死、PutnamBench 也飽和、新 benchmark 出（grad / PhD level）|
| Cross-problem memory / experience transfer | Seed-1.5 宣稱、不開源 | 競爭點轉到「誰的 memory 規模大 + 跨 domain 強」 |
| Forensic / failure analysis | 沒人系統做 | **空白**、有機會 |
| Open-source frontier model 規模 | Goedel-V2 32B、Seed-Prover 1.5 不公開大小 | 開源 70B-200B、閉源訓練模型 1T+ |
| 訓練資料來源 | mathlib + autoformalize + competition archive | autoformalize 機器產 + cross-system 翻譯（Coq/Isabelle 互轉）|
| Benchmark integrity（axiom audit、errata 揭露）| 你的 pilot 是第一個系統做 | 還是沒人做、業界繼續用「Pass rate」掩蓋 |

**最重要的兩個 trend**（影響 Asterism 最深）：

1. **Multi-agent 變主流 → Asterism 的架構優勢 commoditize**。proposal 的「architectural angle is unique」claim 在 2027 會弱化。要在 multi-agent 之上找新差異化。

2. **Benchmark 整個 layer 在變** — miniF2F 死、PutnamBench 飽和、新 benchmark 還沒共識。**空窗期是定義權的機會**。

---

## §2. Asterism 三個耐久 moat（2-3 年仍成立）

### Moat A — Forensic dataset

**為什麼耐久**：別人要做要重新跑 N 年、累積每題 dead_attempts + LESSONS + dispatcher event。Seed-1.5 paper 宣稱有「experience accumulation」但不開源、業界沒第二個系統公開這層資料。

**現狀**：
- DB 已有 9365 strategies（含 quota-rejected）、~857 真實 LLM invocations、dead_attempts 表完整
- `LESSONS.md`、`BRIEF.md`、Context.md sections 全程紀錄
- 跨 problem 規模還小（cantor、PN、SG、IZ、proj、compactness、wilson、imo_1990_p3 + miniF2F 244）

**強化動作（2027 前）**：
1. 把 forensic data 標準化成 HuggingFace dataset：每個 attempt 含 (problem, depth, strategy, tactic_history, outcome, error, recovery)
2. 規範化到 1000+ problem 規模（miniF2F + PutnamBench + 自選研究級）
3. 寫一篇 dataset paper（NeurIPS Datasets and Benchmarks track 是合理 venue）
4. 釋出 dataset license 寫清楚「用於訓練的 attribution 要求」— 防被 Seed / DeepSeek 吸去訓練不認帳

**2-3 年內競爭者怎麼威脅？**
- ByteDance / DeepSeek 跑大規模 RL、會累積自己的 forensic、但**不開源**。Asterism 開源 forensic 在學界價值高、產業價值低、剛好錯位避戰。
- 學界團隊（Apple ML、Microsoft Research）可能跟進、但他們會選 Coq / Isabelle 不一定 Lean 4、互不正面衝突。

**證據強度**：HIGH。已有 baseline、規模問題不是技術問題、是時間問題。

### Moat B — Integrity-first methodology

**為什麼耐久**：業界默契不做 axiom audit + 不揭露 false statement 處理 + 不上報 errata。這是**文化問題、不是技術問題**、改起來慢。

**現狀**：
- 9 個 kernel-verified errata、ready-to-post issue
- native_decide policy 明文揭露（§6 internal report）
- workspace-AND gate bug 自我發現 + 自我修復 + retrospective audit、完整透明
- `#print axioms ⊆ whitelist` 是 cascade promotion gate 強制條件

**強化動作（2027 前）**：
1. 把 axiom audit 變 Asterism Benchmark 一部分：「跑這個 framework 就要 report 兩個數字、寬鬆 / 嚴格」
2. 在 miniF2F-Test、PutnamBench 上重做 errata detection、繼續上報、累積「Asterism 找了 N 個 benchmark bug」signature
3. 寫一篇 methodology paper：「Integrity gaps in current LLM theorem prover benchmarks」— 對所有競爭者公開挑戰「能不能在我們的標準下重跑你的數字」
4. 推進「在 same-standard 下、Asterism 數字 vs SOTA 數字」的可比性

**2-3 年內競爭者怎麼威脅？**
- Apple / Microsoft Research 可能 adopt（學界共鳴）、但他們 adopt = Asterism 方法論勝利、不是 Asterism 輸
- 中國團隊（DeepSeek / ByteDance / Moonshot）大概率不 adopt、因為他們宣稱 SOTA 數字會被打折、有 disincentive
- **真實風險**：學界自己不在乎、繼續用 Pass rate、Asterism 變孤芳自賞

**證據強度**：MEDIUM-HIGH。已有 9 個 errata 是 concrete proof、需要外推到 multi-benchmark。

### Moat C — Long-horizon research-style problem class

**為什麼耐久**：所有現有 benchmark 都是 **單命題、< 10 line statement、< 5 depth、無 informal context**。Asterism 跑的 SG / cantor / PN / Phase 2 Theorist 目標的問題是 PhD-research 級、需要 manifest / BRIEF / LESSONS、跨多個 strategy file。這個 territory **目前沒人耕**。

**現狀**：
- SG（depth 10）、cantor xi、PN、compactness、gen_generates、inner_zero_iff_smul、proj_nonexpansive — 6 個 single-problem run 成功、proved + library-archived
- imo_1993_p5 + amc12a_2009_p25 跑通「minimal Defs.lean hint → IMO-tier proof」
- bridge_lemma_layer 設計中、目標是讓 cross-product polynomial 工作集中、減少 sub-goal 爆炸

**強化動作（2027 前）**：
1. **定義 Asterism Benchmark v1**：cantor / SG / PN + 20-30 個 PhD-level theorem、標準化 manifest 格式、定 baseline difficulty
2. 邀請 Goedel-V2-8B / DeepSeek-Prover-V2-7B 接 Asterism 跑同 benchmark — 證「在這個 problem class 上、Asterism framework + 任何 backend > backend solo」
3. paper：「A benchmark for long-horizon multi-step theorem proving」、定義評估維度（depth、informal context required、cross-lemma reuse）
4. 跟現有 Fate-H / Fate-X（Seed-1.5）區分：他們是 PhD-LEVEL statement、我們是 PhD-LEVEL workflow

**2-3 年內競爭者怎麼威脅？**
- 大廠出 benchmark 競品（Fate-X / 類似）、可能定義權被搶
- 解法：早 1-2 年定義 + 釋出、佔 first-mover
- 風險：Apple HILBERT 已經在 PutnamBench 走 70%、會直接跳 Fate-H、繞過 Asterism 的長 horizon 定義

**證據強度**：MEDIUM。需要 bridge_lemma_layer 落地後、SG 級問題效率上來、才能 scale 到 20-30 題 benchmark。

---

## §3. 三個 6-12 月會被追上的 short hedge（不依賴）

這些別當 moat、是當前的 traction、但很容易被別人複製：

| Hedge | 為什麼會被追上 |
|---|---|
| LSP / MCP 接 Lean | Ax-Prover 已有、HILBERT 用 Kimina Lean Server、變 commodity |
| Multi-agent decomposition | 整個 2025-10+ 領域都這做、Asterism 沒比 HILBERT 突出 |
| 96.3% miniF2F-Valid | benchmark 飽和、明年 99.x% 全家都有 |
| Crash recovery / sandbox / circuit breaker | 是 engineering quality、不是研究 contribution |
| Library promotion 跨 strategy alias | dedup 機制、Seed-1.5 / HILBERT 可加類似的 |

這些是「**現在跟得上 SOTA 的證據**」、但 2027 不會繼續是差異化。

---

## §4. 戰略五大長 bet（2-3 年定方向）

### Bet 1：把 forensic dataset 做成領域引用標準（NeurIPS D&B 2027 / 2028）

- 目標：「想做 LLM theorem prover failure 分析 / RL training data 的、都得來引 Asterism dataset」
- KR：1000+ problem 規模、10000+ attempt traces、HF dataset 下載 1000+
- 依賴：先把 miniF2F-Test 跑完、PutnamBench 跑完、20-30 PhD-level problem 跑完、規範化 schema

### Bet 2：用 general Claude 反證「框架價值」、不是「模型價值」

- 目標：所有 Asterism 數字、都用同 general LLM 多次重跑、公開 distribution；同時跑 Goedel-V2-8B 當 alternative backend、比較 framework vs Goedel-solo
- KR：產生「framework 加成 X%」公開可重現數字、別人引用時必須選一個立場
- 依賴：Goedel-V2 backend spike（design 中）、ablation harness 寫出來

### Bet 3：把 axiom audit + errata detection 變 benchmark integrity 標準

- 目標：未來 prover paper 跑 miniF2F、reviewer 會問「你的 9 個 false statement 怎處理」 — 領域共識
- KR：上 NeurIPS / ICLR position paper 1 篇、被 HILBERT / Seed / Goedel 後續版本引用
- 依賴：errata issue 送出、看 yangky11 接受率、累積 cross-benchmark errata（PutnamBench 也找）

### Bet 4：定義 long-horizon benchmark + 邀請 cross-team 來跑

- 目標：「Asterism Benchmark」是評估 long-horizon prover 的 reference suite
- KR：20-30 problem、HF 上 hosted、3+ 外部 team 用過（Goedel-LM、ByteDance Seed、Apple ML 任一）
- 依賴：bridge_lemma_layer 落地（SG 效率不夠）、Phase 2 Theorist（helper def autonomy）

### Bet 5：framework integrity 變科學量化目標

- 目標：「框架 X 對 prover Y 的 integrity 加成」是可發表的量化研究維度
- KR：寫一篇方法論 paper、定義 framework integrity 量化方式（kernel-purity rate、sorryAx leak rate、errata detection rate、cross-problem transfer rate）
- 依賴：Bet 2 的 ablation 數據 + Bet 3 的方法論成熟

---

## §5. 風險登記

### R1 — 大廠飽和：底層模型升級把整個領域刷掉

- 場景：GPT-6 / Claude 5 / Gemini 3 出來、單模型 Pass@1 在 PutnamBench 95%、框架幾乎無 marginal 貢獻
- 機率：MEDIUM（base model 進步快、但 2-3 年內不會 saturate Fate-X / 研究級）
- 緩解：Bet 4（定義 long-horizon benchmark）+ Bet 2（用 general LLM 反證框架）
- 早期訊號：注意 Claude / GPT 重大版本 release、跑 miniF2F-Test / PutnamBench、看 single-shot Pass@N 跳幅

### R2 — 同質化：Apple / ByteDance 把 multi-agent + cross-problem memory 都做了

- 場景：HILBERT v2 加 forensic、Seed-Prover 2.0 開源 cross-problem dataset、Asterism 失去 1-2 個 moat
- 機率：MEDIUM-HIGH（這幾家有資源、跟得上趨勢）
- 緩解：開源優勢 + 學界 alliance + integrity-first 文化定位（Bet 3）
- 早期訊號：HILBERT、Seed-Prover paper 提到 dataset release / experience accumulation 細節時警覺

### R3 — bridge_lemma_layer 不解、SG-class 問題效率不到位

- 場景：bridge lemma 設計 3 個方向都實作但沒用 / SG / 類似題目仍要 100+ sub-goal、Asterism 在 PhD-level scaling 失敗
- 機率：MEDIUM（設計還沒下、不確定）
- 緩解：先在 SG retry 試各種 bridge 方向、看 (a) Manifest section / (b) prompt / (c) dedup 哪個給 LOC 折扣最大
- 早期訊號：parcadei 的 ~1000 LOC vs Asterism SG 的 3× LOC、實證 measurement

### R4 — 學界冷淡：方法論 paper 沒人引

- 場景：Bet 3 / Bet 5 的 methodology paper 投了、reject 或 accept 後 0 引用、領域繼續用寬鬆 Pass rate
- 機率：MEDIUM
- 緩解：先送 venue 信譽強的（NeurIPS / ICML 主會 vs Workshop）、找 advocate（教授 / Lean community key person）
- 早期訊號：proposal 投出後教授反饋、第一篇 paper 投稿 review

### R5 — 個人 bandwidth：1 FTE 撐不住 5 個長 bet

- 場景：proposal 寫的「1 FTE 6-12 month」實際只夠 2 個 bet
- 機率：HIGH（這是現實）
- 緩解：按優先序鎖、每個 milestone 重新評估、不要平行推進所有
- 早期訊號：6 個月後回看、5 個 bet 哪個 KR 達成、哪個 0 進度

---

## §6. 6-month 優先序（從 5 個 long bet 出發、定 short-term 動作）

按「對 long bet 影響 × 可行性」排序。下次 review 在 2026-11。

### 高優先（必做）

1. **bridge_lemma_layer 設計鎖定 + 落地**（影響 Bet 4 + R3）
   - 從 a/b/c 三方向選一個（或組合）、6 月底前 PoC、SG retry 測 LOC 折扣
   - 跟下面 PutnamBench Phase 1 sanity 同步並行：Phase 1 結果驅動 bridge 設計
2. **PutnamBench 探水 → 跑滿**（影響 Bet 1 + Bet 3 + R3 訊號）
   - Phase 1：50 題 sanity（~$60、1 週）— 看 failure mode、bridge lemma 痛點實證
   - Phase 2：依 Phase 1 結果分歧
     - Phase 1 ≥ 40% → 跑滿 270 題（~$300、3-4 週）、累積 forensic + 業界對比
     - Phase 1 < 40% → 凍結 PutnamBench、優先解 bridge_lemma_layer、修完再 Phase 2
   - **不跑 miniF2F-Test**：你的 9 errata = 3.7% 缺口、Test 預期結果跟 Valid 同形（~95% proved + ~5% errata）、敘事重複、$200-300 換不到新洞察
   - 業界 anchor：Seed-1.5 88%、HILBERT 70%、Asterism 預期 40-65%（general Claude vs fine-tuned prover、合理區間）
3. **upstream errata issue 送出**（影響 Bet 3）
   - 已 ready-to-post、等 commit + 確認、不該拖

### 中優先（推進）

4. **Goedel-V2-8B backend spike**（影響 Bet 2）
   - 小規模 PoC、不要 production-harden、目標：能 swap model run 子集（PutnamBench 50 題 sanity 重跑、看 framework-only 加成）
5. **Phase 2 Theorist Pipeline 設計 doc**（影響 Bet 4、task #106）
   - helper def autonomy、imo_1993_p5 已證 framework-assist 路有用
6. **Forensic schema 規範化**（影響 Bet 1）
   - 把 dead_attempts + LESSONS + dispatcher events 整理成 HF-friendly schema、不一定要 release、先內部對齊

### 低優先（觀察）

7. **miniF2F-v2 244 題 anchor**（影響 Bet 3）
   - 等 Bet 3 methodology paper 起草時再跑、~$20、作為「即使 cleaned-up benchmark 上、嚴格 audit 仍適用」的補充證據
   - 現在跑沒人比、留到 paper 上下文有意義時
8. **方法論 paper outline**（影響 Bet 3 + Bet 5）
   - 還早、但提早寫 outline 對齊敘事
9. **領域 scan 持續**（影響 R1 + R2）
   - 每 2 個月 sweep arxiv + HF、追蹤新 prover、更新 §1 預測

---

## §7. 下次 update（給未來 session 對齊用）

預計 2026-06-14 更新。檢查清單：

- [ ] §0 commit hash / 數字是否仍是最新
- [ ] §1 trend 預測有沒有被新事件打臉（新 prover release、新 benchmark）
- [ ] §2 三個 moat 規模有沒有實際增長（forensic data 規模？errata 數？）
- [ ] §4 五個 bet 的 KR 進展
- [ ] §5 風險訊號有沒有觸發
- [ ] §6 優先序前 3 名是否仍最該做

如果上面有 > 3 項變化、整份重寫一輪、不只是改數字。

---

## §8. 不寫進對外 proposal 的反思

這節給未來自己留底、不對外。

1. **proposal §"Asterism's architectural angle is unique" 在 2027 會弱化** — multi-agent 已是主流。proposal 投出時要 anticipate reviewer 質疑、準備「我們的 multi-agent 跟 HILBERT 差在 cross-problem memory + integrity audit + general LLM 三點」這個答覆。

2. **PutnamBench 預期 40-65%、會被嚇到** — 從 96.3% 跳到 50% 心理上會難看。要記得：那是「general Claude vs fine-tuned 大廠 prover」的真實差距、不是框架退化。把每個 failure mode 當 bridge_lemma_layer 設計輸入、別當士氣打擊。（決定跳過 miniF2F-Test：你的 9 errata = 3.7% 缺口、Test 預期是 Valid 故事複製、$200-300 不換新洞察、PutnamBench 是更高 ROI 的下一步。）

3. **bridge_lemma_layer 是真正的技術風險點** — 沒解、SG-class 跑大 benchmark 會 timeout / quota exhaust。3 個方向都試一下、選好的、不要 over-engineer。

4. **教授提案如果通過、第一筆 API 預算用在哪要想清楚** — 不要全押 miniF2F-Test、留 1/3 給 cross-problem memory ablation (Bet 2 + RQ4)。

5. **proposal 不提 forensic dataset 是對的**（教授版焦點要少）、但內部要把 Bet 1 當第一順位 — 因為這是最防複製的 moat、其他 4 個 bet 都比較容易被追上。
