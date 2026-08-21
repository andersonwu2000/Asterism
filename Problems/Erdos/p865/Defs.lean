import Mathlib

set_option maxHeartbeats 400000

open Finset Filter
open scoped Asymptotics

namespace Problems.Erdos.p865

noncomputable def f (N k : ℕ) : ℕ :=
  sInf {m | ∀ A ⊆ Icc 1 N, A.card ≥ m →
    ∃ S ⊆ A, S.card = k ∧ ∀ x ∈ S, ∀ y ∈ S, x ≠ y → x + y ∈ A}

end Problems.Erdos.p865
