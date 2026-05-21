# Bridge lemma layer

Status: planned (2026-05-06). New design round; previous v1 work
(`goal_history_unified.md`) shipped, this is the next architectural item.

## 動機

對照 `parcadei/sylvester-gallai-lean4`（同題目第三方實作）：
- **parcadei**：~1000 LOC，~30 lemma；所有 cross-product polynomial 工作集中
  在 `AreaProof.lean` 的 ~12 個 bridge lemma（`cross2D_sq_add_inner_sq`
  Lagrange、`infDist_eq_cross_div_dist`、各種 cross-product 恆等式）。
  寫一次，上層證明全程在 affine/metric 抽象 API 走，**重複度極低**。
- **Asterism SG**：同題目跑出 100+ sub-goal、3× LOC。主因不是 framework
  性能、而是**每個 sub-goal 各自重展開 cross-product**。

## 問題本質

Asterism `Manifest.md` 的 `## Lemma hints` 只列 Mathlib primitives
（`Finset.exists_min_image` 等），**沒鼓勵 agent 在拆解早期預先建立
problem-specific bridge lemma 庫**。Backward worker 拆解時是 type-by-type
即興、彼此獨立，沒有「先建工具、再用工具」的階段感。

這**不是**：
- generalization 問題（推廣到更廣定理）
- Mathlib API 問題（換 `Collinear` 定義）

是 abstraction 問題：把代數工作集中在一個 bridge layer、上層邏輯不再
重複 polynomial expansion。

## 三個解法方向（草稿、待設計選擇）

### (a) Manifest `## Bridge lemmas` section

- Manifest 新增 `## Bridge lemmas` section（人手列、跟 `## Lemma hints`
  並列）
- `cli init` 自動把 bridge lemma 放進 `Problems/<p>/Bridges.lean`（或
  類似檔）+ 寫對應 sorry stubs 進 sub-goal pool
- 自動成為 dedup canonical（接 item 11）

### (b) 強化 Backward prompt

- 引導 Backward agent 在早期 spawn 寫 type-only `Lemmas.lean`
- 其後拆解優先 use 該 file 的 lemma signature、避免重展開

### (c) Dedup 擴大 bridge 自動跨 strategy 重用

- 接 item 11 dedup 擴大（commit `865655d` 已做 cross-branch proved-goal
  candidate pool）
- bridge lemma 在 pool 內、新 sub-goal 自動 alias 到它

三個方向不互斥、可組合。

## 與 v3 archive 的對應

`D:\Hadamard\docs\asterism_archive\architecture_pipelines.md` §8 的
**Generalizer pipeline** 概念上就是 bridge lemma 的對應物 ——
「讀 proved Goal G、寫候選 G\*（更廣命題使 G 是特例）」 ——
Lagrange identity 等 bridge 確實是 G\*。

Strategist 看到「多個 sibling Goal 結構相似」就 inject Generalizer
是天然 fit。

短期手動方案 (a)/(c) 可先做、長期目標是把 v3 Generalizer + Strategist
coordinator 補回。Forward (corollary) 跟此問題不直接相關（先前誤判為部分解）。

## 開放決策點（next session 起手回答）

1. **Scope**：bridge lemma 是 problem-specific（cross-problem 不重用）
   還是 cross-problem reusable（接 Library/<Topic>/）？
2. **時機**：寫 bridge lemma 的時機是 `cli init` 時人手填 Manifest /
   framework 自動產 stub / Backward agent 第一次 dispatch 自己決定？
3. **檔案位置**：bridge lemma file 命名 / 位置（`Bridges.lean` /
   `Lemmas.lean` / `proofs/_bridges.lean` / 跟 sub-goal proofs 同層）？
4. **Dedup mechanism**：(c) 怎樣讓 bridge lemma 在 dedup pool 自動匹配
   sub-goal？需要新 SQL filter / 還是現有 cross-branch pool 已涵蓋？
5. **Retroactive**：對既有 proved problems（PN / cantor）是否 retroactively
   apply (a)/(b)/(c)？還是只新 problem 適用？
6. **Strategist hook**：(c) + future Strategist 怎麼 plug — bridge layer
   是 Strategist 的 explicit output 還是 Backward 內 emergent？

## 不要做

- bridge lemma 純自動化偵測（讓 framework 從 sub-goal pattern 自動 extract
  bridge）— 過度工程、agent 寫直接
- cross-problem global bridge library 不分 topic — 失去 Library/<Topic>/
  的 mathematical scope 設計
- 把 bridge lemma 跟 dedup 完全綁死 — 兩個 axis 獨立決定

## 實作順序（占位、實作前重審）

待 design 細化後填。預期 phase：
1. 選 (a)/(b)/(c) 的具體組合 + 設計細節
2. Manifest schema 改動 / parser 加 section（若 (a)）
3. cli init 邏輯改 / Backward prompt 改（依方向）
4. 既有 SG / cantor 的 retro-fit 試跑（若 retroactive）
5. SG run 對照 parcadei LOC、看下降幅度

## 跨參考

- 既有 SG 跟 parcadei 對照：`D:/Asterism/Problems/sylvester_gallai/`
  vs `parcadei/sylvester-gallai-lean4/AreaProof.lean`（外部 repo）
- v3 archive Generalizer pipeline：`D:\Hadamard\docs\asterism_archive\architecture_pipelines.md` §8
- Dedup cross-branch（item 11、已實作）：`Tooling/dedupe.py:_eligible_problem_proved`
- Library cross-problem promotion：`Tooling/library.py`
