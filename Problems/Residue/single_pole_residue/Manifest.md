---
problem: Residue.single_pole_residue
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.single_pole_residue — 單極點 residue 公式

## Statement
∀ {f : ℂ → ℂ} {z₀ : ℂ} {r : ℝ},
  0 < r →
  (∃ R : ℝ, r < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) →
  (∮ z in C(z₀, r), f z) = 2 * Real.pi * Complex.I * Complex.residue f z₀

## Setting
單極點的 residue 公式：包圍 z₀ 的小圓圍道積分 = 2πi · residue。

Residue 定義（見 Defs.lean）用 `Classical.choose` 取一個 admissible R / 2 作積分半徑。本定理的內容是：任意其它合法 r 算出來的 ∮ 都等於這個。

## Dependencies
- `Residue.contour_deformation_annulus` (proved) — 同心圓積分相等

## Lemma hints
- `Defs.lean` 定義的 `Complex.residue`
- 直接套 contour_deformation_annulus、把任意 r 跟 `Classical.choose h / 2` 都當「合法半徑」、推 ∮ 相等

## Strategic notes
有了 contour_deformation_annulus 後本題很輕。預計 Backward 1 層 + Builder 一行收尾。

注意：本題的 `Defs.lean` 引入 `Complex.residue`、之後 `Residue.residue_thm`（總目標、不在此 chain 內、由 `Problems/residue_thm/`）也會 import 此 Defs。
