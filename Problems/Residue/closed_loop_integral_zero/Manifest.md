---
problem: Residue.closed_loop_integral_zero
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.closed_loop_integral_zero — primitive 存在 → closed loop 積分 = 0

## Statement
∀ {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U →
  (∀ z ∈ U, HasDerivAt F (f z) z) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) U →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0

## Setting
微積分基本定理沿路徑的版本：F 是 f 的 primitive、γ closed → ∫γ f = F(γ 1) - F(γ 0) = 0。

## Lemma hints
- `intervalIntegral.integral_eq_sub_of_hasDerivAt` — 微積分基本定理區間版
- 鏈式法則：`deriv (F ∘ γ) = (deriv F ∘ γ) · deriv γ = f ∘ γ · deriv γ`
- `HasDerivAt.comp`

## Strategic notes
純技術 calculus、無需新概念。Mathlib 直接組裝可收。預計 Backward 1-2 層、可能要一個小 Builder helper。
