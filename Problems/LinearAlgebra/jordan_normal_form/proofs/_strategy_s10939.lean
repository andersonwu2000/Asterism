import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Pure index relabel: transport the `Fintype ι`-indexed sigma Jordan family to `Fin (card ι)`.
-- Take `e := Fintype.equivFin ι` and `φ := e.sigmaCongrLeft'`, set `r := card ι`,
-- `k' s := k (e.symm s)`, `v' := v ∘ φ.symm`. LI follows from `hLI.comp φ.symm.injective`;
-- span from `Set.range (v ∘ φ.symm) = Set.range v` (φ.symm surjective); the within-block
-- chain transports verbatim since `φ.symm ⟨s, m⟩ = ⟨e.symm s, m⟩` holds by `rfl` (inner
-- `Fin (k s)` index untouched), so each block's chain is exactly `hchain (e.symm s)`.
theorem s10939
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (ι : Type*) [Fintype ι] (k : ι → ℕ)
    (v : (Σ s : ι, Fin (k s)) → W)
    (hLI : LinearIndependent K v)
    (hsp : (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v))
    (hchain : ∀ (s : ι) (j : Fin (k s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩) :
    ∃ (r : ℕ) (k' : Fin r → ℕ) (v' : (Σ s : Fin r, Fin (k' s)) → W),
      LinearIndependent K v' ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v') ∧
      ∀ (s : Fin r) (j : Fin (k' s)),
        N (v' ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k' s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v' ⟨s, j⟩) = v' ⟨s, i⟩  := by
  classical
  set e := Fintype.equivFin ι with he
  set φ := Equiv.sigmaCongrLeft' (β := fun a : ι => Fin (k a)) e with hφ
  refine ⟨Fintype.card ι, fun s => k (e.symm s), fun p => v (φ.symm p), ?_, ?_, ?_⟩
  · exact hLI.comp _ φ.symm.injective
  · have hr : Set.range (fun p => v (φ.symm p)) = Set.range v := by
      rw [show (fun p => v (φ.symm p)) = v ∘ φ.symm from rfl, Set.range_comp,
        Equiv.range_eq_univ, Set.image_univ]
    rw [hr]; exact hsp
  · intro s j
    exact hchain (e.symm s) j

end Problems.LinearAlgebra.jordan_normal_form
