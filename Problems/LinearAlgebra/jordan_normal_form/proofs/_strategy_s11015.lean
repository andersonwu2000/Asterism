import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s11015
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
    ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1)),
        N (v ⟨Sum.inl t, j.succ⟩) = (↑(d ⟨t.1, j⟩) : W)  := by
  intro t j
  by_cases hlt : (j : ℕ) + 1 < l t.1
  · -- j.succ is interior: castSucc of ⟨j+1, hlt⟩
    have hsucc : j.succ = (⟨(j : ℕ) + 1, hlt⟩ : Fin (l ↑t)).castSucc := by
      ext; simp [Fin.val_succ]
    rw [hsucc, hv_chain]
    have hd' := hd t.1 ⟨(j : ℕ) + 1, hlt⟩
    rcases hd' with ⟨h0, -⟩ | ⟨i, hi_eq, hi_val⟩
    · simp at h0
    · -- hi_eq : ↑i + 1 = ↑⟨↑j + 1, hlt⟩ = ↑j + 1, so i = j
      -- hi_val : (N.restrict h_inv) (d ⟨↑t, ⟨↑j + 1, hlt⟩⟩) = d ⟨↑t, i⟩
      have hi : i = j := by ext; simp at hi_eq ⊢; omega
      rw [hi] at hi_val
      -- hi_val : (N.restrict h_inv) (d ⟨↑t, ⟨↑j + 1, hlt⟩⟩) = d ⟨↑t, j⟩
      have := congr_arg Subtype.val hi_val
      simp [LinearMap.restrict_apply] at this
      exact this
  · -- j.succ = Fin.last
    have hj_eq : (j : ℕ) + 1 = l ↑t := by omega
    have hsucc : j.succ = Fin.last (l ↑t) := by
      ext; simp [Fin.val_succ, Fin.val_last]; omega
    rw [hsucc, hv_top]
    have hfin : (⟨l ↑t - 1, (by have := t.2; omega)⟩ : Fin (l ↑t)) = j := by
      ext; simp; omega
    rw [hfin]
    exact hx t.1 j

end Problems.LinearAlgebra.jordan_normal_form