---
problem: Residue.primitive_simply_connected
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.primitive_simply_connected — simply-connected 開集上 analytic 有 primitive

## Statement
∀ {U : Set ℂ} {f : ℂ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  DifferentiableOn ℂ f U →
  ∃ F : ℂ → ℂ, ∀ z ∈ U, HasDerivAt F (f z) z

## Setting
Cauchy 定理在 simply-connected 開集上的等價形式：analytic ⇒ 有 primitive。

這是 chain 中比較硬的一道、residue theorem 的核心 ingredient（讓 null-winding 圍道積分 = 0）。

## Lemma hints
- `Mathlib.AlgebraicTopology.FundamentalGroupoid.SimplyConnected` — `SimplyConnectedSpace` class
- `Mathlib.Analysis.Complex.CauchyIntegral` — 圓盤上的 primitive 存在
- 標準作法：固定 basepoint `z₀ ∈ U`、定義 `F(z) := ∫_{path z₀ → z} f`、用 simply-connected + Cauchy on disks 證 path independence
- `Residue.cauchy_rect_to_disk` (proved) — 圓盤上 closed loop integral = 0

## Strategic notes
這道預期會被拆成：
1. local primitive existence（圓盤上、直接套 Mathlib）
2. path-independence 證明（用 simply-connected + closed loop = 0）
3. global F 的 deriv 性

可能需要 1-2 個 Forward Inject 補關於 path / cover 的 lemma。
