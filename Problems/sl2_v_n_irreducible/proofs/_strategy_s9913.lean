import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_fpow_span_lie_closed

namespace Problems.sl2_v_n_irreducible

-- Build a LieSubmodule N whose carrier is the R-Submodule span of {fᵏ·v : k ∈ ℕ}.
-- Closure under the sl₂-subalgebra Lie action is the one sub-goal; v ∈ N is f⁰·v;
-- lieSpan_le on the singleton {v} then forces lieSpan {v} ≤ N, closing the parent.
theorem s9913
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) :
    ∀ x : M, x ∈ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} →
      x ∈ Submodule.span R
        (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))  := by
  have h_closure := fpow_span_lie_closed R L M t hv
  let N : LieSubmodule R (t.toLieSubalgebra R) M :=
    { toSubmodule :=
        Submodule.span R (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v))
      lie_mem := fun {y m} hm => h_closure y m hm }
  have hv_mem : v ∈ N := by
    change v ∈ Submodule.span R _
    apply Submodule.subset_span
    exact ⟨0, by simp⟩
  exact fun x hx => (LieSubmodule.lieSpan_le (N := N)).mpr
    (Set.singleton_subset_iff.mpr hv_mem) hx

end Problems.sl2_v_n_irreducible
