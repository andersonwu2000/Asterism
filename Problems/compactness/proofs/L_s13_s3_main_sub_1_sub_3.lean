import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Zorn's lemma applied to the collection of finitely-satisfiable supersets of S.
-- Given a chain-bound property, produces a maximal finitely-satisfiable superset M.
theorem s13_s3_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ X ∈ c, S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α S hfinsat hchain
  let coll : Set (Set (PropForm α)) := {X | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T}
  have hS_in : S ∈ coll := ⟨subset_refl S, hfinsat⟩
  have hchain_bound : ∀ c ⊆ coll, IsChain (· ⊆ ·) c → c.Nonempty → ∃ ub ∈ coll, ∀ s ∈ c, s ⊆ ub := by
    intro c hc_sub hc_chain hc_ne
    obtain ⟨hSU, hUfinsat⟩ := hchain c hc_ne hc_chain (fun X hX => hc_sub hX)
    exact ⟨⋃₀ c, ⟨hSU, hUfinsat⟩, fun s hs => Set.subset_sUnion_of_mem hs⟩
  obtain ⟨M, hSM, hmax⟩ := zorn_subset_nonempty coll hchain_bound S hS_in
  exact ⟨M, hSM, hmax.1.2, fun p hp hext =>
    hp (hmax.mem_of_prop_insert ⟨hSM.trans (Set.subset_insert p M), hext⟩)⟩

end Problems.compactness
