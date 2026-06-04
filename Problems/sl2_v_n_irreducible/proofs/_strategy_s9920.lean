import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_v_mem_of_ne_bot

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose: a non-bot sub-LieSubmodule contained in the cyclic sl₂-span of v
-- must itself contain v; the reverse inclusion then follows by lieSpan_le.
-- sub1 (v_mem_of_ne_bot): if W ≤ lieSpan{v} is non-⊥, then v ∈ W (sl₂ extraction).
-- Combinator: case split on W = ⊥; otherwise lift v ∈ W via lieSpan_le + le_antisymm.
theorem s9920 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0),
  ∀ (W : LieSubmodule R (t.toLieSubalgebra R) M),
    W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} →
    W = ⊥ ∨ W = LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v}  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle
  by_cases hW : W = ⊥
  · exact Or.inl hW
  · refine Or.inr (le_antisymm hWle ?_)
    have hvmem : v ∈ W := v_mem_of_ne_bot R L M t hv hvne W hWle hW
    exact LieSubmodule.lieSpan_le.mpr (Set.singleton_subset_iff.mpr hvmem)

end Problems.sl2_v_n_irreducible
