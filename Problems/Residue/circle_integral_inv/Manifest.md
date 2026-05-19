---
problem: Residue.circle_integral_inv
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.circle_integral_inv — `(z-c)⁻¹` 圍道積分公式

## Statement
∀ (c : ℂ) (R : ℝ),
  0 < R →
  (∮ z in C(c, R), (z - c)⁻¹) = 2 * Real.pi * Complex.I

## Lemma hints
- `Mathlib.MeasureTheory.Integral.CircleIntegral` — `circleIntegral` 定義
  + `∮ z in C(c, R), f z` notation。核心引用對象：
  - `circleIntegral.integral_sub_inv_of_mem_ball`：`∀ {c w R}, w ∈ Metric.ball c R → (∮ z in C(c, R), (z - w)⁻¹) = 2πi`
- `Metric.mem_ball_self` — `c ∈ Metric.ball c R` when `0 < R`

## Strategic notes
直接套 `circleIntegral.integral_sub_inv_of_mem_ball` with `w = c`、邊界條件用 `Metric.mem_ball_self hR`。預計 Backward 一次拆 0-1 層、leaf-bypass 三行內收尾。

這是整套 residue chain 的 atom：之後的 `winding_number_circle` 用此推圓圈 winding=1、`single_pole_residue` 用此推 residue 公式。
