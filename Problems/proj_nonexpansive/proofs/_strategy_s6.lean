import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_le_zero_of_forall_lin_bound
import Problems.proj_nonexpansive.proofs.L_lin_bound_from_quad

namespace Problems.proj_nonexpansive

theorem s6 (c M : ℝ) (hM : 0 ≤ M)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * t * c ≤ t ^ 2 * M) :
    c ≤ 0  := by
  have h1 : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * c ≤ t * M := lin_bound_from_quad c M hM h
  exact le_zero_of_forall_lin_bound c M hM h1

end Problems.proj_nonexpansive
