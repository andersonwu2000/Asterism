import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- n_v_inl_succ_eq_d: per-element chain shift using hv_chain/hv_top and hx/hd
-- entry_kind: Builder
theorem n_v_inl_succ_eq_d
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
  by_cases hj : j.val + 1 = l t.1
  · -- j.succ = Fin.last (l t.1), and j = ⟨l t.1 - 1, _⟩
    have hlt1 : l t.1 - 1 < l t.1 := by omega
    have hjsucc : j.succ = Fin.last (l t.1) := by
      ext; simp [Fin.val_succ, Fin.val_last]; omega
    have hjval : j = ⟨l t.1 - 1, hlt1⟩ := by
      apply Fin.ext; show (j : ℕ) = l t.1 - 1; omega
    rw [hjsucc, hv_top, hjval]
    exact hx t.1 ⟨l t.1 - 1, hlt1⟩
  · -- j.val + 1 < l t.1, so j.succ = castSucc of ⟨j.val+1, _⟩
    have hlt : j.val + 1 < l t.1 := by omega
    have hj' : j.val + 1 < l t.1 := hlt
    set j' : Fin (l t.1) := ⟨j.val + 1, hlt⟩ with hj'_def
    have hjsucc : j.succ = j'.castSucc := by
      ext; simp [Fin.val_succ, Fin.val_castSucc, hj'_def]
    rw [hjsucc, hv_chain t j']
    -- goal: N (↑(d ⟨t.1, j'⟩)) = ↑(d ⟨t.1, j⟩)
    rcases hd t.1 j' with ⟨h0, _⟩ | ⟨i, hi_val, hi_eq⟩
    · -- j'.val = 0, contradicts j'.val = j.val + 1 ≥ 1
      simp [hj'_def] at h0
    · -- i.val + 1 = j'.val = j.val + 1, so i = j
      have hij : i = j := by
        ext; simp [hj'_def] at hi_val; omega
      rw [hij] at hi_eq
      -- hi_eq : N.restrict h_inv (d ⟨t.1, j'⟩) = d ⟨t.1, j⟩ in range N
      have hcoe : (↑((N.restrict h_inv) (d ⟨t.1, j'⟩)) : W) = N (↑(d ⟨t.1, j'⟩)) := by
        simp [LinearMap.restrict_apply]
      rw [← hcoe]
      exact congr_arg Subtype.val hi_eq

end Problems.LinearAlgebra.jordan_normal_form