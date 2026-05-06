import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_t_witness_pos_m_le_one
import Problems.proj_nonexpansive.proofs.L_t_witness_pos_m_mul_le
import Problems.proj_nonexpansive.proofs.L_t_witness_pos_m_pos

namespace Problems.proj_nonexpansive

theorem s10 (M : ℝ) (hM : 0 < M) (ε : ℝ) (hε : 0 < ε) :
    ∃ t : ℝ, 0 < t ∧ t ≤ 1 ∧ t * M ≤ ε  := by
  have h1 : 0 < min 1 (ε / M) := t_witness_pos_m_pos M hM ε hε
  have h2 : min 1 (ε / M) ≤ 1 := t_witness_pos_m_le_one M hM ε hε
  have h3 : min 1 (ε / M) * M ≤ ε := t_witness_pos_m_mul_le M hM ε hε
  exact ⟨min 1 (ε / M), h1, h2, h3⟩

end Problems.proj_nonexpansive
