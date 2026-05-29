import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_fixed_union_countable

namespace Problems.Geometry.banach_tarski

-- Uncountable-sphere escape: the union over n of the n+1-power fixed sets on the
-- radius-1/2 sphere is countable (fixed_union_countable: each finite ⇒ countable union),
-- so the uncountable sphere is not contained in it; pick c in the sphere outside the union.
-- That c has ‖c‖ = 1/2 ≤ 1/2, and any positive power fixing c would place c (= R^(m+1) c)
-- back into the union, contradicting the choice. The lone sub-goal is the countability fact.
theorem s11519 : ∀ (R : E ≃ₗᵢ[ℝ] E),
    ¬ (Metric.sphere (0 : E) (1 / 2)).Countable →
    (∀ n : ℕ, 1 ≤ n → {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ n) x = x}.Finite) →
    ∃ c, ‖c‖ ≤ 1 / 2 ∧ ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c  := by
  intro R hunc hfin
  have hBc : (⋃ n : ℕ, {x ∈ Metric.sphere (0:E) (1/2) | (R ^ (n+1)) x = x}).Countable :=
    fixed_union_countable R hfin
  have hns : ¬ (Metric.sphere (0:E) (1/2)) ⊆
      (⋃ n : ℕ, {x ∈ Metric.sphere (0:E) (1/2) | (R ^ (n+1)) x = x}) :=
    fun h => hunc (hBc.mono h)
  rw [Set.not_subset] at hns
  obtain ⟨c, hcs, hcB⟩ := hns
  have hnorm : ‖c‖ = 1/2 := mem_sphere_zero_iff_norm.mp hcs
  refine ⟨c, le_of_eq hnorm, ?_⟩
  intro n hn heq
  apply hcB
  obtain ⟨m, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (by omega : n ≠ 0)
  exact Set.mem_iUnion.mpr ⟨m, hcs, heq⟩

end Problems.Geometry.banach_tarski
