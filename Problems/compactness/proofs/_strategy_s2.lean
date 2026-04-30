import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s2_main_sub_1
import Problems.compactness.proofs.L_s2_main_sub_2
import Problems.compactness.proofs.L_s2_main_sub_3

namespace Problems.compactness

theorem s2_main {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) : Sat S := by
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := s2_main_sub_1 S hS
  exact s2_main_sub_3 S M hSM (s2_main_sub_2 M hMfinsat hMmax)

end Problems.compactness
