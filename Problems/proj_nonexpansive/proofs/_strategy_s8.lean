import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_exists_t_witness

namespace Problems.proj_nonexpansive

theorem s8 (c M : ℝ) (hM : 0 ≤ M)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * c ≤ t * M) :
    ∀ ε : ℝ, 0 < ε → 2 * c ≤ ε  := by
  intro ε hε
  obtain ⟨t, ht_pos, ht_le1, ht_M⟩ := exists_t_witness M hM ε hε
  linarith [h t ht_pos ht_le1]

end Problems.proj_nonexpansive
