import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inl_bottom_kill
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inl_succ_collapse
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inr_bottom_kill

namespace Problems.LinearAlgebra.jordan_normal_form

-- Collapse `∑ g i • N(v i)` to the inl-succ sub-sum via three sub-lemmas.
-- `inl_bottom_kill`: chain bottom v⟨inl t,0⟩ ↦ 0 (re-declares the proved sibling).
-- `inr_bottom_kill`: complement bottom v⟨inr c,0⟩ ↦ 0 (re-declares the proved sibling).
-- `inl_succ_collapse`: generic sigma identity — given f vanishes at inl/inr bottoms,
--   ∑ f reduces to the inl-succ-indexed sub-sum (re-declares the proved sibling).
-- Combine via `refine inl_succ_collapse p l m (fun i => g i • N(v i)) ?_ ?_`; the
-- two side conditions discharge by `simp only [h_*_zero, smul_zero]`, which
-- beta-reduces the lambda before the rewrites — fixing the s11020 combiner failure
-- (`rw [h_inl_zero t]` failed to match inside an un-beta'd `(fun i => …) ⟨…, 0⟩`).
theorem s11035
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
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K) :
    (∑ i, g i • N (v i)) =
      (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • N (v ⟨Sum.inl ti.1, ti.2.succ⟩))  := by
  have h_inl_zero := inl_bottom_kill N h_inv p l d hd m v hv_chain
  have h_inr_zero := inr_bottom_kill N C hC1 p l m cb v hv_C
  refine inl_succ_collapse p l m (fun i => g i • N (v i)) ?_ ?_
  · intro t
    simp only [h_inl_zero t, smul_zero]
  · intro c
    simp only [h_inr_zero c, smul_zero]

end Problems.LinearAlgebra.jordan_normal_form
