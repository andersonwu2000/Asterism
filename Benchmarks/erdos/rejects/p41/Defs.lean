import Mathlib

set_option maxHeartbeats 400000

open Filter Set

namespace Problems.Erdos.p41

def NtupleCondition (A : Set α) (n : ℕ) : Prop := ∀ (I : Finset α) (J : Finset α),
  ↑I ⊆ A ∧ ↑J ⊆ A ∧ I.card = n ∧ J.card = n ∧
  (∑ i ∈ I, i = ∑ j ∈ J, j) → I = J

end Problems.Erdos.p41
