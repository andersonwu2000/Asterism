import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_above_bottom_vanish
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_bottom_complement_coeffs

namespace Problems.LinearAlgebra.jordan_normal_form

-- LinearIndependent v via `Fintype.linearIndependent_iff`: split a vanishing combination
-- `∑ g i • v i = 0` into two phases (combinator is trivial; both phases subsume all parent hyps).
--   * `above_bottom_vanish` : applying N to the relation sends chain tops/interiors to the
--     range-basis `d` (bottoms/complement to 0), so `d`-LI forces every above-bottom coeff
--     `g ⟨inl t, j⟩` (j ≥ 1) to vanish. Strictly simpler: only a partial coeff result.
--   * `bottom_complement_coeffs` : given the above-bottom coeffs are 0, the residual relation
--     lives among chain bottoms `d⟨t,0⟩ ∈ range N ⊓ ker N` and complement `cb c ∈ C`; `hC2`
--     disjointness + `chain_bottoms_li` + `cb`-LI kill the rest. Strictly simpler: extra `habove`.
theorem s10994

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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    LinearIndependent K v  := by
  classical
  rw [Fintype.linearIndependent_iff]
  intro g hg
  have habove := above_bottom_vanish N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg
  exact bottom_complement_coeffs N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove



end Problems.LinearAlgebra.jordan_normal_form
