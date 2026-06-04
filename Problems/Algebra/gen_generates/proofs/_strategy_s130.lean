import Mathlib
import Problems.Algebra.gen_generates.Defs
import Problems.Algebra.gen_generates.proofs.L_s130_sub_1
import Problems.Algebra.gen_generates.proofs.L_s130_sub_2

namespace Problems.Algebra.gen_generates

theorem s130 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    (gen n) ^ k = Multiplicative.ofAdd (k • (1 : ZMod n)) := by
  intro n _inst k
  have h1 : Multiplicative.toAdd ((gen n) ^ k) = k • (1 : ZMod n) := s130_sub_1 n k
  have h2 : (gen n) ^ k = Multiplicative.ofAdd (Multiplicative.toAdd ((gen n) ^ k)) :=
    s130_sub_2 n k ((gen n) ^ k)
  rw [h2, h1]

end Problems.Algebra.gen_generates
