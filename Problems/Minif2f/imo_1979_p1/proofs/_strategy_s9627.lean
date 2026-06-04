import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_nat_recip_sum_quotient
import Problems.Minif2f.imo_1979_p1.proofs.L_sum_real_eq_sum_via_nat_cast

namespace Problems.Minif2f.imo_1979_p1

-- Decomposition: bridge real-form denominators to nat-cast form, then assert numerator exists.
-- (A) sum_real_eq_sum_via_nat_cast: rewrite each `(660+(j:ℝ))*(1319-(j:ℝ))` as `(((660+j)*(1319-j) : ℕ) : ℝ)` (cast bridge).
-- (B) nat_recip_sum_quotient: ∃ n, nat-cast-form sum = n / (cast product). Combine via `obtain` + `Eq.trans`.
theorem s9627 :
    ∃ n : ℕ,
      (∑ j ∈ Finset.range 330,
          (1 : ℝ) / ((660 + (j : ℝ)) * (1319 - (j : ℝ)))) =
        (n : ℝ) / ((∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j)) : ℕ) : ℝ)  := by
  have h_bridge := sum_real_eq_sum_via_nat_cast
  have h_exists := nat_recip_sum_quotient
  obtain ⟨n, hn⟩ := h_exists
  exact ⟨n, h_bridge.trans hn⟩

end Problems.Minif2f.imo_1979_p1
