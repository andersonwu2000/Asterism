import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Package the LI + spanning chain family `v` from `h` into a `Module.Basis` via
-- `Module.Basis.mk hLI hsp`, then transport the chain property: `Module.Basis.mk_apply`
-- rewrites every `c ⟨s,_⟩` back to `v ⟨s,_⟩`, so the goal is literally `hchain s j`.
theorem s10977
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (h : ∃ (r : ℕ) (k : Fin r → ℕ) (v : (Σ s : Fin r, Fin (k s)) → W),
      LinearIndependent K v ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v) ∧
      ∀ (s : Fin r) (j : Fin (k s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩) :
    ∃ (r : ℕ) (k : Fin r → ℕ)
      (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W),
      ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩  := by
  obtain ⟨r, k, v, hLI, hsp, hchain⟩ := h
  refine ⟨r, k, Module.Basis.mk hLI hsp, ?_⟩
  intro s j
  simp only [Module.Basis.mk_apply]
  exact hchain s j

end Problems.LinearAlgebra.jordan_normal_form
