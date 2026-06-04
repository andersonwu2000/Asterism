import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs

namespace Problems.Minif2f.imo_1987_p6

-- entry_kind: Builder
theorem hyp_yields_p_prime : ∀ (p : ℕ),
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    Nat.Prime p := by
  intro p h
  have h0 := h 0 (Nat.zero_le _)
  simp at h0
  exact h0

end Problems.Minif2f.imo_1987_p6
