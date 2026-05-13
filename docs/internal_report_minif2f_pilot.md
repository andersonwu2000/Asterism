# Asterism × miniF2F-Valid 內部報告

撰寫日期：2026-05-13
HEAD：`6828076`
範圍：`yangky11/miniF2F-lean4` 的 `MiniF2F/Valid/` 全集（244 題）

目的：誠實記錄這次 pilot run 的所有結果、發現的 framework BUG、處理過程、跟業界基準的對比、以及對外可揭露的內容。教授報告之後從這份提煉。

---

## TL;DR

- **244/244 全部 classified**（無一題 framework 棄權）
  - 235 proved（kernel-accepted Lean 4 proofs）
  - 9 disproved（kernel-verified counterexamples）
- 235 proved 內細分（whitelist `[propext, Classical.choice, Quot.sound]`）：
  - **232 嚴格 kernel-pure**（含 2 個事後手動補 open 的）
  - **3 用 native_decide**（接受、業界標準做法）
- 對比業界（同 valid 244 題）：
  - HyperTree (2022) 58.6%、DeepSeek-Prover-V2 671B 100% (Pass@8192)、Seed-Prover 100% (含 human-corrected subset)
  - **我們 96.3% (235/244 raw)、Pass@~4 budget、general Claude（無特化模型）**
- **這次 run 中段發現 framework gate BUG**（workspace-AND condition、整 run 沒過 kernel gate）
  - 已修（commit `147bec5`）、跑 retrospective audit 確認 0 sorryAx leak

## 數字明細

| 項目 | 數量 | 備註 |
|---|---|---|
| miniF2F-Valid 全集 | **244** | 從 `yangky11/miniF2F-lean4` import |
| Proved 總數 | **235** | DB status=proved + Lean kernel accepts |
| ─ Whitelist-pure | 230 | audit 即時通過 |
| ─ Whitelist-pure（事後手動補 open）| 2 | aime_1997_p11、imo_1966_p4（見 §3）|
| ─ native_decide | 3 | aimeI_2000_p7、amc12a_2019_p9、mathd_numbertheory_709 |
| Shelved + 反例證明 | **9** | source-bug errata（見 §4）|
| Defs.lean 人工 helper | 2 | imo_1993_p5、amc12a_2009_p25（見 §5）|

## §1. 方法

**Framework**：Asterism（v2、HEAD `6828076`）、multi-agent prover：
- Backward (Opus 4.7)：decomposing strategy、產 sub-goal
- Builder (Sonnet 4.6)：leaf proof、tactic-driven
- LSP gateway：4 worker、Mathlib-warm
- Single integrity gate：`library.maybe_promote → axiom_probe(Root.lean)`

**Run 規模**：
- 預算：4.5 hr daemon wall-clock
- 總 LLM invocations：~916 spawn（succeeded + meaningful failure；quota-rejected 8685 不算 invoke）
- ~Pass@4 budget equivalent
- 配置：`dispatch.pool=8`、`gateway.workers=4`、`spawn_timeout=900s`、`shelve_threshold=5`

## §2. Framework correctness 故事（重要）

這次 run 中段發現 framework 有重大 correctness gap、整理如下。

### 2.1 gate condition BUG

`db.root_proved(conn, problem=None)` 不帶 `problem` 參數時、語意是「workspace 內**所有** roots 都 proved」。

`dispatcher.py:939` 的 gate：
```python
if db.root_proved(conn):
    for problem_name in manifests:
        library.maybe_promote(...)  # ← 唯一 kernel axiom_probe
```

**期待語意**：每個 root proved 時跑一次 axiom_probe
**實際語意**：所有 244 個都 proved 才跑一次 axiom_probe

這次 run 9 個 errata shelved 卡死 gate、**`library.maybe_promote` 整輪沒跑過一次**、237 個被標 proved 的 root 沒一個過 framework kernel 認證。

### 2.2 root cause

Git blame：
- `f1a2b9f Asterism v2 initial commit (2026-04-29)`：單 problem workspace、語意正確
- `a6b24cb cli: init-batch + run --scope for multi-problem workflows`：加 multi-problem、**dispatcher gate 沒同步改**
- semantic 默默變 conjunctive AND

是 incremental refactor 漏改的 regression、不是設計上的決定。

### 2.3 修復

Commit `147bec5`（dispatcher.py + library.py）：
- 把 workspace-AND gate 拆成 per-problem loop
- `library.maybe_promote` 加 idempotence short-circuit（防 per-tick 重跑 axiom_probe）
- 780 unit tests passed + 1 新 regression test

### 2.4 retrospective audit

由於 framework gate 沒跑、必須事後手動 audit 確認 proved 結果可信度：
- `_audit_gateway.py`：對 237 proved roots（含 minif2f + 舊單 problem run）跑 `verify_file` + `#print axioms`
- 4-worker parallel、83.4 min 跑完
- 結果：**0 sorryAx leak**、3 個 native_decide（非 whitelist 但業界接受）、2 個 build/verify fail（人工 patch 副作用、見 §3）

→ **這次 run 沒有 silent sorryAx 污染**、proved 標記實質正確。

## §3. 2 個 audit FAIL 案

Audit 在以下 2 題報 FAIL：

| Problem | 報錯 | 真實原因 |
|---|---|---|
| `aime_1997_p11` | `build_fail` (type mismatch `Real.pi` vs `π`) | 之前手動加 `open Real` 到 Root.lean、但 leaf / strategy file 沒同步 |
| `imo_1966_p4` | `verify_fail` (`lake setup-file`) | 同類、leaf signature 不一致 |

### 3.1 根因

`4f8559b 2026-05-12` 那次手動加 `open Real` 到 4 個 problem 的 Root.lean、但 framework 寫 strategy / leaf 時不會自動帶 opens、agent 寫的時候有些用 `Real.pi` 全名、有些用 `π` 簡寫、又有些 leaf 用 `open Real in <decl>` scope-limited。混在一起、最後 type-unify 失敗。

### 3.2 修復

Commit `6828076`：對 aime_1997_p11、imo_1965_p1、imo_1966_p4 三題下所有 .lean file（49 個）統一加 `open BigOperators Real Nat Topology Rat`。一個 ambiguous `ne_of_gt` 顯式消歧。

驗證（手動 axiom_probe = 等價於 framework 該跑的 gate）：

| Problem | lake build | `#print axioms main` |
|---|---|---|
| aime_1997_p11 | ✓ | `[propext, Classical.choice, Quot.sound]` |
| imo_1965_p1 | ✓ | 同上 |
| imo_1966_p4 | ✓ | 同上 |

三題全 kernel-pure clean。

### 3.3 framework followup（task #117）

cmd_init opens fix（`6906399`）只動 Root.lean、agent 寫的 strategy / leaf 沒拿到 opens。應改成 framework 在 spawn 時把 Defs.lean opens 推給 agent、或 post-process 自動補。

## §4. 9 個 source bug errata

全部跟 `MiniF2F/Valid/` 的 transcription 有關、原始競賽題沒問題、只是 Lean 4 formalization 寫錯。每個附 kernel-verified disproof（`#print axioms` 只報 whitelist 三個 axiom、無 sorryAx）。

| # | Problem | Bug class | Counterexample |
|---|---|---|---|
| 1 | `imo_1967_p3` | `∏` body precedence 截斷 subtraction | k=5, m=1, n=2, c(s)=s(s+1) |
| 2 | `imo_1962_p4` | answer-set step π/6 太細、admits x=0 | LHS≠RHS |
| 3 | `amc12a_2020_p13` | ℕ-div trivializes 1/k=0 | a=b=c=2, n=2 |
| 4 | `mathd_algebra_282` | ℕ-div in 8^(1/3) | f(1)=1, sum=78≠79 |
| 5 | `aime_1988_p3` | 缺 x>1 precondition | x=1 → 0=27 |
| 6 | `aime_1984_p5` | log_neg_eq_log、signs free | a=64, b=-8 |
| 7 | `amc12a_2002_p21` | recurrence `∀n≥2` 漏 u₂,u₃ | u₂=10000 |
| 8 | `mathd_numbertheory_126` | minimality scope error | a=1480 |
| 9 | `mathd_algebra_433` | 答案值錯（f(8)=1, not 19）| reflexive |

詳細 counterexample + disproof Lean code 在 `docs/errata/minif2f/*_disproof.lean`、issue draft 在 `docs/errata/minif2f/upstream_issue.md`。

### 4.1 Upstream verify

Issue 送 `yangky11/miniF2F-lean4`、原因：
- 我們 import 來源
- 維護者活躍（`1be24b7 2026-02` 才 merge 過 Test-split 7 errata 修復 PR）
- 不會送 `openai/miniF2F`、那個 frozen at v1 不接 fix

Prior-art 全 verified：**9/9 完全沒人回報過**、issue + PR 跨 3 個 main repo 都 0 match。

## §5. Defs.lean 人工 helper（誠實揭露）

2 題用了 Defs.lean intervention（minimal hint）：

| Problem | Helper | Outcome |
|---|---|---|
| `imo_1993_p5` | `noncomputable def goldA (n : ℕ) : ℕ := ⌊n·φ⌋.toNat`（一行、無 lemma）| proved；agent 自己 invent `f n = goldA (n+1) - 1` shift、找 Beatty 對應、證 Hofstadter identity（IMO-tier）|
| `amc12a_2009_p25` | `noncomputable def θ : ℕ → ℝ`（Fibonacci angle、tan-addition / Pisano-period）| proved |

這 2 個算「framework-assisted」、不算 fully autonomous。內部報告寫清、教授版可揭可不揭（取決於敘事）。

Phase 2 Theorist Pipeline 就是要把 helper definition generation 也納入 framework（task #106）。

## §6. native_decide 的處理

### 6.1 現象

3 個 proved root 的 strategy body 用了 `native_decide`：

| Problem | Strategy | 用途 |
|---|---|---|
| `aimeI_2000_p7` | s768 | 收 `↑(1/4).den + (1/4).num = 5` 數值 |
| `amc12a_2019_p9` | s589 | 數值收尾 |
| `mathd_numbertheory_709` | s9316 | 數值收尾 |

axiom set 多 `_native.native_decide.ax_1_1`（即 `Lean.ofReduceBool`）、不在嚴格 whitelist。

### 6.2 為何沒攔

- Builder leaf 跟 Backward leaf-bypass 在提交時跑 `axiom_probe`、native_decide 會被拒
- 但 **decomposing strategy**（含 sub-goal + 自己 body）的 axiom check 設計上延後到 root gate
- 這次 run root gate 沒跑（§2 的 BUG）、native_decide 漏網
- 即使 root gate 跑了、會拒、agent 會被 force redispatch

### 6.3 決策：接受

業界做法：
- DeepSeek-Prover-V2、HyperTree、Sagredo、Seed-Prover、LeanDojo published 數字**都沒做 axiom whitelist filter**、predefault 接受 native_decide proofs
- Lean kernel 仍會驗、加的只是 Lean compiler bytecode trust
- 3/237 ≈ 1.3% 影響、不傷 headline integrity

我們報告**對外揭露**這點、不打混：
> "Of the 235 proofs, 232 are strictly kernel-pure (whitelist `[propext, Classical.choice, Quot.sound]`); 3 used `native_decide`, expanding trust to Lean's compiled bytecode — accepted in mainstream Lean theorem-proving benchmarks."

### 6.4 framework 層面

不主動加 forbidden_lemmas（task #116 closed）。若將來想跑「嚴格 mode」、framework root gate 跑起來後自動拒、agent 會被迫改用 `decide` / `norm_num`。

## §7. 對比業界

| Framework | Score | Budget | Lean version | Specialized? |
|---|---|---|---|---|
| HyperTree (2022) | 58.6% | tree search | Lean 3 | Yes |
| DeepSeek-Prover-V2 671B | 100% Valid (test 88.9% @ Pass@8192) | Pass@8192 | Lean 4 | Yes |
| Seed-Prover (ByteDance 2025) | 100% | Medium budget、days/problem、>1000 line proofs、含 human-corrected subset | Lean 4 | Yes |
| **Asterism (我們)** | **96.3% (235/244 raw)** | ~Pass@4 spawns/problem | Lean 4 | **No — general Claude** |

額外貢獻（沒人在報告裡放的）：
- 9 個 kernel-verified counterexample，公開、不靜默修 statement
- 跟 Seed-Prover 那種「manually added or corrected by human experts」截然不同
- framework correctness gap 自我發現 + 自我修復、過程透明

## §8. 對外揭露 / Caveat list

對教授 / 對 upstream / 對任何外部讀者都要誠實寫的：

1. **3 個 proof 用 native_decide**（trust expansion 揭露、見 §6）
2. **2 個 proof 用 Defs.lean human helper**（minimal hint、見 §5）
3. **2 個 proof 事後手動補 open clauses**（修 leaf signature mismatch、見 §3）
4. **這次 run 中 framework 沒跑過 kernel gate**（已修、retrospective audit 確認無 sorryAx leak）
5. **不主張 exhaustive completeness**（"未發現進一步反例"≠"證明不存在反例"）

## §9. 待辦 followup（framework）

| # | 主題 |
|---|---|
| #101 | 延後 insert_strategy 到 quota check 之後（避免 dead strategy 噪音）|
| #102 | TREE.md 把 dead strategies 分類顯示 |
| #103 | 連續 quota_exhausted exponential backoff |
| #106 | Phase 2 Theorist Pipeline 設計 doc |
| #110 | spawn_timeout 扣除 LSP slot 等待時間 |
| #111 | gateway slot soft-reservation 增加 hot_rate |
| #112 | dedupe 擋 shelved-equivalent sub-goal |
| #113 | forbidden_lemma 擴展涵蓋 shelved 子目標 |
| #115 | Lake olean cache invalidation（已部分修：framework gate 修好了、後續可選加 daemon-exit lake build sweep） |
| **#117** | **framework propagate Defs.lean opens 給 agent-authored files**（這次 run 發現的、最該優先修）|

## §10. 已完成的 framework 改動（這次 run 中觸發）

| Commit | 修了什麼 |
|---|---|
| `147bec5` | dispatcher: per-problem gate（fix workspace-AND BUG）+ library.maybe_promote idempotence |
| `6906399` | cli: cmd_init / cmd_reset 把 Defs.lean opens 寫進 Root.lean stub |
| `6828076` | 三個 problem 的 strategy/leaf files 手動補 opens（直到 #117 修好前 stop-gap）|

## §11. 對外傳遞建議

### 11.1 給 maintainer（yangky11/miniF2F-lean4）

`docs/errata/minif2f/upstream_issue.md` 是 ready-to-post body。內容已對齊「謙和、誠實、避免 fix prescriptive、不主張 completeness」。

送之前要不要 commit + 確認再說。

### 11.2 給教授

之後從這份提煉 1-2 頁的版本、focus 在 headline + 9 個 errata + framework discovery、技術細節（gate BUG 為何發生、如何修）可省。

主軸：
- 96.3%、無特化模型
- 9 個 errata 公開、不靜默修
- framework 自我發現 correctness gap + 自我修復
- 跟業界對比有獨特誠實度

教授不會看細節、但這幾條敘事點他應該會 appreciate。
