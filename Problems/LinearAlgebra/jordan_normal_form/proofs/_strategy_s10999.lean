import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_li_extract_above
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_pushforward_d_relation

namespace Problems.LinearAlgebra.jordan_normal_form

-- Above-bottom coeffs vanish: push `N` through the relation `hg : ∑ gᵢ • vᵢ = 0`.
-- `pushforward_d_relation` collapses `N (∑ gᵢ • vᵢ) = 0` to a combination of the range-basis
--   `d`: complement vectors and chain bottoms (j = 0) die under `N`, while each interior/top
--   shifts down to `d⟨t, j-1⟩`, leaving `∑_{t,i} g⟨inl t, i.succ⟩ • d⟨t,i⟩ = 0`.
-- `li_extract_above` then runs `d`'s linear independence on that relation to force every
--   above-bottom coefficient `g⟨inl t, j⟩` (j ≥ 1) to 0. Each phase drops the other's work
--   (phase 1 needs no LI; phase 2 needs no `N`-pushforward), so both are strictly simpler.
theorem s10999
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
    (hg : ∑ i, g i • v i = 0) :
    ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0  := by
  have h_rel := pushforward_d_relation N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg
  exact li_extract_above N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg h_rel

end Problems.LinearAlgebra.jordan_normal_form
