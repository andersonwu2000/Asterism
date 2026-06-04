import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_succ_n_eq_d
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_push_n_smul_sum
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_reindex_n_sum_drop_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- Decompose `N (∑ gᵢ • vᵢ) = ∑_{t,j} g⟨inl t, j.succ⟩ • d⟨t.1, j⟩` into three abstract steps:
-- (1) push N through the smul sum (`push_n_smul_sum`); (2) drop the vanishing inl-zero
-- and inr-zero terms and reindex the survivors to `Σ t, Fin (l t.1)` via `ti.2.succ`
-- (`reindex_n_sum_drop_zero`); (3) the per-element chain shift `N (v ⟨inl t, j.succ⟩) = d ⟨t.1, j⟩`
-- (`chain_succ_n_eq_d`). The closer rewrites by (1) and (2), then `Finset.sum_congr` applies (3)
-- pointwise inside the smul. Each sub-goal is strictly more abstract: (1) is pure linearity, (2)
-- is bookkeeping over the sigma index, (3) is the pointwise structural identity.
theorem s11029
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
    N (∑ i, g i • v i) =
      (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • (↑(d ⟨ti.1.1, ti.2⟩) : W))  := by
  have h_lin := push_n_smul_sum N p l m v g
  have h_reindex := reindex_n_sum_drop_zero N h_inv p l d hd C hC1 m cb v hv_chain hv_C g
  have h_chain := chain_succ_n_eq_d N h_inv p l d hd x hx m v hv_chain hv_top
  rw [h_lin, h_reindex]
  exact Finset.sum_congr rfl (fun ti _ => by rw [h_chain ti.1 ti.2])

end Problems.LinearAlgebra.jordan_normal_form
