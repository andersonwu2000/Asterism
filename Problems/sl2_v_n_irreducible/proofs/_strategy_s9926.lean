import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_diag_scalar_v
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_low_kills

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Apply e^j to the sum ∑ i ∈ range(n+1), c i • f^i v and isolate the i = j term.
-- sub1 (e_pow_low_kills): for i < j, applying j copies of e to f^i v gives 0 (primitive vector).
-- sub2 (e_pow_diag_scalar_v): for j ≤ n, e^j (f^j v) = mu • v for some mu ≠ 0 (descent formula).
-- Combinator: linearity (map_sum, map_smul) + Finset.sum_eq_single j, using sub1 for i < j,
-- hcabove for j < i ≤ n, and sub2 for i = j. Resulting scalar c j * mu is nonzero.
theorem s9926 : ∀ (R : Type*) [Field R] [CharZero R]
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
    (_hcabove : ∀ i, j < i → i ≤ n → c i = 0),
  ∃ lam : R, lam ≠ 0 ∧
    ((LieModule.toEnd R L M e) ^ j)
        (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v)
      = lam • v  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove
  have h_low : ∀ i, i < j →
      ((LieModule.toEnd R L M e) ^ j) (((LieModule.toEnd R L M f) ^ i) v) = 0 :=
    fun i hi => e_pow_low_kills R L M t hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove i hi
  have h_diag := e_pow_diag_scalar_v R L M t hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove

  obtain ⟨mu, hmune, hmu_eq⟩ := h_diag
  refine ⟨c j * mu, mul_ne_zero hcjne hmune, ?_⟩
  rw [map_sum]
  have hj_mem : j ∈ Finset.range (n + 1) := Finset.mem_range.mpr (Nat.lt_succ_of_le hjle)
  rw [Finset.sum_eq_single j ?_ (fun h => absurd hj_mem h)]
  · rw [map_smul, hmu_eq, smul_smul]
  · intro i hi hij
    rw [map_smul]
    rcases lt_or_gt_of_ne hij with h_lt | h_gt
    · rw [h_low i h_lt, smul_zero]
    · rw [hcabove i h_gt (Nat.lt_succ_iff.mp (Finset.mem_range.mp hi)), zero_smul]

end Problems.sl2_v_n_irreducible
