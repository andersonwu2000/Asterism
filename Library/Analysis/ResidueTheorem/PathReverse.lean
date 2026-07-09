import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Calculus.ContDiff.Operations
import Mathlib.Analysis.Calculus.Deriv.Add
import Mathlib.Analysis.Calculus.Deriv.Mul
import Mathlib.MeasureTheory.Integral.IntervalIntegral.Basic

/-!
# Path reversal for contour integrals

This file establishes basic properties of reversed paths for use in the Residue Theorem.
Given a smooth path `β : ℝ → ℂ` parametrised on `[0, 1]`, the **reversed path** is
`fun t ↦ β (1 - t)`. The main results show that the reversed path is $C^1$, avoids the same
points as `β`, and its contour integral equals the negative of the original.

## Main statements

- `avoid_a_reversed_path`: if `β t ≠ a` for all `t ∈ [0, 1]`, then `β (1 - t) ≠ a` for all
  `t ∈ [0, 1]`.
- `contDiffOn_path_reverse`: the reversed path is $C^1$ on `[0, 1]`.
- `integral_reverse_sign_flip`: the contour integral over the reversed path equals the negative
  of the original integral.
- `exists_path_reverse`: packages the above into a single existence statement.
-/

namespace Library.Analysis.ResidueTheorem.PathReverse

/-- If `β t ≠ a` for all `t ∈ [0, 1]`, then the reversed path `fun t ↦ β (1 - t)` also avoids
`a` on `[0, 1]`. This follows because `1 - t ∈ [0, 1]` whenever `t ∈ [0, 1]`. -/
theorem avoid_a_reversed_path
    {a : ℂ} {β : ℝ → ℂ}
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    ∀ t ∈ Set.Icc (0 : ℝ) 1, β (1 - t) ≠ a := by
  intro t ht
  exact hβ_avoid (1 - t) ⟨by linarith [ht.2], by linarith [ht.1]⟩

/-- If `β` is $C^1$ on `[0, 1]`, then so is the reversed path `fun t ↦ β (1 - t)`. This
follows from the chain rule: the map `t ↦ 1 - t` is $C^1$ and sends `[0, 1]` to itself. -/
theorem contDiffOn_path_reverse
    {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1)) :
    ContDiffOn ℝ 1 (fun t => β (1 - t)) (Set.Icc 0 1) := by
  have h1 : ContDiffOn ℝ 1 (fun t : ℝ => 1 - t) (Set.Icc 0 1) :=
    (contDiff_const.sub contDiff_id).contDiffOn
  have h2 : Set.MapsTo (fun t : ℝ => 1 - t) (Set.Icc 0 1) (Set.Icc 0 1) := by
    intro t ht
    simp only [Set.mem_Icc] at ht ⊢
    constructor <;> linarith [ht.1, ht.2]
  exact hβ.comp h1 h2

/-- Reversing a path flips the sign of the contour integral: the integral
$\int_0^1 Q(\beta(1-t))\,(\beta \circ (1-\cdot))'(t)\,\mathrm{d}t$
equals $-\int_0^1 Q(\beta(t))\,\beta'(t)\,\mathrm{d}t$.
The sign comes from the derivative of $t \mapsto 1 - t$; the limits are restored to
$[0, 1]$ via `intervalIntegral.integral_comp_sub_left`. -/
theorem integral_reverse_sign_flip
    {Q : ℂ → ℂ} {a : ℂ} {β : ℝ → ℂ}
    (_hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (_hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    (∫ t in (0 : ℝ)..1, Q (β (1 - t)) * deriv (fun s => β (1 - s)) t) =
      -(∫ t in (0 : ℝ)..1, Q (β t) * deriv β t) := by
  have hderiv : ∀ t ∈ Set.uIcc (0 : ℝ) 1,
      deriv (fun s => β (1 - s)) t = -deriv β (1 - t) := by
    intro t _
    by_cases hd : DifferentiableAt ℝ β (1 - t)
    · have h1 : HasDerivAt (fun s : ℝ => (1 : ℝ) - s) (-1 : ℝ) t := by
        have := (hasDerivAt_const t (1:ℝ)).sub (hasDerivAt_id t)
        simpa using this
      have h2 : HasDerivAt (fun s => β (1 - s)) ((-1 : ℝ) • deriv β (1 - t)) t := by
        have h := hd.hasDerivAt.scomp t h1
        simpa [Function.comp] using h
      rw [h2.deriv]; simp
    · have hd2 : ¬DifferentiableAt ℝ (fun s => β (1 - s)) t := by
        intro hdiff
        apply hd
        have h_inner : HasDerivAt (fun s : ℝ => (1:ℝ) - s) (-1 : ℝ) (1 - t) := by
          have := (hasDerivAt_const (1-t) (1:ℝ)).sub (hasDerivAt_id (1-t))
          simpa using this
        have hdiff' : DifferentiableAt ℝ (fun s => β (1-s)) (1-(1-t)) := by
          rw [show (1:ℝ) - (1-t) = t from by ring]; exact hdiff
        have hcomp := hdiff'.comp (1-t) h_inner.differentiableAt
        have hfun : (fun s => β (1-s)) ∘ (fun s : ℝ => 1 - s) = β :=
          funext (fun s => congr_arg β (by ring : (1:ℝ) - (1-s) = s))
        rwa [hfun] at hcomp
      rw [deriv_zero_of_not_differentiableAt hd, deriv_zero_of_not_differentiableAt hd2,
        neg_zero]
  have step1 : ∫ t in (0:ℝ)..1, Q (β (1-t)) * deriv (fun s => β (1-s)) t =
      ∫ t in (0:ℝ)..1, Q (β (1-t)) * (-deriv β (1-t)) :=
    intervalIntegral.integral_congr fun t ht => by simp only [hderiv t ht]
  rw [step1, show ∫ t in (0:ℝ)..1, Q (β (1-t)) * (-deriv β (1-t)) =
      -(∫ t in (0:ℝ)..1, Q (β (1-t)) * deriv β (1-t)) by
    rw [← intervalIntegral.integral_neg]; congr 1; ext t; ring]
  congr 1
  have hsub : ∫ x in (0:ℝ)..1, (fun t : ℝ => Q (β t) * deriv β t) (1 - x) =
      ∫ x in (1:ℝ)-(1:ℝ)..(1:ℝ)-(0:ℝ), (fun t : ℝ => Q (β t) * deriv β t) x :=
    @intervalIntegral.integral_comp_sub_left ℂ _ _ 0 1 (fun t => Q (β t) * deriv β t) 1
  simp only [sub_self, sub_zero] at hsub
  simpa using hsub

/-- Given a $C^1$ path `β : ℝ → ℂ` on `[0, 1]` avoiding a point `a : ℂ`, there exists a
reversed path `β_rev` satisfying:
- `β_rev` is $C^1$ on `[0, 1]`,
- `β_rev 0 = β 1` and `β_rev 1 = β 0` (the endpoints are swapped),
- `β_rev t ≠ a` for all `t ∈ [0, 1]`,
- the contour integral of `Q` along `β_rev` equals
  $-\int_0^1 Q(\beta(t))\,\beta'(t)\,\mathrm{d}t$.


The witness is `fun t ↦ β (1 - t)`. -/
theorem exists_path_reverse
    {Q : ℂ → ℂ} {a : ℂ}
    {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    ∃ β_rev : ℝ → ℂ,
      ContDiffOn ℝ 1 β_rev (Set.Icc 0 1) ∧
      β_rev 0 = β 1 ∧
      β_rev 1 = β 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, β_rev t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (β_rev t) * deriv β_rev t) =
        -(∫ t in (0 : ℝ)..1, Q (β t) * deriv β t) := by
  have h_c1 := contDiffOn_path_reverse hβ
  have h_avoid := avoid_a_reversed_path hβ_avoid
  have h_int := integral_reverse_sign_flip (Q := Q) (a := a) hβ hβ_avoid
  refine ⟨fun t => β (1 - t), h_c1, ?_, ?_, h_avoid, h_int⟩
  · change β (1 - 0) = β 1
    norm_num
  · change β (1 - 1) = β 0
    norm_num

end Library.Analysis.ResidueTheorem.PathReverse
