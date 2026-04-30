import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs.L_s9_s3_main_sub_1_sub_1
import Problems.gen_generates.proofs.L_s9_s3_main_sub_1_sub_2

namespace Problems.gen_generates

theorem s9_s3_main_sub_1 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n),
    ∃ k : ℤ, k • (1 : ZMod n) = Multiplicative.toAdd x := by
  intro n _ x
  have ⟨k, hk⟩ := s9_s3_main_sub_1_sub_2 n x
  exact ⟨k, (s9_s3_main_sub_1_sub_1 n x k).trans hk⟩

end Problems.gen_generates
