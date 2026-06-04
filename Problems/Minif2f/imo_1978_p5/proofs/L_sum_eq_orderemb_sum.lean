import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- sum_eq_orderemb_sum: reindex ∑ x ∈ s, x over orderEmbOfFin via
-- sum_coe_sort + Fintype.sum_equiv on orderIsoOfFin, using
-- coe_orderIsoOfFin_apply to match the coercions.
theorem sum_eq_orderemb_sum :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ∀ (s : Finset ℕ) (hcard : s.card = m), (∀ x ∈ s, 1 ≤ x) →
      (∑ x ∈ s, (x : ℝ)) = ∑ i : Fin m, ((s.orderEmbOfFin hcard i : ℕ) : ℝ) := by
  intro n a _ _ m _ s hcard _
  rw [← Finset.sum_coe_sort s (fun x : ℕ => (x : ℝ))]
  symm
  apply Fintype.sum_equiv (s.orderIsoOfFin hcard) _ _
  intro j
  simp [Finset.coe_orderIsoOfFin_apply]

end Problems.Minif2f.imo_1978_p5
