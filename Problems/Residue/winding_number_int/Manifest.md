---
problem: Residue.winding_number_int
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.winding_number_int — winding number 積分是 2πi 的整數倍

## Statement
∀ {γ : ℝ → ℂ} {a : ℂ},
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  γ 0 = γ 1 →
  a ∉ γ '' Set.Icc 0 1 →
  ∃ k : ℤ,
    (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * k

## Setting
這道題建立 winding number 的整數性 — 一個 C¹ closed path `γ` 繞避開點 `a`、其積分 `(1/(2πi)) · ∫γ 1/(z-a)` 是整數。

這個結果讓 `Defs.lean` 的 `Complex.windingNumber` 定義有意義（Classical.choose 出來的 `k` 真的存在）。

## Lemma hints
- `Mathlib.Analysis.SpecialFunctions.Complex.Log` — `Complex.log` 在連續分支的可導性
- `Mathlib.Analysis.Calculus.FDeriv.RestrictScalars` / `intervalIntegral.integral_comp`
- 標準作法：定義 `θ t := ∫ s in 0..t, deriv γ s / (γ s - a)`、證 `θ` 是 `Complex.log(γ - a)` 在某分支上的 antiderivative、由 `γ 0 = γ 1` 推 `θ 1 - θ 0 = 2πi · k`

## Strategic notes
這道是 chain 中最硬的之一。預期：
- Backward 拆出 antiderivative existence、`exp(θ) = (γ - a)/(γ 0 - a)` periodicity 等 sub-goals
- 可能需要 Strategist Inject(Forward) 補 `Complex.log` 在連續分支上的相關 lemma
- 預計 1-2 個 Inject batch、3-5 小時

agent 可定義 windingNumber 用本問題的存在性結果為 specification。
