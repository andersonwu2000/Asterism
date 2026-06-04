import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- block_top_preimages_2: each range-basis element has a preimage under N;
-- pick via LinearMap.mem_range on the subtype membership (d tj).2
theorem block_top_preimages_2
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ x : (Σ t : Fin p, Fin (l t)) → W,
      ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W) := by
  refine ⟨fun tj => (LinearMap.mem_range.mp (d tj).2).choose, ?_⟩
  intro t j
  exact (LinearMap.mem_range.mp (d ⟨t, j⟩).2).choose_spec

end Problems.LinearAlgebra.jordan_normal_form
