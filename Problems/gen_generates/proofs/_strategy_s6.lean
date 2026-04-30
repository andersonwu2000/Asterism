import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs.L_s6_s3_main_sub_2_sub_1
import Problems.gen_generates.proofs.L_s6_s3_main_sub_2_sub_2

namespace Problems.gen_generates

theorem s6_s3_main_sub_2 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n) (k : ℤ),
    k • (1 : ZMod n) = Multiplicative.toAdd x → (gen n) ^ k = x := by
  intro n _ x k h
  have h1 : (gen n) ^ k = Multiplicative.ofAdd (k • (1 : ZMod n)) :=
    s6_s3_main_sub_2_sub_1 n x k
  have h2 : Multiplicative.ofAdd (Multiplicative.toAdd x) = x :=
    s6_s3_main_sub_2_sub_2 n x k
  rw [h1, h]
  exact h2

end Problems.gen_generates
