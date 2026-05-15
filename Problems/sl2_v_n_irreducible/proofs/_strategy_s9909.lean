import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_descent_witness
import Problems.sl2_v_n_irreducible.proofs.L_iterate_e_in_w

namespace Problems.sl2_v_n_irreducible

-- Reduce ∃ c≠0, c•v ∈ W to (descent witness) + (iterated-e closure of W).
-- Sub-goal `descent_witness` carries the substantive Humphreys e-descent:
-- expand w in the {fᵏ·v} spanning set, take the largest non-vanishing power
-- and apply that many e's to land on a non-zero scalar multiple of v.
-- Sub-goal `iterate_e_in_W` is the generic iteration (induction on k) of the
-- fact that W is closed under the e-action because e ∈ t.toLieSubalgebra R.
theorem s9909
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0) :
  ∃ c : R, c ≠ 0 ∧ c • v ∈ W  := by
  have h_descent := descent_witness R L M t hv hvne W hWle w hwW hwne
  have h_iter := iterate_e_in_w R L M t hv hvne W hWle w hwW hwne

  obtain ⟨k, c, hc, heq⟩ := h_descent
  have hekw : ((LieModule.toEnd R L M e) ^ k) w ∈ W := h_iter k
  rw [heq] at hekw
  exact ⟨c, hc, hekw⟩

end Problems.sl2_v_n_irreducible

