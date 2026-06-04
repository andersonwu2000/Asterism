import Mathlib
import Problems.Algebra.gen_generates.Defs
import Problems.Algebra.gen_generates.proofs.L_s126_sub_1
import Problems.Algebra.gen_generates.proofs.L_s126_sub_2
import Problems.Algebra.gen_generates.proofs.L_s126_sub_3
import Problems.Algebra.gen_generates.proofs.L_s126_sub_4

namespace Problems.Algebra.gen_generates

theorem s126 : ∀ (n : ℕ) [Fact (2 ≤ n)] (x : G n), x ∈ Subgroup.zpowers (gen n) := by
  intro n _inst x
  rw [Subgroup.mem_zpowers_iff]
  refine ⟨((Multiplicative.toAdd x).val : ℤ), ?_⟩
  have h2 := s126_sub_2 n ((Multiplicative.toAdd x).val : ℤ)
  have h3 := s126_sub_3 n ((Multiplicative.toAdd x).val : ℤ)
  have h1 := s126_sub_1 n (Multiplicative.toAdd x)
  have h4 := s126_sub_4 n x
  rw [h2, h3, h1]
  exact h4

end Problems.Algebra.gen_generates
