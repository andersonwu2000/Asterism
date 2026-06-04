import Mathlib
import Problems.Algebra.gen_generates.Defs

namespace Problems.Algebra.gen_generates

theorem s130_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (k : ℤ),
    Multiplicative.toAdd ((gen n) ^ k) = k • (1 : ZMod n) := by
  intro n _inst k
  simp only [gen, toAdd_zpow, toAdd_ofAdd]

end Problems.Algebra.gen_generates
