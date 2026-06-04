import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_pushforward_d_eq_alias

namespace Problems.LinearAlgebra.jordan_normal_form

-- Use the already-abstract `pushforward_d_eq` identity:
--   N (∑ gᵢ • vᵢ) = ∑_{ti} g⟨inl ti.1, ti.2.succ⟩ • d⟨ti.1.1, ti.2⟩
-- Then `hg : ∑ gᵢ • vᵢ = 0` collapses the LHS via `map_zero`, giving the goal.
theorem s11036
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0) :
    (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • (↑(d ⟨ti.1.1, ti.2⟩) : W)) = 0  := by
  have heq := pushforward_d_eq_alias N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g
  rw [← heq, hg, map_zero]

end Problems.LinearAlgebra.jordan_normal_form
