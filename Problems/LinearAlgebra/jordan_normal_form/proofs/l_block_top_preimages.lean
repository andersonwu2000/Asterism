import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- block_top_preimages: every basis vector of range N has an N-preimage;
-- witnesses chosen via LinearMap.mem_range since each d ⟨t,j⟩ ∈ range N by construction.
-- entry_kind: Builder
theorem block_top_preimages
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
  have key : ∀ s : Σ t : Fin p, Fin (l t), ∃ w : W, N w = ↑(d s) :=
    fun s => LinearMap.mem_range.mp (d s).2
  choose x hx using key
  exact ⟨x, fun t j => hx ⟨t, j⟩⟩

end Problems.LinearAlgebra.jordan_normal_form
