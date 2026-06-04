import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_exists_idx_nonzero_of_sum_ne_zero
import Problems.sl2_v_n_irreducible.proofs.L_exists_max_idx_with_zeros_above

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose into: (1) extract some i ≤ n with c i ≠ 0 from sum ≠ 0
-- (contrapositive: if all c i = 0 for i ≤ n, the sum vanishes), and
-- (2) given any nonzero coefficient ≤ n, pick the largest such index.
-- Combinator: thread sub1's existential into sub2's hypothesis chain.
theorem s9927 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (c : ℕ → R)
    (_hsumne : (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v) ≠ 0),
  ∃ j : ℕ, j ≤ n ∧ c j ≠ 0 ∧ ∀ i, j < i → i ≤ n → c i = 0  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne c _hsumne
  have h_exists := exists_idx_nonzero_of_sum_ne_zero R L M t _hv _hvne W _hWle _hWne w _hwW _hwne c _hsumne
  exact exists_max_idx_with_zeros_above R L M t _hv _hvne W _hWle _hWne w _hwW _hwne c _hsumne h_exists

end Problems.sl2_v_n_irreducible
