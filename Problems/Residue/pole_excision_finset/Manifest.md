---
problem: Residue.pole_excision_finset
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.pole_excision_finset — winding number 加法分解

## Statement
∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ} {r : ℂ → ℝ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∀ a ∈ T, 0 < r a) →
  (∀ a ∈ T, Metric.closedBall a (r a) ⊆ U) →
  (∀ a ∈ T, ∀ b ∈ T, b ≠ a → b ∉ Metric.closedBall a (r a)) →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) -
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) *
      (∮ z in C(a, r a), f z) = 0

## Setting
這是 residue theorem 的「homology 拆解」骨幹：把 γ 圍 T 的圍道積分 — 「∑ winding · 小圓圍道積分」 = 0。

reading：γ 跟「在每個 a∈T 處繞 winding(γ,a) 次的小圓 cycle」是同一條 homology class、所以圍同 f 的積分相等、差為零。

## Dependencies
- `Residue.winding_number_int` (proved) — `Complex.windingNumber` 定義
- `Residue.null_winding_cauchy` (will be proved by us) — null-winding 圍道積分 = 0

## Lemma hints
- 構造 augmented loop `γ̃ := γ ∘ (concat with -winding(γ, a) copies of small circle around each a)`、它 null-winding around every a
- 套 null_winding_cauchy 得 ∫γ̃ f = 0
- 化簡為原 statement

## Strategic notes
這是 chain 中的「組裝題」。預期：
- 拆出 γ̃ 構造（Forward 出 `winding_combination_loop`）
- 套 null_winding_cauchy
- 算 ∫γ̃ = ∫γ - ∑ winding · ∮_circle_a 的代數操作

預計 Backward 2 層 + 1-2 Forward。
