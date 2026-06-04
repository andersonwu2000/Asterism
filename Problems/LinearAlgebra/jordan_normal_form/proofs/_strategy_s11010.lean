import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct leaf: the residual is exactly the `hg` dependence after the `habove` collapse.
-- Split `∑ i` over the Σ/⊕ index (`Finset.sum_sigma` + `Fintype.sum_sum_type`) into the
-- `Sum.inl` chain block and `Sum.inr` complement block. On each `inl` fiber `Fin.sum_univ_succ`
-- isolates `j=0`; `habove` zeroes every `j≥1` term and `hv_chain` (at `i=⟨0,t.2⟩`, whose
-- `castSucc` is `0`) rewrites the survivor to `g⟨inl t,0⟩ • d⟨t.1,0⟩`. Each `inr` fiber is
-- `Fin 1`, so `Fin.sum_univ_one` + `hv_C` give `g⟨inr c,0⟩ • cb c`. Sorry-free; no sub-goals.
theorem s11010
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
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
      + (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W)) = 0  := by
  have hsplit :
      (∑ i, g i • v i)
        = (∑ t : {t : Fin p // 0 < l t},
              ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩)
          + (∑ c : Fin m, ∑ j : Fin 1, g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩) := by
    rw [← Finset.univ_sigma_univ, Finset.sum_sigma, Fintype.sum_sum_type]
    rfl
  have hinl :
      (∑ t : {t : Fin p // 0 < l t},
          ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩)
        = ∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W) := by
    apply Finset.sum_congr rfl
    intro t _
    rw [Fin.sum_univ_succ,
      Finset.sum_eq_zero (fun j _ => by rw [habove t j.succ (by simp), zero_smul]), add_zero]
    congr 1
    exact hv_chain t ⟨0, t.2⟩
  have hinr :
      (∑ c : Fin m, ∑ j : Fin 1, g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩)
        = ∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W) := by
    apply Finset.sum_congr rfl
    intro c _
    rw [Fin.sum_univ_one]
    congr 1
    exact hv_C c
  rw [← hinl, ← hinr, ← hsplit]
  exact hg

end Problems.LinearAlgebra.jordan_normal_form
