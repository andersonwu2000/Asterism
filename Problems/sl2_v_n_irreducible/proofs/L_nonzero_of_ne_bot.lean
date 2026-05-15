import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- nonzero_of_ne_bot: LieSubmodule.mem_bot + ext: W ≠ ⊥ implies W contains a nonzero element.
theorem nonzero_of_ne_bot
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (hWne : W ≠ ⊥) :
  ∃ w : M, w ∈ W ∧ w ≠ 0 := by
  by_contra h
  push Not at h
  apply hWne
  ext x
  simp only [LieSubmodule.mem_bot]
  exact ⟨fun hx => h x hx, fun hx => hx ▸ W.zero_mem⟩

end Problems.sl2_v_n_irreducible
