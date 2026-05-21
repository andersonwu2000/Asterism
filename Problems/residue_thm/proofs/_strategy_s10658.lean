import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_avoid_a_reversed_path
import Problems.residue_thm.proofs.L_c1_reversed_path
import Problems.residue_thm.proofs.L_integral_reverse_sign_flip

namespace Problems.residue_thm

-- Take β_rev := β ∘ (1 - ·). Decompose into three sub-pieces matching the proved-sibling
-- shape of s10539: (1) ContDiffOn ℝ 1 of β∘(1-·), (2) pointwise avoidance, (3) integral
-- sign-flip via chain rule + substitution. Endpoint equalities collapse by `norm_num`.
-- Each sub-goal restates one strictly-smaller component (no hβ_avoid in c1, no Q in c1/avoid),
-- and the framework's proved-sibling auto-import is reached from each Builder wrapper.
theorem s10658
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
        -(∫ t in (0 : ℝ)..1, Q (β t) * deriv β t)  := by
  have h_c1 := c1_reversed_path hβ
  have h_avoid := avoid_a_reversed_path hβ_avoid
  have h_int := integral_reverse_sign_flip (Q := Q) (a := a) hβ hβ_avoid
  refine ⟨fun t => β (1 - t), h_c1, ?_, ?_, h_avoid, h_int⟩
  · change β (1 - 0) = β 1
    norm_num
  · change β (1 - 1) = β 0
    norm_num

end Problems.residue_thm
