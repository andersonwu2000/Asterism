import Mathlib
namespace Problems.Minif2f.amc12a_2002_p12

-- vieta_sum: Vieta's formula — if a,b∈ℕ are both roots of x²-63x+k and a≠b, then a+b=63.
-- Proof: f(a)=f(b)=0 gives (a-b)(a+b-63)=0; since a≠b we conclude a+b=63.
theorem vieta_sum : ∀ (f : ℝ → ℝ) (k : ℝ) (a b : ℕ),
    (∀ x, f x = x ^ 2 - 63 * x + k) →
    (f a = 0 ∧ f b = 0) →
    a ≠ b →
    (Nat.Prime a ∧ Nat.Prime b) →
    a + b = 63 := by
  intro f k a b hf ⟨ha, hb⟩ hne _
  have ha' : (a : ℝ) ^ 2 - 63 * (a : ℝ) + k = 0 := by rw [← hf]; exact ha
  have hb' : (b : ℝ) ^ 2 - 63 * (b : ℝ) + k = 0 := by rw [← hf]; exact hb
  have hfact : ((a : ℝ) - b) * ((a : ℝ) + b - 63) = 0 := by nlinarith [ha', hb']
  have hne' : (a : ℝ) ≠ (b : ℝ) := by exact_mod_cast hne
  have hsum : (a : ℝ) + b = 63 := by
    rcases mul_eq_zero.mp hfact with h | h
    · exact absurd (sub_eq_zero.mp h) hne'
    · linarith
  exact_mod_cast hsum

end Problems.Minif2f.amc12a_2002_p12
