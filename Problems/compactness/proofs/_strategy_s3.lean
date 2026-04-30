import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s3_main_sub_1
import Problems.compactness.proofs.L_s3_main_sub_2
import Problems.compactness.proofs.L_s3_main_sub_3

namespace Problems.compactness

theorem s3_main : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hfinsat
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := s3_main_sub_1 S hfinsat
  have hcomplete := s3_main_sub_2 M hMfinsat hMmax
  obtain ⟨v, hv⟩ := s3_main_sub_3 M hMfinsat hcomplete
  exact ⟨v, fun p hp => (hv p).mp (hSM hp)⟩

end Problems.compactness
