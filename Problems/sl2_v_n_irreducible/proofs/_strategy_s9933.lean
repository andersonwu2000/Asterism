import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_lie_e_f_pow_v_mem_span
import Problems.sl2_v_n_irreducible.proofs.L_lie_f_f_pow_v_mem_span
import Problems.sl2_v_n_irreducible.proofs.L_lie_h_f_pow_v_mem_span

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose ⁅l, (fⁱ)v⁆ for l ∈ t.toLieSubalgebra R by unpacking
-- l = c₁•e + c₂•f + c₃•⁅e,f⁆ via `IsSl2Triple.mem_toLieSubalgebra_iff`
-- and rewriting ⁅e,f⁆ = h, leaving three generator sub-goals:
--   sub_e (lie_e_f_pow_v_mem_span): ⁅e, (fⁱ)v⁆ ∈ span — uses `lie_e_pow_succ_toEnd_f`
--   sub_f (lie_f_f_pow_v_mem_span): ⁅f, (fⁱ)v⁆ ∈ span — uses `lie_f_pow_toEnd_f`
--   sub_h (lie_h_f_pow_v_mem_span): ⁅h, (fⁱ)v⁆ ∈ span — uses `lie_h_pow_toEnd_f`
-- Combinator: convert subalg bracket to L-bracket (rfl), distribute via
-- `add_lie`/`smul_lie`, close with `Submodule.{add_mem,smul_mem}` on each sub-goal.
theorem s9933 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (l : (t.toLieSubalgebra R)) (i : ℕ) (_hi : i < n + 1),
  ⁅l, ((LieModule.toEnd R L M f) ^ i) v⁆ ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ))  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne l i hi
  have h_e := lie_e_f_pow_v_mem_span R L M t hv hvne W hWle hWne w hwW hwne i hi
  have h_f := lie_f_f_pow_v_mem_span R L M t hv hvne W hWle hWne w hwW hwne i hi
  have h_h := lie_h_f_pow_v_mem_span R L M t hv hvne W hWle hWne w hwW hwne i hi
  obtain ⟨c₁, c₂, c₃, hl⟩ := IsSl2Triple.mem_toLieSubalgebra_iff.mp l.2
  change ⁅(↑l : L), ((LieModule.toEnd R L M f) ^ i) v⁆ ∈ _
  rw [show (↑l : L) = c₁ • e + c₂ • f + c₃ • h from by rw [hl, t.lie_e_f]]
  rw [add_lie, add_lie, smul_lie, smul_lie, smul_lie]
  exact Submodule.add_mem _
    (Submodule.add_mem _ (Submodule.smul_mem _ _ h_e) (Submodule.smul_mem _ _ h_f))
    (Submodule.smul_mem _ _ h_h)

end Problems.sl2_v_n_irreducible
