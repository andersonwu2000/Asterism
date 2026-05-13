# Asterism v2 — Current Status

更新於 **2026-05-13**、HEAD `562d8a9`、796 unit tests green / 1 skipped。

## TL;DR — miniF2F-valid pilot done

- **235 proved / 244 (96.3% raw)**
- **9 shelved**、全部是 kernel-verified source bug（每個附 disproof.lean、`#print axioms` clean）
- 「provable subset」上 235/235 = **100%**
- 1 個 Defs.lean intervention（imo_1993_p5、minimal `goldA` hint 後 agent 自己證、ledger 紀錄）
- 1 個 adapter bug fix（4 個 root 沒 `open Real`、修了 reset 後都 proved）
- Total ~916 LLM invocations / 244 problems（avg 3.75）、~Pass@4 budget 等價
- Daemon idle exit clean、無新 bug pending

## 對比業界（miniF2F-valid 244）

| Framework | Pass / Score | Budget | Lean | Specialized? |
|---|---|---|---|---|
| HyperTree (2022) | 58.6% | tree search | Lean 3 | yes |
| DeepSeek-Prover-V2 671B | 100% (test 88.9% @ Pass@8192) | Pass@8192 | Lean 4 | yes |
| Seed-Prover (ByteDance, 2025) | 100% | Medium budget、days/problem、>1000 line proofs、**static fix subset** | Lean 4 | yes |
| **Asterism (我們)** | **96.3% (235/244, raw)** | ~3-4 spawns/problem (Pass@~4 equiv) | Lean 4 | **no — general Claude** |

額外貢獻：**9 個 kernel-verified counterexample 公開、Asterism 不靜默修 statement**（contrast Seed-Prover "manually added or corrected"）。

## Source-bug errata（9 個 disproof commits）

`docs/errata/minif2f/`、每個 `<name>_disproof.lean` 含 `theorem disproof : ¬ stmt` + `#print axioms` showing `[propext, Classical.choice, Quot.sound]`（no sorryAx）。

| Problem | Bug class | Commit |
|---|---|---|
| amc12a_2002_p21 | quantifier scope（recurrence ∀ n ≥ 2 漏 u₂ u₃）| - |
| mathd_numbertheory_126 | minimality scope |  |
| aime_1988_p3 | 缺 x > 1 precondition、log convention |  |
| aime_1984_p5 | log_neg_eq_log、sign 不約束 |  |
| amc12a_2020_p13 | ℕ-division trivialize |  |
| imo_1962_p4 | answer-set step π/6 太細（FB-research 已修、yangky11 沒同步）|  |
| mathd_algebra_282 | ℕ-division 在 cube root |  |
| mathd_algebra_433 | 答案值錯（38 vs 79）| afa23bf |
| imo_1967_p3 | `∏` body precedence 截斷 subtraction | ff8f187 |

5 個是 unique-to-this-run discovery、無前例 GitHub issue（audited via openai/miniF2F + yangky11/miniF2F-lean4）。

## Defs.lean intervention（誠實揭露、影響 1 個 proved）

`docs/errata/minif2f/defs_intervention_ledger.md`、紀錄人工介入。

| Problem | Helper | Outcome |
|---|---|---|
| imo_1993_p5 (g642) | 1 行 `noncomputable def goldA (n : ℕ) : ℕ := ⌊n·φ⌋.toNat`（無 docstring / 無 lemmas）| **proved**、agent 自己 invent `f n = goldA (n+1) - 1` shift、找 Beatty 對應、證 Hofstadter identity（IMO-tier）|
| amc12a_2009_p25 (g596) | `noncomputable def θ : ℕ → ℝ`（Fib angle、tan-addition / Pisano-period）| proved |

兩個 case 用 minimal hint（一行 def）、agent 補完整 proof structure。這是 Phase 2 "Theorist" pipeline 的 proof-of-concept。

## Adapter / framework bug fixes（這次 run 修的）

- **cmd_init 漏帶 `open Real`**：4 個 minif2f problems (aime_1997_p11、imo_1962_p4、imo_1965_p1、imo_1966_p4) Defs.lean 有 `open Real Nat Topology Rat` 但 Root.lean 沒、`π` etc. 變 auto-bound implicit、theorem 不可證。手動加 open + reset、全部之後 proved。Followup task #108。
- **backward apply_edit race**（race fix commit `15b3d94`、之前已修）
- **assembly gate**（防 strategy patch body `:= by sorry`、commit `0e270a8`、之前已修）

## Framework follow-ups (tasks)

| # | 主題 | 為何 |
|---|---|---|
| 101 | 延後 `insert_strategy` 到 quota check 後 | 8587 quota-rejected dead strategies / TREE.md 雜亂、root cause |
| 102 | TREE.md 把 dead strategies 分類顯示 | cosmetic、quota dead 應 collapse |
| 103 | 連續 quota_exhausted exponential backoff | quota throttle 期省 API |
| 104 | 完整 miniF2F-244 final report 給教授 | 待整理（用此 STATUS + ledger）|
| 105 | 草擬 upstream miniF2F errata issue body | 9 個 disproof → 1 個 issue 集中上報 |
| 106 | Phase 2 Theorist Pipeline 設計 doc | imo_1993_p5 + amc12a_2009_p25 已 prove this works |
| 107 | (done via #104 一起)驗證 imo_1993_p5 + amc12a_2009_p25 ledger | |
| 108 | cmd_init 自動繼承 Defs.lean opens | 防 4 個 problem 同類 transcription accident |
| 109 | gateway.workers 配置實驗（已 trial workers=4 pool=8、tool latency p50 大降）| optimize hot_rate |
| 110 | spawn timeout 扣除 LSP slot wait 時間 | agent budget 公平 |
| 111 | gateway slot soft-reservation 增加 hot_rate | 同 cluster |
| 112 | dedupe 擋 shelved-equivalent sub-goal | imo_1990_p3 觀察 |
| 113 | forbidden_lemma 擴展涵蓋 shelved 子目標 | imo_1990_p3 stale olean root cause class |
| 114 | imo_1990_p3 rollback (DONE、是 false alarm)|  |
| 115 | **重要**：Lake olean cache 或 daemon-idle-exit kernel audit | catch class of stale-olean sorryAx leak |

## imo_1990_p3 case study (#114 → #115)

- Framework cascade 標 proved
- `#print axioms main` 第一次回 `[propext, sorryAx]` → 我手動 rollback shelve
- 排查：15 transitive olean stale（source > olean mtime）— source 已 sorry-free、olean 是更早 revision build 的 sorry 版本
- 刪 stale olean、force rebuild、`#print axioms main` 回 `[propext, Classical.choice, Quot.sound]`、proof 真乾淨
- revert 回 proved (commit `562d8a9`)
- **真正 framework bug**：multi-problem run 下 `library.maybe_promote → axiom_probe` 因 `root_proved=False` 永不跑、stale olean 一旦發生無 detection
- **修法 #115**：daemon idle exit 前對 proved roots force rebuild + #print axioms

## Run config（這次的）

- HEAD `562d8a9`
- `Asterism.yaml`: pool=8, gateway.workers=4
- Backward: Opus 4.7、Builder: Sonnet 4.6
- spawn_timeout 900s、shelve_threshold 5、trap_check 660s、silence_threshold 300s

## Phase 2 next steps（建議）

1. **#115 daemon-exit axiom audit**（必做、framework correctness gap）
2. **#108 cmd_init opens propagation**（防 transcription bug recurr）
3. **#106 Theorist Pipeline 設計 doc**（imo_1993_p5 / amc12a_2009_p25 提供 design data point）
4. **#105 errata upstream report**（先送 yangky11/miniF2F-lean4、9 個一次性）

## 歷史 SG / PN（這次未動）

之前 single-problem run 的 result stable、commit 上未動。完整 SG/PN/IZ 證明在 `Problems/<name>/` 下、跟 mini F2F 兼容並行。
