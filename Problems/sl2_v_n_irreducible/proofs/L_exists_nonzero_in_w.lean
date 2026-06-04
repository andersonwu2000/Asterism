import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- exists_nonzero_in_w: W ≠ ⊥ implies ∃ nonzero w ∈ W via LieSubmodule.eq_bot_iff contrapositive
theorem exists_nonzero_in_w : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥),
  ∃ w ∈ W, w ≠ 0 := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne
  rw [ne_eq, LieSubmodule.eq_bot_iff] at _hWne
  push Not at _hWne
  exact _hWne

end Problems.sl2_v_n_irreducible
