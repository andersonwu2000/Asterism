import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inl_zero_n_eq
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inr_zero_n_eq
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_sigma_drop_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- Decompose into three abstract sub-goals:
-- (i) `inl_zero_n_eq` — N(v⟨inl t, 0⟩) = 0 via hd's j=0 branch + hv_chain;
-- (ii) `inr_zero_n_eq` — N(v⟨inr c, 0⟩) = 0 since cb c ∈ C ⊆ ker N;
-- (iii) `sigma_drop_zero` — sigma-sum bookkeeping: any f vanishing on
--   inl-0 / inr indices equals its inl-succ sub-sum.
-- Closer applies (iii) to f := g • N ∘ v, discharging its premises via
-- (i)/(ii) wrapped by `smul_zero`.
theorem s11055
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K) :
    (∑ i, g i • N (v i)) =
      ∑ ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • N (v ⟨Sum.inl ti.1, ti.2.succ⟩)  := by
  have h_inl : ∀ t : {t : Fin p // 0 < l t},
      N (v ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) = 0 :=
    inl_zero_n_eq N h_inv p l d hd m v hv_chain
  have h_inr : ∀ c : Fin m,
      N (v ⟨Sum.inr c, (0 : Fin 1)⟩) = 0 :=
    inr_zero_n_eq N C hC1 p l m cb v hv_C
  exact sigma_drop_zero p l m (fun i => g i • N (v i))
    (fun t => by change g _ • N (v _) = 0; rw [h_inl t, smul_zero])
    (fun c => by change g _ • N (v _) = 0; rw [h_inr c, smul_zero])

end Problems.LinearAlgebra.jordan_normal_form
