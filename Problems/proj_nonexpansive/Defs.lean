import Mathlib

/-!
Shared definitions for the proj_nonexpansive problem (HW C 泛函 4).
A function `P : X → X` is a metric projector onto `K ⊆ X` if for
each `x` it returns the closest point of `K` to `x`. We don't assume
existence (only that some such `P` is given as a hypothesis).
-/

namespace Problems.proj_nonexpansive

def IsMetricProjector {X : Type*} [NormedAddCommGroup X]
    (K : Set X) (P : X → X) : Prop :=
  ∀ x, P x ∈ K ∧ ∀ y ∈ K, ‖x - P x‖ ≤ ‖x - y‖

end Problems.proj_nonexpansive
