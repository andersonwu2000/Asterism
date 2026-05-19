---
problem: Residue.winding_number_circle
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.winding_number_circle — 圓圈的 winding number 具體值

## Statement
∀ (c : ℂ) (R : ℝ) (a : ℂ),
  0 < R →
  (‖a - c‖ < R → Complex.windingNumber (fun t => c + R * Complex.exp (2 * Real.pi * Complex.I * t)) a = 1) ∧
  (R < ‖a - c‖ → Complex.windingNumber (fun t => c + R * Complex.exp (2 * Real.pi * Complex.I * t)) a = 0)

## Setting
圓圈 `γ(t) = c + R·exp(2πi·t)`（單位速 t ∈ [0,1]）對內部點 winding = 1、對外部點 winding = 0。圓上點 (‖a-c‖ = R) 留作 boundary case 不在本問題範圍。

## Dependencies
- `Residue.circle_integral_inv` (proved) — `∮ z in C(c,R), (z-c)⁻¹ = 2πi`、把它換成 `γ` parametrization 就是 inside-case
- `Residue.winding_number_int` (proved) — `windingNumber` 定義 + 整數性

## Lemma hints
- `circleIntegral_def_Icc` — 把 `∮ z in C(c,R), f` 展開成 parametrized integral
- `Complex.exp` 的 derivative + 鏈式法則
- 證 outside case 用 `Mathlib.Analysis.Complex.Polynomial` / Cauchy 圓盤 integral = 0（要靠之後的 `cauchy_rect_to_disk` 嗎？看 agent 怎麼選）

## Strategic notes
拆 inside / outside 兩 case：
- inside：把 ∫γ 1/(z-a) 變數變換 + 用 circle_integral_inv 推 = 2πi、divide 出 k=1
- outside：a 不在 closedBall c R 內、被積函數在 closedBall 上 holomorphic、Cauchy → 積分 = 0、divide 出 k=0

預計 Backward 2-3 層、可能需要小幅 Forward。
