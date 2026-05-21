import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem integral_reverse_sign_flip
    {Q : ℂ → ℂ} {a : ℂ} {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
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
      rw [deriv_zero_of_not_differentiableAt hd, deriv_zero_of_not_differentiableAt hd2, neg_zero]
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

end Problems.residue_thm
