import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Zorn's lemma applied to the collection of finitely-satisfiable supersets of S.
-- Given the chain bound, produces a maximal finitely-satisfiable superset M with the
-- exact maximality form: any fin-sat superset of M equals M.
theorem s18_s4_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ X ∈ c, S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M' := by
  intro S hS hchain
  let 𝒞 : Set (Set (PropForm _)) :=
    {N | S ⊆ N ∧ ∀ T : Set (PropForm _), T ⊆ N → T.Finite → Sat T}
  obtain ⟨M, hSM, hM_max⟩ := zorn_subset_nonempty 𝒞
    (fun c hcC hcChain ⟨X, hX⟩ =>
      ⟨⋃₀ c, hchain c ⟨X, hX⟩ hcChain (fun Y hY => hcC hY),
       fun s hs => Set.subset_sUnion_of_mem hs⟩)
    S ⟨Subset.refl S, hS⟩
  exact ⟨M, hSM, hM_max.prop.2,
    fun M' hMM' hM'sat => hM_max.eq_of_subset ⟨hSM.trans hMM', hM'sat⟩ hMM'⟩

end Problems.compactness
