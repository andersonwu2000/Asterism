import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integral_reverse_chain_neg: chain rule gives deriv (β ∘ (1-·)) t = (-1) • deriv β (1-t);
-- pull the sign out of the integral via congr + pointwise DifferentiableAt case-split.
-- entry_kind: Builder
theorem integral_reverse_chain_neg
    {Q : ℂ → ℂ} {a : ℂ} {β : ℝ → ℂ}
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a) :
    (∫ t in (0 : ℝ)..1, Q (β (1 - t)) * deriv (fun s => β (1 - s)) t) =
      -(∫ t in (0 : ℝ)..1, Q (β (1 - t)) * deriv β (1 - t)) := by
    rw [← intervalIntegral.integral_neg]
    congr 1
    ext t
    have hderiv_eq : deriv (fun s => β (1 - s)) t = (-1 : ℝ) • deriv β (1 - t) := by
      by_cases hβD : DifferentiableAt ℝ β (1 - t)
      · have hinner : HasDerivAt (fun s => (1 : ℝ) - s) (-1 : ℝ) t := by
          simpa using (hasDerivAt_id t).const_sub 1
        have hchain := hβD.hasDerivAt.scomp t hinner
        simp only [] at hchain
        exact hchain.deriv
      · have hnotD : ¬DifferentiableAt ℝ (fun s => β (1 - s)) t := by
          intro hD
          apply hβD
          have h_sub : DifferentiableAt ℝ (fun u => (1 : ℝ) - u) (1 - t) := by fun_prop
          have hD' : DifferentiableAt ℝ (fun s => β (1 - s)) (1 - (1 - t)) := by
            have heq : 1 - (1 - t) = t := by ring
            rwa [heq]
          have hcomp := hD'.comp (1 - t) h_sub
          have hfun : (fun s => β (1 - s)) ∘ (fun u => (1 : ℝ) - u) = β := by ext u; simp
          rwa [hfun] at hcomp
        rw [deriv_zero_of_not_differentiableAt hnotD, deriv_zero_of_not_differentiableAt hβD]
        simp
    rw [hderiv_eq]
    simp

end residue_thm

end Problems