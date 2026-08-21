import Mathlib

set_option maxHeartbeats 400000

open Filter
open scoped Topology Real

namespace Problems.Erdos.p1

abbrev IsSumDistinctSet (A : Finset ℕ) (N : ℕ) : Prop :=
    A ⊆ Finset.Icc 1 N ∧ (fun (⟨S, _⟩ : A.powerset) => S.sum id).Injective

end Problems.Erdos.p1
