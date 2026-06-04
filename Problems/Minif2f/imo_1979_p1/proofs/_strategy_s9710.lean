import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_sum_recip_eq_witness_div_prod

namespace Problems.Minif2f.imo_1979_p1

-- Supply the explicit witness n = ∑ j ∈ s, ∏ k ∈ s.erase j, f k so the ∃ is closed.
-- Reduces to one ∃-free equation: ∑ 1/(f j) = (∑ ∏_{k≠j} f k) / (∏ f j).
theorem s9710 (f : ℕ → ℕ) (s : Finset ℕ)
    (hpos : ∀ j ∈ s, 0 < f j) :
    ∃ n : ℕ, (∑ j ∈ s, (1 : ℝ) / ((f j : ℕ) : ℝ)) =
      (n : ℝ) / ((∏ j ∈ s, f j : ℕ) : ℝ)  := by
  have h_eq := sum_recip_eq_witness_div_prod f s hpos
  exact ⟨∑ j ∈ s, ∏ k ∈ s.erase j, f k, h_eq⟩

end Problems.Minif2f.imo_1979_p1
