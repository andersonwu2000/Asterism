import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- sum_decomp_to_neg: Finset.sum splitting — derives comp = -chain from hg by
--   collapsing each chain fiber to its bottom term (habove kills j>0 terms,
--   hv_chain identifies j=0 as D⟨t,0⟩) then reassembling via
--   Finset.sum_sigma + Fintype.sum_sum_type + Fin.sum_univ_one.
theorem sum_decomp_to_neg
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
    -- Reduce each chain fiber to its bottom term
    have chain_reduce : ∀ t : {t : Fin p // 0 < l t},
        ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩ =
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • D ⟨t.1, ⟨0, t.2⟩⟩ := by
      intro t
      rw [Finset.sum_eq_single (0 : Fin (l t.1 + 1))]
      · have hzero : v ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = D ⟨t.1, ⟨0, t.2⟩⟩ := by
          have h := hv_chain t ⟨0, t.2⟩
          simpa [Fin.castSucc, Fin.ext_iff] using h
        rw [hzero]
      · intro j _ hj0
        simp [habove t j (Fin.pos_of_ne_zero hj0)]
      · simp
    -- Split hg into chain + comp parts, using the fact that:
    have heq : (∑ t : {t : Fin p // 0 < l t},
          ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩) +
        (∑ c : Fin m, ∑ j : Fin 1, g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩) =
        ∑ i, g i • v i := by
      conv_rhs =>
        rw [show (Finset.univ : Finset (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
              Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
                (fun _ : Fin m => 1) s))) =
              Finset.sigma Finset.univ (fun s => Finset.univ) from
            Finset.univ_sigma_univ.symm]
        rw [Finset.sum_sigma]
      rw [Fintype.sum_sum_type]
      rfl
    simp only [Fin.sum_univ_one, hv_C] at heq
    simp_rw [chain_reduce] at heq
    exact heq.trans hg
end Problems.LinearAlgebra.jordan_normal_form
