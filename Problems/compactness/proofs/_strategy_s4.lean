import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s4_main_sub_1
import Problems.compactness.proofs.L_s4_main_sub_2
import Problems.compactness.proofs.L_s4_main_sub_3
import Problems.compactness.proofs.L_s4_main_sub_4

namespace Problems.compactness

theorem s4_main : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hFinSat
  obtain ⟨M, hSM, hFinSatM, hMaxM⟩ := s4_main_sub_1 S hFinSat
  have hNeg := s4_main_sub_2 M hFinSatM hMaxM
  have hConj := s4_main_sub_3 M hFinSatM hNeg
  exact s4_main_sub_4 S M hSM hNeg hConj

end Problems.compactness
