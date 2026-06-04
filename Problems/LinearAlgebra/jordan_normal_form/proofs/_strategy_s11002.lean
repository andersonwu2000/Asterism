import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_bottom_coeffs_of_sum_zero
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_bottom_range_part_zero
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_bottom_residual

namespace Problems.LinearAlgebra.jordan_normal_form

-- Bottom-coeff vanishing for the chain part of the assembled Jordan family.
-- After `habove` kills every above-bottom coeff, the dependence `hg` collapses to a pure
-- bottom relation `(∑_t g⟨inl t,0⟩ • d⟨t.1,0⟩) + (∑_c g⟨inr c,0⟩ • cb c) = 0` (`chain_bottom_residual`).
-- The first sum lies in `range N`, the second in `C`; `hC2`-disjointness forces the
-- `range N` part to vanish (`chain_bottom_range_part_zero`). Linear independence of the chain
-- bottoms (`chain_bottoms_li`, lifted along `range N ↪ W`) then forces each chain-bottom coeff
-- to 0 (`chain_bottom_coeffs_of_sum_zero`). Combinator threads h_res → h_zero → conclusion.
-- Each sub-goal is strictly simpler: #1 is the sum reduction alone, #2 assumes that relation and
-- only runs disjointness, #3 assumes the range part is 0 and only runs the LI argument.
theorem s11002
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
    ∀ (t : {t : Fin p // 0 < l t}), g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0  := by
  have h_res :
      (∑ t : {t : Fin p // 0 < l t},
          g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
        + (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W)) = 0 :=
    chain_bottom_residual N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove
  have h_zero :
      (∑ t : {t : Fin p // 0 < l t},
          g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) = 0 :=
    chain_bottom_range_part_zero N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove h_res
  exact chain_bottom_coeffs_of_sum_zero N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove h_zero

end Problems.LinearAlgebra.jordan_normal_form
