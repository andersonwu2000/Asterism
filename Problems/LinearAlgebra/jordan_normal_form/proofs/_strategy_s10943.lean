import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_lower_coeffs_zero
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_upper_coeffs_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- LI of the assembled Jordan family `v`, via `Fintype.linearIndependent_iff`: fix a
-- vanishing combination `∑ g s • v s = 0` and show every coefficient is 0, split into
-- two strictly-simpler steps over the coefficient function `g`.
--   • `upper_coeffs_zero`: applying `N` collapses the relation to a combination of the
--     range-basis `d` (tops map to chain heads, bottoms/complement to 0); `d`'s LI forces
--     every non-bottom coefficient (`inl`-block index `≥ 1`) to vanish.
--   • `lower_coeffs_zero`: with the upper coefficients gone, what remains lives in
--     `(range N ⊓ ker N) ⊕ C`; `hC2`-disjointness + LI of `d`/`cb` kill the bottom-chain
--     and complement coefficients.
-- Combine: case-split each index into bottom (j = 0) / interior (j ≥ 1) / complement.
theorem s10943
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    LinearIndependent K v  := by
  classical
  rw [Fintype.linearIndependent_iff]
  intro g hg
  have hup := upper_coeffs_zero N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg
  have hlow := lower_coeffs_zero N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg hup
  rintro ⟨s, j⟩
  cases s with
  | inl t =>
    rcases Nat.eq_zero_or_pos (j : ℕ) with h0 | hpos
    · have hj : j = (0 : Fin (l ↑t + 1)) := Fin.ext (by simpa using h0)
      rw [hj]; exact hlow.1 t
    · exact hup t j hpos
  | inr c =>
    have hj : j = (0 : Fin 1) := Fin.fin_one_eq_zero j
    rw [hj]; exact hlow.2 c

end Problems.LinearAlgebra.jordan_normal_form
