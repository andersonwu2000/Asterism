import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

-- Forward rationale: Strategist brick (2) — homotopy invariance of the lifted
-- endpoint Γ(1) for loops at 1 ∈ Circle. Mathlib already has
-- `IsCoveringMap.liftPath_apply_one_eq_of_homotopicRel`
-- (Topology/Homotopy/Lifting.lean:359), and `Path.Homotopic γ γ'` unfolds to
-- `Nonempty (Path.Homotopy γ γ') = Nonempty (HomotopyRel γ.toContinuousMap
-- γ'.toContinuousMap {0,1}) = γ.toContinuousMap.HomotopicRel γ'.toContinuousMap {0,1}`,
-- so this is a thin specialization to `Circle.isCoveringMap_exp` at basepoint 0.
-- Once `winding γ := Classical.choose (lift_endpoint_mem_two_pi_int γ)` is in
-- place, well-definedness on `Path.Homotopic.Quotient (1) (1)` follows from
-- this equation plus `Int.cast_injective` on `n * (2π)`.
-- entry_kind: Builder
theorem lift_endpoint_eq_of_homotopic
    (γ γ' : Path (1 : Circle) 1) (h : γ.Homotopic γ') :
    (Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
        (by simp : γ.toContinuousMap 0 = Circle.exp 0)) 1
      = (Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap 0
        (by simp : γ'.toContinuousMap 0 = Circle.exp 0)) 1 := by
  exact Circle.isCoveringMap_exp.liftPath_apply_one_eq_of_homotopicRel h 0 (by simp) (by simp)

end Problems.pi1_circle
