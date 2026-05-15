import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- iterate_e_in_w: induction on k using LieSubmodule closure under e-action;
-- e ∈ toLieSubalgebra so W.lie_mem closes each step.
theorem iterate_e_in_w
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0) :
  ∀ k : ℕ, ((LieModule.toEnd R L M e) ^ k) w ∈ W := by
  intro k
  induction k with
  | zero => simp [hwW]
  | succ k ih =>
    rw [pow_succ', Module.End.mul_apply]
    have he_mem : e ∈ t.toLieSubalgebra R := by
      apply Submodule.subset_span; simp
    have key : LieModule.toEnd R L M e (((LieModule.toEnd R L M e) ^ k) w) =
        ⁅(⟨e, he_mem⟩ : t.toLieSubalgebra R), ((LieModule.toEnd R L M e) ^ k) w⁆ := by
      simp [LieModule.toEnd_apply_apply]
    rw [key]
    exact W.lie_mem ih

end Problems.sl2_v_n_irreducible
