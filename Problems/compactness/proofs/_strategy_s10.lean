import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s10_sub_1
import Problems.compactness.proofs.L_s10_sub_2
import Problems.compactness.proofs.L_s10_sub_3

namespace Problems.compactness

open Classical

theorem s10 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ φ : PropForm α, φ ∉ M →
        ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T) := by
  have hChainBound : ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C →
      (∀ N ∈ C, ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T :=
    fun C hchain hfinsat T hT hfin => s10_sub_1 C hchain hfinsat T hT hfin
  obtain ⟨M, hSM, hFinSat, hMax⟩ := s10_sub_2 S hS hChainBound
  exact ⟨M, hSM, hFinSat, fun φ hφ => s10_sub_3 S M hSM hFinSat hMax φ hφ⟩

end Problems.compactness
