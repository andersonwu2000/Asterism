import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_family_chain_2
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_family_li_span_2

namespace Problems.LinearAlgebra.jordan_normal_form

-- Build the chain family `v` explicitly (mirrors the proved `extended_jordan_family` route):
-- index `P ⊕ Fin m` with `P := {t // 0 < l t}`, `m := finrank K C`, `cb := finBasis K C`;
-- each nonempty range-N chain `t` is extended via `Fin.snoc` by its top preimage
-- `x ⟨t, l t - 1⟩`, each complement vector `cb c` is a length-1 chain. The defining equations
-- `hv_chain`/`hv_top`/`hv_C` hold by `Fin.snoc_castSucc`/`Fin.snoc_last`/`rfl`. Two sub-goals
-- consume only those equations (weak `hd` = strong `hd` minus the `j = 0` clause):
--   * `family_li_span_2` — `LinearIndependent K v ∧ ⊤ ≤ span K (range v)` (dimension count).
--   * `family_chain_2` — the within-block Jordan chain relation.
-- The final `Fin r` index is a pure `Fintype.equivFin` relabel of the `P ⊕ Fin m` index.
theorem s10976
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
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N) :
    ∃ (r : ℕ) (k : Fin r → ℕ) (v : (Σ s : Fin r, Fin (k s)) → W),
      LinearIndependent K v ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v) ∧
      ∀ (s : Fin r) (j : Fin (k s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩ := by
  classical
  have hd' : ∀ (t : Fin p) (j : Fin (l t)),
      (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
        ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
          (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩ :=
    fun t j => (hd t j).imp (fun h => h.2) id
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
    family_li_span_2 N hN h_inv p l d hd' x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  have hchain :=
    family_chain_2 N hN h_inv p l d hd' x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  set e := Fintype.equivFin (P ⊕ Fin m) with he
  set φ := Equiv.sigmaCongrLeft' (β := fun a : (P ⊕ Fin m) => Fin (kk a)) e with hφ
  refine ⟨Fintype.card (P ⊕ Fin m), fun s => kk (e.symm s), fun q => v (φ.symm q), ?_, ?_, ?_⟩
  · exact hLI.comp _ φ.symm.injective
  · have hr : Set.range (fun q => v (φ.symm q)) = Set.range v := by
      rw [show (fun q => v (φ.symm q)) = v ∘ φ.symm from rfl, Set.range_comp,
        Equiv.range_eq_univ, Set.image_univ]
    rw [hr]; exact hspan
  · intro s j
    exact hchain (e.symm s) j

end Problems.LinearAlgebra.jordan_normal_form
