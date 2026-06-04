import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_bottoms_mem_range_2
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_comp_block_eq_neg_chain_bottoms_2

namespace Problems.LinearAlgebra.jordan_normal_form

-- The complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`, via two sub-goals.
--   * `comp_block_eq_neg_chain_bottoms_2` : pure sum bookkeeping using `hg`, `habove`,
--     `hv_chain`, `hv_C` to rewrite the block as `-(∑ t, g⟨inl t,0⟩ • d⟨t.1,0⟩)`.
--     Strictly simpler: no `range N` reasoning, no linear independence.
--   * `chain_bottoms_mem_range_2` : the chain-bottom sum lies in `range N` since each
--     `↑(d ·) ∈ range N` and `range N` is closed under scalar mul + finite sum.
--     Strictly simpler: pure submodule closure facts, no full sum identity.
-- Combinator: rewrite via the equality, then `neg_mem` on the membership.
theorem s11034
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
    (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ LinearMap.range N  := by
  have h_eq : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W))
      = -(∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) :=
    comp_block_eq_neg_chain_bottoms_2
      N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove
  have h_mem : (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
      ∈ LinearMap.range N :=
    chain_bottoms_mem_range_2
      N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove
  rw [h_eq]
  exact neg_mem h_mem

end Problems.LinearAlgebra.jordan_normal_form
