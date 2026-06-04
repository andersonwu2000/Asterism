import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- chain_succ_n_eq_d: per-element chain shift N(v⟨inl t, j.succ⟩) = d⟨t.1, j⟩.
-- Case split: j last → use hv_top + hx; j interior → use hv_chain + hd predecessor.
-- entry_kind: Builder
theorem chain_succ_n_eq_d
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (m : ℕ)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩) :
    ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1)),
        N (v ⟨Sum.inl t, j.succ⟩) = (↑(d ⟨t.1, j⟩) : W) := by
  intro t j
  by_cases hjl : (j : ℕ) + 1 = l t.1
  · -- j is last: j.succ = Fin.last (l t.1)
    have hsucc_last : j.succ = Fin.last (l t.1) := by
      apply Fin.ext; simp only [Fin.val_succ]; exact hjl
    rw [hsucc_last, hv_top]
    have hjeq : j = ⟨l t.1 - 1, by omega⟩ := by
      apply Fin.ext; change (j : ℕ) = l t.1 - 1; omega
    rw [← hjeq]; exact hx t.1 j
  · -- j is not last: j.succ = castSucc of (j.val+1)
    have hjlt : (j : ℕ) + 1 < l t.1 := by omega
    have hsucc_cs : j.succ = (⟨(j : ℕ) + 1, hjlt⟩ : Fin (l t.1)).castSucc := by
      apply Fin.ext; simp only [Fin.val_succ, Fin.val_castSucc]
    rw [hsucc_cs, hv_chain]
    rcases hd t.1 ⟨(j : ℕ) + 1, hjlt⟩ with ⟨h0, _⟩ | ⟨i, hi, hrestr⟩
    · simp at h0
    · have hij : i = j := by apply Fin.ext; simp at hi; omega
      have hcoe : ((N.restrict h_inv) (d ⟨t.1, ⟨(j : ℕ) + 1, hjlt⟩⟩) : W) =
          N (↑(d ⟨t.1, ⟨(j : ℕ) + 1, hjlt⟩⟩)) := by
        simp [LinearMap.restrict_apply]
      rw [← hcoe, hrestr, hij]

end Problems.LinearAlgebra.jordan_normal_form
