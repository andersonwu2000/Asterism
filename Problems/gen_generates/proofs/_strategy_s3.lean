import Mathlib
import Problems.gen_generates.Defs
import Problems.gen_generates.proofs.L_s3_main_sub_1
import Problems.gen_generates.proofs.L_s3_main_sub_2

namespace Problems.gen_generates

theorem s3_main : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n), x ∈ Subgroup.zpowers (gen n) := by
  intro n _ x
  rw [Subgroup.mem_zpowers_iff]
  obtain ⟨k, hk⟩ := s3_main_sub_1 n x
  exact ⟨k, s3_main_sub_2 n x k hk⟩

end Problems.gen_generates
