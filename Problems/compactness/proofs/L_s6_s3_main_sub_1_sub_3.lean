import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s6_s3_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C → C.Nonempty →
        (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), S ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M ⊆ N → N = M := by
  intro α S hfinsat hchain
  let CS : Set (Set (PropForm α)) :=
    {N | S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T}
  obtain ⟨M, hSM, hMmax⟩ := zorn_subset_nonempty CS
    (fun c hcCS hcchain hcne => by
      obtain ⟨hSunion, hunionfinsat⟩ :=
        hchain c hcchain hcne (fun N hN => hcCS hN)
      exact ⟨⋃₀ c, ⟨hSunion, hunionfinsat⟩,
             fun z hz => Set.subset_sUnion_of_mem hz⟩)
    S ⟨fun x hx => hx, hfinsat⟩
  exact ⟨M, hSM, hMmax.1.2,
         fun N hSN hNfinsat hMN =>
           le_antisymm (hMmax.2 ⟨hSN, hNfinsat⟩ hMN) hMN⟩

end Problems.compactness
