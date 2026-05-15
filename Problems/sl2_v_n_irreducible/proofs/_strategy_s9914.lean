import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_kills_lower_fpow_v
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_m_fpow_m_eq_scalar_v

namespace Problems.sl2_v_n_irreducible

-- e-descent splits into vanishing on lower fⁱ·v (i < m) and scalar reduction at fᵐ·v.
-- Sub-goal A `e_pow_kills_lower_fpow_v`: e^j kills f^i v for i < j (sl₂ exhaustion).
-- Sub-goal B `e_pow_m_fpow_m_eq_scalar_v`: e^m f^m v = c•v with c ≠ 0 (product of (i+1)(n-i)).
-- Combinator: linearity (map_sum, LinearMap.map_smul) + Finset.sum_range_succ split.
theorem s9914
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0)
    (hwspan : w ∈ Submodule.span R
      (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)))
    (m : ℕ) (hmn : m ≤ n) (α : ℕ → R) (hαm : α m ≠ 0) :
  ∃ c : R, c ≠ 0 ∧ ((LieModule.toEnd R L M e) ^ m)
    (∑ i ∈ Finset.range (m + 1), α i • ((LieModule.toEnd R L M f) ^ i) v) = c • v  := by
  have h_kill :=
    e_pow_kills_lower_fpow_v R L M t hv hvne W hWle w hwW hwne hwspan m hmn α hαm
  have h_top :=
    e_pow_m_fpow_m_eq_scalar_v R L M t hv hvne W hWle w hwW hwne hwspan m hmn α hαm
  obtain ⟨c', hc'ne, h_eq⟩ := h_top
  refine ⟨α m * c', mul_ne_zero hαm hc'ne, ?_⟩
  rw [map_sum, Finset.sum_range_succ]
  have h_lower : ∀ i ∈ Finset.range m,
      ((LieModule.toEnd R L M e) ^ m) (α i • ((LieModule.toEnd R L M f) ^ i) v) = 0 := by
    intro i hi
    rw [LinearMap.map_smul, h_kill i m (Finset.mem_range.mp hi), smul_zero]
  rw [Finset.sum_eq_zero h_lower, zero_add, LinearMap.map_smul, h_eq, smul_smul]

end Problems.sl2_v_n_irreducible
