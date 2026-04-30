import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s9_s2_main_sub_1_sub_1
import Problems.compactness.proofs.L_s9_s2_main_sub_1_sub_2
import Problems.compactness.proofs.L_s9_s2_main_sub_1_sub_3

namespace Problems.compactness

theorem s9_s2_main_sub_1 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M
      ∧ (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
      ∧ (∀ p : PropForm α, p ∉ M →
           ∃ T : Set (PropForm α), T ⊆ insert p M ∧ T.Finite ∧ ¬Sat T) := by
  let FS : Set (Set (PropForm α)) :=
    {N | S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T}
  have chain_bound : ∀ C ⊆ FS, IsChain (· ⊆ ·) C → C.Nonempty →
      ∃ ub ∈ FS, ∀ z ∈ C, z ⊆ ub := by
    intro C hCFS hCchain hCne
    refine ⟨⋃₀ C, ?_, fun z hz => Set.subset_sUnion_of_mem hz⟩
    exact s9_s2_main_sub_1_sub_2 S hS C hCchain hCne (fun N hNC => hCFS hNC)
  obtain ⟨M, hMFS, hSM, hMmax⟩ :=
    zorn_subset_nonempty FS chain_bound S ⟨le_refl _, hS⟩
  exact ⟨M, hSM, hMFS.2,
    s9_s2_main_sub_1_sub_3 S hS M hSM hMFS.2
      (fun N hSN hNfinsat hMN => hMmax ⟨hSN, hNfinsat⟩ hMN)⟩

end Problems.compactness
