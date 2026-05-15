import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_v_mem_of_w_nonzero

namespace Problems.sl2_v_n_irreducible

-- Disjunction on W ≤ lieSpan{v}: case-split on W = ⊥; in the nontrivial case use
-- le_antisymm with hW, reducing to lieSpan{v} ≤ W, i.e. v ∈ W (via lieSpan_le).
-- Sub-goal `v_mem_of_w_nonzero` carries the substantive content (any non-zero
-- sub-LieSubmodule of the cyclic span contains v itself).
theorem s9906 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0),
  ∀ (W : LieSubmodule R (t.toLieSubalgebra R) M),
    W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} →
    W = ⊥ ∨ W = LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v}  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hW
  by_cases hWbot : W = ⊥
  · exact Or.inl hWbot
  · refine Or.inr (le_antisymm hW ?_)
    have h_v_mem : v ∈ W :=
      v_mem_of_w_nonzero R L M t hv hvne W hW hWbot
    rw [LieSubmodule.lieSpan_le, Set.singleton_subset_iff]
    exact h_v_mem

end Problems.sl2_v_n_irreducible
