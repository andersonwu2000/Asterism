import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- fixed_union_countable: countable union of finite fixed-point sets via Set.countable_iUnion
theorem fixed_union_countable (R : E ≃ₗᵢ[ℝ] E)
    (hfin : ∀ n : ℕ, 1 ≤ n → {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ n) x = x}.Finite) :
    (⋃ n : ℕ, {x ∈ Metric.sphere (0 : E) (1 / 2) | (R ^ (n + 1)) x = x}).Countable := by
  apply Set.countable_iUnion
  intro n
  exact (hfin (n + 1) (Nat.succ_pos n)).countable

end Problems.Geometry.banach_tarski
