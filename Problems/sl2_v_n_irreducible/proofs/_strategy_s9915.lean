import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_lie_y_fpow_v_mem

namespace Problems.sl2_v_n_irreducible

-- Reduce ⁅y, m⁆ ∈ span{fᵏ·v} by Submodule.span_induction on m.
-- Generator case is the single sub-goal `lie_y_fpow_v_mem`
-- (y in sl₂-subalgebra, m = fᵏ·v concrete); zero/add/smul cases
-- close by `lie_add`, `lie_smul` and submodule linearity.
theorem s9915
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) :
    ∀ (y : t.toLieSubalgebra R) (m : M),
      m ∈ Submodule.span R (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)) →
      ⁅y, m⁆ ∈ Submodule.span R
        (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))  := by
  have h_sub := lie_y_fpow_v_mem R L M t hv
  intro y m hm
  induction hm using Submodule.span_induction with
  | mem x hx =>
    obtain ⟨k, rfl⟩ := hx
    exact h_sub y k
  | zero => simp
  | add x z hx hz ih1 ih2 =>
    rw [lie_add]
    exact Submodule.add_mem _ ih1 ih2
  | smul a x hx ih =>
    rw [lie_smul]
    exact Submodule.smul_mem _ a ih

end Problems.sl2_v_n_irreducible
