import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- Orthonormality: x in span of bottom modes {b_j : m ≤ j} is ⟂ to b_i for i < m.
-- span_induction on the membership; the linear functional ⟪b i, ·⟫ vanishes on each
-- generator b_j (i ≠ j since i < m ≤ j by orthonormality) and is closed under +/•.
-- Direct leaf — no sub-goals.
theorem s11631
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    ∀ x : E, x ∈ Submodule.span ℝ (b '' {i : Fin n | m ≤ (i : ℕ)}) →
      ∀ i : Fin n, (i : ℕ) < m → @inner ℝ E _ (b i) x = 0  := by
  intro x hx i hi
  induction hx using Submodule.span_induction with
  | mem y hy =>
      obtain ⟨j, hj, rfl⟩ := hy
      have hij : i ≠ j := by
        intro h
        rw [h] at hi
        exact absurd hi (not_lt.mpr hj)
      exact b.orthonormal.2 hij
  | zero => simp
  | add y z _ _ ihy ihz =>
      rw [inner_add_right, ihy, ihz, add_zero]
  | smul a y _ ih =>
      rw [inner_smul_right, ih, mul_zero]


end Problems.LinearAlgebra.courant_fischer
