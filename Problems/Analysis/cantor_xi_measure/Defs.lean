import Mathlib

/-!
Shared definitions for the cantor_xi_measure problem (實變 2 Q3.2).
The generalised Cantor set `C_ξ` is the limit of recursively-defined
nested closed sets `cantorXi ξ n` ⊆ [0, 1]. Each iteration removes
the open middle of length `ξ` from each remaining interval (after
appropriate scaling).
-/

namespace Problems.Analysis.cantor_xi_measure

open Set

/-- Iterate `n` of the ξ-Cantor construction starting from `[0, 1]`.
    `cantorXi ξ (n+1)` = scale prev by `(1-ξ)/2`, then take the union
    with the same scale shifted by `(1+ξ)/2`. -/
noncomputable def cantorXi (ξ : ℝ) : ℕ → Set ℝ
  | 0     => Icc 0 1
  | n + 1 =>
      let prev := cantorXi ξ n
      ((fun x => (1 - ξ) / 2 * x) '' prev) ∪
      ((fun x => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' prev)

/-- The ξ-Cantor set: intersection of all iterates. -/
noncomputable def cantorSet (ξ : ℝ) : Set ℝ := ⋂ n, cantorXi ξ n

end Problems.Analysis.cantor_xi_measure
