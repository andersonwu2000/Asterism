import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs
import Problems.Minif2f.imo_1964_p1_1.proofs.L_period
import Problems.Minif2f.imo_1964_p1_1.proofs.L_small_cases

namespace Problems.Minif2f.imo_1964_p1_1

-- Decompose by strong induction on n using periodicity 2^(k+3) - 1 ≡ 2^k - 1 (mod 7):
-- h_period descends from n ≥ 3 to n-3; h_small_cases discharges n ∈ {0,1,2}.
theorem s604 : ∀ (n : ℕ) (h₀ : 7 ∣ 2 ^ n - 1), 3 ∣ n  := by
  intro n
  induction n using Nat.strong_induction_on with
  | _ n ih =>
    intro h₀
    by_cases hn : n < 3
    · exact h_small_cases n hn h₀
    · push_neg at hn
      obtain ⟨m, rfl⟩ := Nat.exists_eq_add_of_le hn
      have h₁ : 7 ∣ 2 ^ m - 1 := h_period m (by rw [Nat.add_comm]; exact h₀)
      have h₂ : 3 ∣ m := ih m (by omega) h₁
      omega

end Problems.Minif2f.imo_1964_p1_1
