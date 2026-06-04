import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_succ_kills_f_pow_v_clean

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose: drop the unused c/j/W/w bookkeeping from the parent — the
-- conclusion `e^(i+1) (f^i v) = 0` only references the sl₂ triple `t`, the
-- primitive vector `v` of weight `n`, and the index `i`. The cleaned
-- sub-goal `e_pow_succ_kills_f_pow_v_clean` is the standard sl₂ descent
-- identity, universal in `i` (no `i ≤ n` or `i < j` hypothesis needed:
-- the relation e (f^k v) = k(n−k+1) • f^(k−1) v together with `e v = 0`
-- collapses by induction regardless of k vs n).
-- Combinator: intros and apply the cleaned sub-goal at the given `i`.
theorem s9932 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (c : ℕ → R)
    (_hsumne : (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v) ≠ 0)
    (j : ℕ) (_hjle : j ≤ n) (_hcjne : c j ≠ 0)
    (_hcabove : ∀ i, j < i → i ≤ n → c i = 0)
    (i : ℕ) (_hilt : i < j),
  ((LieModule.toEnd R L M e) ^ (i + 1)) (((LieModule.toEnd R L M f) ^ i) v) = 0  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv _hvne W _hWle _hWne w _hwW _hwne
    c _hsumne j _hjle _hcjne _hcabove i _hilt
  have h_e_pow_succ_kills_f_pow_v_clean := e_pow_succ_kills_f_pow_v_clean R L M t hv
  exact h_e_pow_succ_kills_f_pow_v_clean i
end Problems.sl2_v_n_irreducible
