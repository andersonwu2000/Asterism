import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs

namespace Problems.Minif2f.imo_1987_p4

-- residue_involution: uses iter_shift to show f(f a % 1987) ≡ a (mod 1987),
-- then case-splits on f a / 1987 ∈ {0, 1} (forced by a < 1987) to close with omega.
theorem residue_involution (f : ℕ → ℕ) (hff : ∀ n, f (f n) = n + 1987) :
    ∀ a, a < 1987 → f (f a % 1987) % 1987 = a := by
  have hshift : ∀ n, f (n + 1987) = f n + 1987 := by
    intro n
    have h1 := hff (f n)
    have h2 := hff n
    rw [← h2]; exact h1
  have hiter : ∀ n m, f (n + 1987 * m) = f n + 1987 * m := by
    intro n m
    induction m with
    | zero => simp
    | succ m ih =>
      have heq : n + 1987 * m.succ = (n + 1987 * m) + 1987 := by omega
      rw [heq, hshift, ih]; linarith
  intro a ha
  have hkey : f (f a % 1987) + 1987 * (f a / 1987) = a + 1987 := by
    have h1 := hiter (f a % 1987) (f a / 1987)
    have h2 : f a % 1987 + 1987 * (f a / 1987) = f a := by omega
    rw [h2] at h1
    linarith [hff a]
  have hcases : f a / 1987 = 0 ∨ f a / 1987 = 1 := by omega
  rcases hcases with h | h <;> simp [h] at hkey <;> omega

end Problems.Minif2f.imo_1987_p4
