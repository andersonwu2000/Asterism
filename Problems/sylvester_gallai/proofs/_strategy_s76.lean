import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s76_sub_1

namespace Problems.sylvester_gallai

theorem s76 (L da D2 t : ℝ) (hL : 0 < L) (hD2 : 0 < D2) (ht : 1 < t) :
    L ^ 2 < da ^ 2 + D2 ∨ (1 - t) ^ 2 * L ^ 2 < (da - t * L) ^ 2 + D2  := by
  have hid : t * ((da - L) ^ 2 + D2) + (t - 1) * (L ^ 2 - da ^ 2 - D2) +
      ((1 - t) ^ 2 * L ^ 2 - (da - t * L) ^ 2 - D2) = 0 := s76_sub_1 L da D2 t
  by_contra h
  push_neg at h
  obtain ⟨hA, hB⟩ := h
  nlinarith [sq_nonneg (da - L), sq_nonneg (da - t * L)]

end Problems.sylvester_gallai
