import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s8_sub_1
import Problems.compactness.proofs.L_s8_sub_2
import Problems.compactness.proofs.L_s8_sub_3
import Problems.compactness.proofs.L_s8_sub_4

namespace Problems.compactness

theorem s8 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ φ : PropForm α, φ ∉ M →
        ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T) := by
  -- Build chain bounds for F = {N | S ⊆ N ∧ fin-sat N} using s8_sub_1 and s8_sub_2
  have hbound : ∀ C : Set (Set (PropForm α)), C.Nonempty → IsChain (· ⊆ ·) C →
      (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
      ∃ UB : Set (PropForm α),
        (∀ N ∈ C, N ⊆ UB) ∧
        S ⊆ UB ∧
        ∀ T : Set (PropForm α), T ⊆ UB → T.Finite → Sat T := by
    intro C ⟨N₀, hN₀⟩ hchain hmem
    refine ⟨⋃₀ C, fun N hN => Set.subset_sUnion_of_mem hN,
            (hmem N₀ hN₀).1.trans (Set.subset_sUnion_of_mem hN₀), ?_⟩
    intro T hT hfin
    exact s8_sub_2 C
      (fun N hN T' hT' hfin' => (hmem N hN).2 T' hT' hfin')
      (s8_sub_1 C hchain)
      T hT hfin
  -- Apply Zorn to get ⊆-maximal M in F
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := s8_sub_3 S hS hbound
  -- Convert ⊆-maximality to the s1-style maximality condition
  exact ⟨M, hSM, hMfinsat, s8_sub_4 S M hSM hMfinsat hMmax⟩

end Problems.compactness
