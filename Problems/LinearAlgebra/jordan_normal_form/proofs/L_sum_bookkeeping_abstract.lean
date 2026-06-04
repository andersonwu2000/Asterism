import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- sum_bookkeeping_abstract: pure sum identity — from hg=0 and habove (g=0 on j≥1 chain entries),
-- the inr complement sum equals the negative of the inl chain-bottom sum.
-- Uses Fintype.sum_sigma + Fintype.sum_sum_type to split the sigma index, then
-- inr_simp (Fin 1 fiber) and inl_simp (habove kills j≥1, hv_chain supplies j=0).
-- entry_kind: Builder
theorem sum_bookkeeping_abstract
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (p m : ℕ) (l : Fin p → ℕ)
    (D : (Σ t : Fin p, Fin (l t)) → W)
    (CB : Fin m → W)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = D ⟨t.1, i⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = CB c)
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • CB c)
      = -(∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • D ⟨t.1, ⟨0, t.2⟩⟩) := by
  rw [eq_neg_iff_add_eq_zero, add_comm]
  rw [Fintype.sum_sigma, Fintype.sum_sum_type] at hg
  have inr_simp : ∀ c : Fin m,
      ∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
            (fun _ : Fin m => 1) (Sum.inr c)), g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩
      = g ⟨Sum.inr c, (0 : Fin 1)⟩ • CB c := by
    intro c; simp [hv_C]
  simp_rw [inr_simp] at hg
  have inl_simp : ∀ t : {t : Fin p // 0 < l t},
      ∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
            (fun _ : Fin m => 1) (Sum.inl t)), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩
      = g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • D ⟨t.1, ⟨0, t.2⟩⟩ := by
    intro t
    change ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩ = _
    rw [Fin.sum_univ_succ, add_comm]
    have hzero : ∑ i : Fin (l t.1), g ⟨Sum.inl t, i.succ⟩ • v ⟨Sum.inl t, i.succ⟩ = 0 := by
      apply Finset.sum_eq_zero
      intro i _
      simp [habove t i.succ (Fin.succ_pos i)]
    rw [hzero, zero_add]
    congr 1
    simpa [Fin.ext_iff] using hv_chain t ⟨0, t.2⟩
  simp_rw [inl_simp] at hg
  exact hg

end Problems.LinearAlgebra.jordan_normal_form
