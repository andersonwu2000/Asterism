import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_lie_e_fpow_v_mem
import Problems.sl2_v_n_irreducible.proofs.L_lie_f_fpow_v_mem
import Problems.sl2_v_n_irreducible.proofs.L_lie_h_fpow_v_mem

namespace Problems.sl2_v_n_irreducible

-- Reduce ⁅y, fᵏ·v⁆ ∈ span to the three basis cases ⁅e,·⁆, ⁅f,·⁆, ⁅h,·⁆.
-- mem_toLieSubalgebra_iff unfolds y as c₁•e + c₂•f + c₃•⁅e,f⁆; t.lie_e_f rewrites
-- the third summand to c₃•h, then bilinearity reduces to the three sub-claims.
theorem s9917
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R))
    (y : t.toLieSubalgebra R) (k : ℕ) :
    ⁅y, ((LieModule.toEnd R L M f) ^ k) v⁆ ∈
      Submodule.span R (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))  := by
  have h_e := lie_e_fpow_v_mem R L M t hv k
  have h_f := lie_f_fpow_v_mem R L M t hv k
  have h_h := lie_h_fpow_v_mem R L M t hv k
  obtain ⟨c₁, c₂, c₃, hy⟩ := (IsSl2Triple.mem_toLieSubalgebra_iff (R := R)).mp y.2
  change ⁅(y : L), ((LieModule.toEnd R L M f) ^ k) v⁆ ∈ _
  rw [hy, t.lie_e_f, add_lie, add_lie, smul_lie, smul_lie, smul_lie]
  exact Submodule.add_mem _
    (Submodule.add_mem _ (Submodule.smul_mem _ _ h_e) (Submodule.smul_mem _ _ h_f))
    (Submodule.smul_mem _ _ h_h)

end Problems.sl2_v_n_irreducible
