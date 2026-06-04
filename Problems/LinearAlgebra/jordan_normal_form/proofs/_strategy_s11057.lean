import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_n_distrib_smul_sum
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_n_sum_collapse_to_inl_succ
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_n_v_inl_succ_eq_d

namespace Problems.LinearAlgebra.jordan_normal_form

-- Mirror the abstract 3-step decomposition pattern: linearity → reindex/drop-zero → per-element shift.
-- (1) `n_distrib_smul_sum`: N distributes through `∑ g i • v i` into `∑ g i • N (v i)`.
-- (2) `n_sum_collapse_to_inl_succ`: drop vanishing inl-bottom and inr-bottom terms; reindex
--     surviving inl-succ terms to `Σ t, Fin (l t.1)`.
-- (3) `n_v_inl_succ_eq_d`: per-element chain shift `N (v ⟨inl t, j.succ⟩) = d ⟨t.1, j⟩`.
-- Combiner: rewrite by (1) and (2), then `Finset.sum_congr` applies (3) pointwise inside `g • _`.
theorem s11057
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
  have h_lin := n_distrib_smul_sum N p l m v g
  have h_reindex := n_sum_collapse_to_inl_succ N hN h_inv p l d hd x hx
    C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C g
  have h_chain := n_v_inl_succ_eq_d N h_inv p l d hd x hx m v hv_chain hv_top
  rw [h_lin, h_reindex]
  exact Finset.sum_congr rfl (fun ti _ => by rw [h_chain ti.1 ti.2])

end Problems.LinearAlgebra.jordan_normal_form
