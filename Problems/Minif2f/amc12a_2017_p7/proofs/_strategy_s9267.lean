import Mathlib
import Problems.Minif2f.amc12a_2017_p7.Defs

namespace Problems.Minif2f.amc12a_2017_p7

-- Direct induction on k: base case k=0 reduces 2*0+1=1 to h₀; succ step applies
-- h₂ at n=2(k+1)+1 (odd, >1) to rewrite f(2k+3) = f(2k+1)+2, then uses ih.
theorem s9267 (f : ℕ → ℝ) (h₀ : f 1 = 2)
    (h₁ : ∀ n, 1 < n ∧ Even n → f n = f (n - 1) + 1)
    (h₂ : ∀ n, 1 < n ∧ Odd n → f n = f (n - 2) + 2) :
    ∀ k : ℕ, f (2*k + 1) = 2*k + 2  := by
  intro k
  induction k with
  | zero =>
    simp
    exact h₀
  | succ k ih =>
    have hodd : Odd (2*(k+1)+1) := ⟨k+1, by ring⟩
    have hgt : 1 < 2*(k+1)+1 := by omega
    have h := h₂ (2*(k+1)+1) ⟨hgt, hodd⟩
    have heq : 2*(k+1)+1 - 2 = 2*k + 1 := by omega
    rw [heq] at h
    rw [h, ih]
    push_cast
    ring

end Problems.Minif2f.amc12a_2017_p7
