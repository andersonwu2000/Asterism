import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_reverse_avoid_a
import Problems.residue_thm.proofs.L_path_reverse_c1
import Problems.residue_thm.proofs.L_path_reverse_integral_eq_neg

namespace Problems.residue_thm

-- Take β_rev := β ∘ (1 - ·). The endpoint equalities reduce by `simp` after `1 - 0 = 1`,
-- `1 - 1 = 0`. The three non-trivial sub-goals are: C¹ via composition with the smooth map
-- (1 - ·), pointwise avoidance via `1 - t ∈ Icc 0 1`, and the integral sign-flip via the
-- chain rule (`deriv (fun s => β (1 - s)) t = -deriv β (1 - t)`) plus substitution `u = 1 - t`.
theorem s10539
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
  have h_c1 := path_reverse_c1 hβ
  have h_avoid := path_reverse_avoid_a hβ_avoid
  have h_int := path_reverse_integral_eq_neg (Q := Q) (a := a) hβ hβ_avoid
  refine ⟨fun t => β (1 - t), h_c1, ?_, ?_, h_avoid, h_int⟩
  · change β (1 - 0) = β 1
    norm_num
  · change β (1 - 1) = β 0
    norm_num

end Problems.residue_thm
