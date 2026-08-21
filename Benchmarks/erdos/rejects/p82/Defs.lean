import Mathlib

set_option maxHeartbeats 400000

open SimpleGraph Filter

namespace Problems.Erdos.p82

def IsRegularInduced {G : SimpleGraph V} (S : Subgraph G) : Prop :=
  open scoped Classical in
  S.IsInduced ∧ ∃ k, (S.coe).IsRegularOfDegree k

noncomputable def F (n : ℕ) : ℕ :=
  sSup {k | ∀ (G : SimpleGraph (Fin n)), ∃ S : Subgraph G,
    IsRegularInduced S ∧ k ≤ S.verts.ncard}

end Problems.Erdos.p82
