---
problem: Residue.cauchy_rect_to_disk
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.cauchy_rect_to_disk — Cauchy 定理在閉圓盤上

## Statement
∀ {f : ℂ → ℂ} {c : ℂ} {R : ℝ},
  0 < R →
  DifferentiableOn ℂ f (Metric.closedBall c R) →
  (∮ z in C(c, R), f z) = 0

## Setting
Cauchy 圓盤定理的 statement-level wrapper：閉圓盤上 differentiable 的 f、其邊界圓圈積分 = 0。

## Lemma hints
- `Mathlib.Analysis.Complex.CauchyIntegral` — 核心 Mathlib 工具
  - `Complex.circleIntegral_div_sub_of_differentiable_on_off_countable` 之類
  - `Complex.integral_boundary_rect_of_continuousOn_of_differentiableOn`
- `DifferentiableOn.analyticOn` — 在 open 上 differentiable → analytic
- 找 mathlib 已有「analytic on closedBall → circleIntegral = 0」的直接陳述

## Strategic notes
Mathlib 很可能已有非常接近的版本、agent 只要 adapt 對齊 hypothesis 形狀。Backward 1 層 + leaf-bypass 直引 Mathlib 預計可收。
