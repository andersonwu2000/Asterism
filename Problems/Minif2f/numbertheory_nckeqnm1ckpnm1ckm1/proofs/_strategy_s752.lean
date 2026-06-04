import Mathlib
import Problems.Minif2f.numbertheory_nckeqnm1ckpnm1ckm1.Defs

namespace Problems.Minif2f.numbertheory_nckeqnm1ckpnm1ckm1

-- Direct proof: Pascal's rule via `Nat.choose_succ_succ`.
-- Rewrite `n = n'+1`, `k = k'+1` using `0 < n`, `0 < k`, then `simp` closes.
theorem s752 : ∀ (n k : ℕ) (h₀ : 0 < n ∧ 0 < k) (h₁ : k ≤ n), Nat.choose n k = Nat.choose (n - 1) k + Nat.choose (n - 1) (k - 1)  := by
  intro n k h₀ h₁
  obtain ⟨hn, hk⟩ := h₀
  obtain ⟨n, rfl⟩ := Nat.exists_eq_succ_of_ne_zero hn.ne'
  obtain ⟨k, rfl⟩ := Nat.exists_eq_succ_of_ne_zero hk.ne'
  simp [Nat.choose_succ_succ, Nat.add_comm]

end Problems.Minif2f.numbertheory_nckeqnm1ckpnm1ckm1
