import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_comp_coeffs_of_mem_range
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_comp_combo_mem_range

namespace Problems.LinearAlgebra.jordan_normal_form

-- Complement coeffs `g ⟨inr c, 0⟩` vanish, given `habove` (above-bottom chain coeffs are 0).
-- Two simpler phases; the combinator just threads phase 1 into phase 2.
--   * `comp_combo_mem_range` : the complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`.
--     From `hg`, `habove` kills the above-bottom terms, leaving chain bottoms
--     (`v⟨inl t,0⟩ = d⟨t.1,0⟩ ∈ range N`) plus this block, so the block = minus that sum.
--     Strictly simpler: pure sum bookkeeping, no linear independence.
--   * `comp_coeffs_of_mem_range` : given that membership, the block is also in `C`
--     (each `cb c ∈ C`), so `hC2`-disjointness makes it 0 and `cb`-LI kills every coeff.
--     Strictly simpler: takes the membership as a hypothesis; only disjointness + LI remain.
theorem s11001
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
    ∀ (c : Fin m), g ⟨Sum.inr c, (0 : Fin 1)⟩ = 0  := by
  have hmem := comp_combo_mem_range N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove
  exact comp_coeffs_of_mem_range N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove hmem

end Problems.LinearAlgebra.jordan_normal_form
