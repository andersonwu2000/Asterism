import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s15_s3_main_sub_1_sub_1
import Problems.compactness.proofs.L_s15_s3_main_sub_1_sub_2
import Problems.compactness.proofs.L_s15_s3_main_sub_1_sub_3

namespace Problems.compactness

theorem s15_s3_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  intro α S hfinsat
  exact s15_s3_main_sub_1_sub_3 S hfinsat (fun c hc hc_chain hc_nonempty =>
    s15_s3_main_sub_1_sub_2 S hfinsat c hc hc_chain hc_nonempty
      (s15_s3_main_sub_1_sub_1 S hfinsat c hc_chain hc_nonempty))

end Problems.compactness
