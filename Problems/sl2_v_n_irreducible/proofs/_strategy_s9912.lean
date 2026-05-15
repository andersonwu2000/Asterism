import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_top_truncated_sum
import Problems.sl2_v_n_irreducible.proofs.L_max_index_extraction

namespace Problems.sl2_v_n_irreducible

-- Humphreys e-descent on the {fᵏ·v} cyclic span via max-index extraction.
-- Sub-goal A `max_index_extraction`: w expressed as Σ_{i ≤ m} αᵢ•fⁱ·v with m ≤ n and αₘ ≠ 0
-- (max index of non-zero coefficient exists since w ≠ 0; bounded by n since fᵏ·v = 0 for k > n).
-- Sub-goal B `e_pow_top_truncated_sum`: applying eᵐ to such a truncated sum lands on a
-- non-zero scalar of v (lower fⁱ·v with i<m are killed by eᵐ; the αₘ•fᵐ·v term descends
-- via the standard `(i+1)(n−i)` coefficient formula, accumulating a non-zero product).
theorem s9912
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0)
    (hwspan : w ∈ Submodule.span R
      (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))) :
  ∃ k : ℕ, ∃ c : R, c ≠ 0 ∧ ((LieModule.toEnd R L M e) ^ k) w = c • v  := by
  have h_extract :=
    max_index_extraction R L M t hv hvne W hWle w hwW hwne hwspan
  obtain ⟨m, hmn, α, hαm, hw_eq⟩ := h_extract
  have h_descent :=
    e_pow_top_truncated_sum R L M t hv hvne W hWle w hwW hwne hwspan m hmn α hαm
  obtain ⟨c, hc, h_eq⟩ := h_descent
  exact ⟨m, c, hc, by rw [hw_eq]; exact h_eq⟩

end Problems.sl2_v_n_irreducible
