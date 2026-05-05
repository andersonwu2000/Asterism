import Mathlib
import Problems.proj_nonexpansive.proofs.L_s169_sub_1
import Problems.proj_nonexpansive.proofs.L_s169_sub_2

namespace Problems.proj_nonexpansive

theorem s169 (a b : ℝ)
    (h : ∀ t : ℝ, 0 < t → t < 1 → 2 * a ≤ t * b) :
    a ≤ 0  := by
  have hall : ∀ ε : ℝ, 0 < ε → 2 * a ≤ ε := fun ε hε => s169_sub_1 a b h ε hε
  exact s169_sub_2 a b h hall

end Problems.proj_nonexpansive
