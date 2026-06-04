import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_exists_nonzero_in_w
import Problems.sl2_v_n_irreducible.proofs.L_extract_scalar_v

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose: pick a non-zero w ∈ W (W ≠ ⊥), then run the sl₂ raising
-- extraction on w to land a non-zero scalar multiple of v in W; cancel
-- by λ⁻¹ to conclude v ∈ W.
-- sub1 (exists_nonzero_in_w): W ≠ ⊥ → ∃ w ∈ W, w ≠ 0. Generic LieSubmodule
--   fact (`eq_bot_iff` contrapositive); strictly simpler — no sl₂ content.
-- sub2 (extract_scalar_v): given an explicit non-zero w ∈ W (with W inside
--   the cyclic span), ∃ λ ≠ 0 with λ • v ∈ W. This is the substantive
--   Humphreys argument (expand w in the {fⁱ·v} basis, apply eᵏ for the
--   highest-power index k to land a non-zero scalar multiple of v).
--   Strictly simpler than the parent: the non-zero witness w is in hand.
-- Combinator: v = λ⁻¹ • (λ • v) ∈ W via `W.smul_mem` (Submodule smul-closure).
theorem s9921 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥),
  v ∈ W  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne
  obtain ⟨w, hwW, hwne⟩ :=
    exists_nonzero_in_w R L M t hv hvne W hWle hWne
  obtain ⟨lam, hlne, hlv⟩ :=
    extract_scalar_v R L M t hv hvne W hWle hWne w hwW hwne
  have hrw : v = lam⁻¹ • (lam • v) := by
    rw [smul_smul, inv_mul_cancel₀ hlne, one_smul]
  rw [hrw]
  exact W.smul_mem _ hlv

end Problems.sl2_v_n_irreducible
