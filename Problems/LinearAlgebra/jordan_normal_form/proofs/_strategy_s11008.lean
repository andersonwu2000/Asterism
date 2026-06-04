import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct leaf (no sub-goals): the chain bottoms `↑(d ⟨t.1, ⟨0, t.2⟩⟩)` are an injective
-- subfamily of the Jordan basis `d`, so they are LI in `range N` (d.linearIndependent.comp
-- on the injection `t ↦ ⟨t.1, ⟨0, t.2⟩⟩`), then LI in W after lifting through the range
-- subtype (.map' with trivial kernel). `Fintype.linearIndependent_iff` reads `hzero` off to
-- force every bottom coeff `g ⟨Sum.inl t, 0⟩ = 0`. Sorry-free; ships alone for leaf-bypass.
theorem s11008
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
    (hzero : (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) = 0) :
    ∀ (t : {t : Fin p // 0 < l t}), g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0  := by
  have h_li : LinearIndependent K
      (fun t : {t : Fin p // 0 < l t} => (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) := by
    have hsub : LinearIndependent K
        (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩) := by
      apply d.linearIndependent.comp
          (fun t : {t : Fin p // 0 < l t} => (⟨t.1, ⟨0, t.2⟩⟩ : Σ t : Fin p, Fin (l t)))
      intro a b hab
      simp only [Sigma.mk.inj_iff] at hab
      exact Subtype.ext hab.1
    exact hsub.map' (LinearMap.range N).subtype (Submodule.ker_subtype _)
  exact Fintype.linearIndependent_iff.mp h_li
    (fun t => g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) hzero

end Problems.LinearAlgebra.jordan_normal_form
