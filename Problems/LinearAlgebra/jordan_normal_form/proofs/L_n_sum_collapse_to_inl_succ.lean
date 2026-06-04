import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- n_sum_collapse_to_inl_succ: collapses ∑ over all v-indices to inl-succ terms only;
-- inl-bottom terms vanish (chain-bottom maps to 0 via hd), inr terms vanish (C ≤ ker N).
-- entry_kind: Builder
theorem n_sum_collapse_to_inl_succ
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
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
               (fun _ : Fin m => 1) s)) → K) :
    (∑ i, g i • N (v i)) =
      (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • N (v ⟨Sum.inl ti.1, ti.2.succ⟩)) := by

  rw [Fintype.sum_sigma, Fintype.sum_sum_type]
  have h_inr : ∀ c : Fin m,
      (∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
                            (fun _ : Fin m => 1) (Sum.inr c)),
        g ⟨Sum.inr c, j⟩ • N (v ⟨Sum.inr c, j⟩)) = 0 := fun c => by
    simp only [Sum.elim_inr]
    have hker : N ((cb c : W)) = 0 :=
      LinearMap.mem_ker.mp (hC1 (Submodule.coe_mem _))
    simp [hv_C c, hker]
  simp_rw [h_inr, Finset.sum_const_zero, add_zero]
  have h_inl_bot : ∀ (t : {t : Fin p // 0 < l t}),
      N (v ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) = 0 := fun t => by
    have hlt : 0 < l t.1 := t.2
    have hj0 : (⟨0, hlt⟩ : Fin (l t.1)).castSucc = (0 : Fin (l t.1 + 1)) := by
      simp [Fin.castSucc]
    rw [← hj0, hv_chain t ⟨0, hlt⟩]
    have hd0 : (N.restrict h_inv) (d ⟨t.1, ⟨0, hlt⟩⟩) = 0 :=
      ((hd t.1 ⟨0, hlt⟩).resolve_right
        (fun ⟨i, hi, _⟩ => by simp at hi)).2
    have heq := LinearMap.restrict_apply h_inv (d ⟨t.1, ⟨0, hlt⟩⟩)
    rw [hd0] at heq
    simpa using heq.symm
  have h_inl_split : ∀ (t : {t : Fin p // 0 < l t}),
      (∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
                            (fun _ : Fin m => 1) (Sum.inl t)),
        g ⟨Sum.inl t, j⟩ • N (v ⟨Sum.inl t, j⟩)) =
      ∑ j : Fin (l t.1), g ⟨Sum.inl t, j.succ⟩ • N (v ⟨Sum.inl t, j.succ⟩) := fun t => by
    simp only [Sum.elim_inl]
    change ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • N (v ⟨Sum.inl t, j⟩) = _
    rw [Fin.sum_univ_succ]
    simp [h_inl_bot t]
  simp_rw [h_inl_split]
  rw [Fintype.sum_sigma]

end Problems.LinearAlgebra.jordan_normal_form
