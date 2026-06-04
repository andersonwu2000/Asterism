import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inf_ker_restrict_bridge
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_restrict_ker_finrank_count

namespace Problems.LinearAlgebra.jordan_normal_form

-- finrank(range N ⊓ ker N) = #{0 < l t} via a two-step transitive equality.
-- h_bridge: the W-side intersection range N ⊓ ker N is the image under the subtype
--   embedding of ker (N.restrict h_inv) (the kernel of N's restriction to range N),
--   so the two finranks agree — an abstract restriction↔intersection fact, no Jordan
--   structure needed.
-- h_count: ker (N.restrict h_inv) is spanned by the chain bottoms {d⟨t,0⟩ : 0 < l t},
--   an LI subfamily of the Jordan basis d, so its finrank is the bottom-count
--   #{0 < l t} (strong-hd: the j=0 constraint forces proper chains).
-- Eq.trans chains the two. Each sub-goal is local and abstract over (f,p) / (M,d).
theorem s11000
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W)
      = Fintype.card {t : Fin p // 0 < l t}  := by
  have h_bridge := inf_ker_restrict_bridge N (LinearMap.range N) h_inv
  have h_count := restrict_ker_finrank_count (N.restrict h_inv) d hd
  exact h_bridge.trans h_count

end Problems.LinearAlgebra.jordan_normal_form
