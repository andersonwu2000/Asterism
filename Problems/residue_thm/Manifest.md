---
problem: residue_thm
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# residue_thm — Cauchy residue theorem (Wikipedia full version)

## Statement
∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a

## Setting
- `U : Set ℂ` simply-connected open
- `T : Finset ℂ` finite set of poles inside `U`
- `f` holomorphic on `U \ T`
- `γ : ℝ → ℂ` closed C¹ curve on `[0,1]` whose image avoids the poles
- conclusion: contour integral = 2πi · sum over poles of (winding) · (residue)

## Dependency chain
這個問題是 11-piece chain 的「組裝題」。本問題的證明應該短：把以下 proved 結果組合即可。

按依賴序：
1. `Residue.circle_integral_inv` — `∮ z in C(c,R), (z-c)⁻¹ = 2πi`
2. `Residue.winding_number_int` — winding 積分整數性（並引入 `Complex.windingNumber`）
3. `Residue.winding_number_circle` — 圓圈具體 winding 值
4. `Residue.cauchy_rect_to_disk` — Cauchy 圓盤定理
5. `Residue.primitive_simply_connected` — simply-connected analytic ⇒ primitive
6. `Residue.closed_loop_integral_zero` — primitive ⇒ closed loop integral = 0
7. `Residue.contour_deformation_annulus` — 同心圓圍道積分相等
8. `Residue.single_pole_residue` — 單極點 residue 公式（並引入 `Complex.residue`）
9. `Residue.pole_excision_finset` — γ 跟 ∑ winding·小圓 cycle 同 homology class
10. `Residue.null_winding_cauchy` — winding=0 → 圍道積分=0

## Lemma hints
直接組裝：
- `pole_excision_finset` 給出 `∫γ f = ∑ winding γ a · ∮_{C(a, r a)} f`
- 對每個 a、`single_pole_residue` 給出 `∮_{C(a, r a)} f = 2πi · residue f a`
- 代入後就是 statement

## Strategic notes
所有重活在前 10 個 problem。本問題預計 Backward 1 層、Builder 4-6 行收尾。
若前置 chain 完成、本題應於 30 分鐘內證完。
