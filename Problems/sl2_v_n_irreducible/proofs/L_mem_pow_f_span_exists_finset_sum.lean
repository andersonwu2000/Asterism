import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- mem_pow_f_span_exists_finset_sum: span membership over image of finset unpacks to
-- coefficient sum via Submodule.mem_span_image_finset_iff_exists_fun'
theorem mem_pow_f_span_exists_finset_sum : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (x : M) (_hxsp : x ∈ Submodule.span R
      ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ))),
  ∃ c : ℕ → R,
    x = ∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne x hxsp
  rw [Submodule.mem_span_image_finset_iff_exists_fun'] at hxsp
  obtain ⟨c, hc⟩ := hxsp
  exact ⟨c, hc.symm⟩

end Problems.sl2_v_n_irreducible
