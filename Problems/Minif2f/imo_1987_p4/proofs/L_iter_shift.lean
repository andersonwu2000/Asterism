import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs

namespace Problems.Minif2f.imo_1987_p4

-- iter_shift: induction on m using one-step shift f(n+1987) = f n + 1987,
-- derived from hff(f n) rewritten by hff n (f∘f∘f n = f n + 1987 both ways).
theorem iter_shift (f : ℕ → ℕ) (hff : ∀ n, f (f n) = n + 1987) :
    ∀ n m, f (n + 1987 * m) = f n + 1987 * m := by
  have hshift : ∀ n, f (n + 1987) = f n + 1987 := by
    intro n
    have h1 := hff (f n)
    have h2 := hff n
    rw [← h2]
    exact h1
  intro n m
  induction m with
  | zero => simp
  | succ m ih =>
    have heq : n + 1987 * m.succ = (n + 1987 * m) + 1987 := by omega
    rw [heq, hshift, ih]
    linarith

end Problems.Minif2f.imo_1987_p4
