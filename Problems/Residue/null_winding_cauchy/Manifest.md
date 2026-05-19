---
problem: Residue.null_winding_cauchy
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.null_winding_cauchy — winding=0 → 圍道積分=0（有孔版）

## Statement
∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∀ a ∈ T, Complex.windingNumber γ a = 0) →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0

## Setting
homology-form Cauchy 定理：U simply-connected open、T finite poles、f analytic on U\T、γ closed C¹ on U\T、γ around every pole winding = 0 → ∫γ f = 0。

residue_thm 主問題用此 + pole_excision_finset 推出完整 multi-pole 公式。

## Dependencies
- `Residue.winding_number_int` (proved) — `Complex.windingNumber` 定義
- `Residue.primitive_simply_connected` (proved)
- `Residue.closed_loop_integral_zero` (proved)

## Lemma hints
- 標準作法：構造小開球覆蓋 γ 的 image、每球小到避開 T、用 primitive_simply_connected 在每球上、貼合
- 或：用 cover-by-rectangles approach (Mathlib `Complex.integral_boundary_rect`) 跨 punctures
- 真正硬的部分：「winding=0 around every pole」這條件如何進入推理 — 通常要 deform γ 到無 pole 的 simply-connected subset

## Strategic notes
chain 中最硬的一道。可能要拆成多 sub-goal：
1. γ image 的開覆蓋
2. local primitive existence
3. 全 path 上 antiderivative pairing
4. winding=0 推 0 round-trip
預計 2-3 Forward batch、5-8 小時。
