---
problem: residue_thm
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# residue_thm — Cauchy residue theorem

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
