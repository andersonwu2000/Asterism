import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- inl_zero_n_eq: N(v⟨inl t, 0⟩) = 0 via hd's j=0 branch (castSucc bridges v to d)
theorem inl_zero_n_eq
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
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
    ∀ t : {t : Fin p // 0 < l t},
      N (v ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) = 0 := by
  intro t
  set j0 : Fin (l t.1) := ⟨0, t.2⟩
  have hcast : j0.castSucc = (0 : Fin (l t.1 + 1)) := by ext; simp [j0]
  rw [← hcast, hv_chain t j0]
  -- goal: N ↑(d ⟨t.1, j0⟩) = 0
  have hd0 := hd t.1 j0
  simp only [j0] at hd0
  rcases hd0 with ⟨-, hN⟩ | ⟨i, hi, -⟩
  · -- hN : (N.restrict h_inv) (d ⟨t.1, j0⟩) = 0 as an element of range N
    have hval := congr_arg Subtype.val hN
    simp only [LinearMap.restrict_apply, ZeroMemClass.coe_zero] at hval
    exact hval
  · omega

end Problems.LinearAlgebra.jordan_normal_form