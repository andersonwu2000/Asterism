import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_bottom_coeffs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_complement_coeffs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Given `habove` (all above-bottom coeffs vanish), every coeff vanishes by casing on `idx`.
--   * `chain_bottom_coeffs` : chain-bottom coeffs `g ⟨inl t, 0⟩` vanish (residual ∈ range N,
--     hC2-disjoint from C, then `chain_bottoms_li`). Strictly simpler: only the `j = 0` chain part.
--   * `complement_coeffs` : complement coeffs `g ⟨inr c, 0⟩` vanish (residual ∈ C, hC2-disjoint
--     from range N, then `cb`-LI). Strictly simpler: only the complement part.
-- Combinator is pure structural casing: above-bottom → `habove`, chain bottom → h_bottom,
-- complement (Fin 1, forced 0) → h_comp.
theorem s10998
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
    ∀ idx, g idx = 0  := by
  have h_bottom := chain_bottom_coeffs N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove
  have h_comp := complement_coeffs N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove
  rintro ⟨s, j⟩
  cases s with
  | inl t =>
    rcases Nat.eq_zero_or_pos (j : ℕ) with hj | hj
    · have hj0 : j = (0 : Fin (l t.1 + 1)) := Fin.ext hj
      subst hj0; exact h_bottom t
    · exact habove t j hj
  | inr c =>
    have hj0 : j = (0 : Fin 1) := Fin.fin_one_eq_zero j
    subst hj0; exact h_comp c

end Problems.LinearAlgebra.jordan_normal_form
