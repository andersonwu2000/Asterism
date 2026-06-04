import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_sum_recip_eq_quotient_of_pos_nat

namespace Problems.Minif2f.imo_1979_p1

-- Decomposition: invoke an abstract lemma `sum_recip_eq_quotient_of_pos_nat` that for any
-- finite set of positive nat-valued denominators expresses ∑ 1/f j as n / ∏ f j (cast to ℝ).
-- Specialize at f j := (660+j)*(1319-j) on Finset.range 330 (positivity from omega bounds).
theorem s9670 :
    ∃ n : ℕ,
      (∑ j ∈ Finset.range 330,
          (1 : ℝ) / ((((660 + j) * (1319 - j) : ℕ) : ℝ))) =
        (n : ℝ) / ((∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j)) : ℕ) : ℝ)  := by
  have h_pos : ∀ j ∈ Finset.range 330, 0 < (660 + j) * (1319 - j) := by
    intro j hj
    have hj' : j < 330 := Finset.mem_range.mp hj
    exact Nat.mul_pos (by omega) (by omega)
  exact sum_recip_eq_quotient_of_pos_nat
    (fun j => (660 + j) * (1319 - j)) (Finset.range 330) h_pos

end Problems.Minif2f.imo_1979_p1
