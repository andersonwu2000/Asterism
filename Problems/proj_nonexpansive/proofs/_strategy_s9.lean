import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_t_witness_pos_m
import Problems.proj_nonexpansive.proofs.L_t_witness_zero_m

namespace Problems.proj_nonexpansive

theorem s9 (M : ℝ) (hM : 0 ≤ M) (ε : ℝ) (hε : 0 < ε) :
    ∃ t : ℝ, 0 < t ∧ t ≤ 1 ∧ t * M ≤ ε  := by
  rcases hM.lt_or_eq with hMpos | hMzero
  · exact t_witness_pos_m M hMpos ε hε
  · have h1 := t_witness_zero_m ε hε
    rwa [← hMzero]

end Problems.proj_nonexpansive
