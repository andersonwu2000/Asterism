import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_fpow_submodule_span_descent
import Problems.sl2_v_n_irreducible.proofs.L_w_in_fpow_submodule_span

namespace Problems.sl2_v_n_irreducible

-- Two-step Humphreys descent on the cyclic span.
-- Sub-goal A `w_in_fpow_submodule_span`: w lies in the R-Submodule span of
-- {fᵏ·v : k ∈ ℕ} — a concrete description of `lieSpan R (t.toLieSubalgebra R) {v}`
-- as a Submodule, stripping out the descent argument entirely.
-- Sub-goal B `fpow_submodule_span_descent`: any non-zero element of that Submodule
-- span admits some eᵐ landing on a non-zero scalar multiple of v — the substantive
-- descent argument, now divorced from the LieSubmodule structure of W.
theorem s9910
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0) :
  ∃ k : ℕ, ∃ c : R, c ≠ 0 ∧ ((LieModule.toEnd R L M e) ^ k) w = c • v  := by
  have h_span :=
    w_in_fpow_submodule_span R L M t hv hvne W hWle w hwW hwne
  exact fpow_submodule_span_descent R L M t hv hvne W hWle w hwW hwne h_span

end Problems.sl2_v_n_irreducible
