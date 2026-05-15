import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_lie_span_v_le_fpow_span

namespace Problems.sl2_v_n_irreducible

-- Backward step: the carrier of `lieSpan R (t.toLieSubalgebra R) {v}` is
-- contained in the R-Submodule span of `{fᵏ·v : k ∈ ℕ}`; applying this
-- inclusion to `w ∈ W ⊆ lieSpan {v}` closes the goal.
theorem s9911
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0) :
  w ∈ Submodule.span R
    (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))  := by
  have h_lie_span_v_le_fpow_span :
      ∀ x : M, x ∈ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} →
        x ∈ Submodule.span R
          (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)) :=
    lie_span_v_le_fpow_span R L M t hv
  exact h_lie_span_v_le_fpow_span w (hWle hwW)

end Problems.sl2_v_n_irreducible
