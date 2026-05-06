import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_c_nonpos_from_two_c_le_eps
import Problems.proj_nonexpansive.proofs.L_forall_pos_two_c_le_eps

namespace Problems.proj_nonexpansive

theorem s7 (c M : ℝ) (hM : 0 ≤ M)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * c ≤ t * M) :
    c ≤ 0  := by
  have h1 : ∀ ε : ℝ, 0 < ε → 2 * c ≤ ε := forall_pos_two_c_le_eps c M hM h
  exact c_nonpos_from_two_c_le_eps c M hM h h1

end Problems.proj_nonexpansive
