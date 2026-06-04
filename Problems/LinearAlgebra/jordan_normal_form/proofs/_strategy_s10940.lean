import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_family_chain
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_family_li_span

namespace Problems.LinearAlgebra.jordan_normal_form

-- Build the fintype-indexed Jordan family of `W` explicitly, then split the proof in two.
-- Index `ι := {t : Fin p // 0 < l t} ⊕ Fin (finrank K C)`: each nonempty range-N chain
-- `t` is extended (via `Fin.snoc`) by its top preimage `x ⟨t, l t - 1⟩` into a length-`l t + 1`
-- chain `↑(d ⟨t,0⟩), …, ↑(d ⟨t, l t -1⟩), x⟨t, l t -1⟩`; each complement basis vector `cb c`
-- is a length-1 chain. `hv_chain`/`hv_top`/`hv_C` characterise `v` on the three index shapes
-- (proved here by `Fin.snoc_castSucc`/`Fin.snoc_last`/`rfl`). The two sub-goals consume only
-- those characterisations: `family_li_span` (LinearIndependent ∧ spanning — the dimension-count
-- argument, Backward) and `family_chain` (the within-block Jordan relation, mechanical case work).
theorem s10940
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
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N) :
    ∃ (ι : Type) (_ : Fintype ι) (k : ι → ℕ) (v : (Σ s : ι, Fin (k s)) → W),
      LinearIndependent K v ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v) ∧
      ∀ (s : ι) (j : Fin (k s)),
        N (v ⟨s, j⟩) = 0 ∨
        ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩  := by
  classical
  let m := Module.finrank K C
  let cb : Module.Basis (Fin m) K C := Module.finBasis K C
  let P := {t : Fin p // 0 < l t}
  let kk : (P ⊕ Fin m) → ℕ := Sum.elim (fun t : P => l t.1 + 1) (fun _ : Fin m => 1)
  let v : (Σ s : (P ⊕ Fin m), Fin (kk s)) → W := fun sj =>
    match sj with
    | ⟨Sum.inl t, j⟩ =>
        Fin.snoc (α := fun _ => W) (fun i => (↑(d ⟨t.1, i⟩) : W))
          (x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩) j
    | ⟨Sum.inr c, _⟩ => (cb c : W)
  have hv_chain : ∀ (t : P) (i : Fin (l t.1)),
      v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W) :=
    fun t i => Fin.snoc_castSucc _ _ i
  have hv_top : ∀ (t : P),
      v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩ :=
    fun t => Fin.snoc_last _ _
  have hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W) := fun _ => rfl
  obtain ⟨hLI, hspan⟩ :=
    family_li_span N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  have hchain :=
    family_chain N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  exact ⟨P ⊕ Fin m, inferInstance, kk, v, hLI, hspan, hchain⟩


end Problems.LinearAlgebra.jordan_normal_form
