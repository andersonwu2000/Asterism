import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- inl_bottom_kill: chain bottom v⟨inl t,0⟩ maps to 0 under N, via hd's j=0 case and hv_chain
theorem inl_bottom_kill
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (m : ℕ)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W)) :
    ∀ t : {t : Fin p // 0 < l t}, N (v ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) = 0 := by
  intro t
  have hcast : (⟨0, t.2⟩ : Fin (l t.1)).castSucc = (0 : Fin (l t.1 + 1)) := by
    simp
  rw [← hcast, hv_chain t ⟨0, t.2⟩]
  have hd0 := hd t.1 ⟨0, t.2⟩
  rcases hd0 with ⟨-, hrestr⟩ | ⟨i, hi, -⟩
  · have key : (N.restrict h_inv (d ⟨t.1, ⟨0, t.2⟩⟩) : W) = N (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W) := by
      simp [LinearMap.restrict_apply]
    rw [← key, hrestr]; simp
  · simp at hi

end Problems.LinearAlgebra.jordan_normal_form

