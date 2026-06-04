import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct leaf proof: complement coeffs vanish from `hmem` + disjointness + cb's LI.
-- The block `∑ c, g⟨inr c,0⟩ • cb c` lies in C (each cb c ∈ C); `hmem` puts it in `range N`;
-- `hC2`-disjointness collapses C ⊓ range N to ⊥, so the block = 0; then `cb.linearIndependent`
-- (pushed along the injective subtype) + `Fintype.linearIndependent_iff` kills every coeff.
theorem s11033
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
      g ⟨Sum.inl t, j⟩ = 0)
    (hmem : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ LinearMap.range N) :
    ∀ (c : Fin m), g ⟨Sum.inr c, (0 : Fin 1)⟩ = 0  := by
  have hmemC : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ C :=
    Submodule.sum_mem C (fun c _ => Submodule.smul_mem C _ (cb c).2)
  have hmem2 : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ C ⊓ LinearMap.range N :=
    Submodule.mem_inf.mpr ⟨hmemC, hmem⟩
  have hbot : C ⊓ LinearMap.range N = ⊥ :=
    le_antisymm (disjoint_iff_inf_le.mp hC2) bot_le
  rw [hbot] at hmem2
  have hblock : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) = 0 :=
    (Submodule.mem_bot K).mp hmem2
  have hli : LinearIndependent K (fun c : Fin m => (cb c : W)) :=
    (cb.linearIndependent).map' (C.subtype) (LinearMap.ker_eq_bot.mpr Subtype.val_injective)
  intro c
  exact (Fintype.linearIndependent_iff.mp hli
    (fun c => g ⟨Sum.inr c, (0 : Fin 1)⟩) hblock) c
end Problems.LinearAlgebra.jordan_normal_form
