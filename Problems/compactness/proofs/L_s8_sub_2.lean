import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Chain fin-sat: given per-member finite-satisfiability and a chain-cover
witness, any finite T ⊆ ⋃₀ C is satisfiable. -/
theorem s8_sub_2 {α : Type}
    (C : Set (Set (PropForm α)))
    (hfinsat : ∀ N ∈ C, ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T)
    (hcover : ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → ∃ N ∈ C, T ⊆ N)
    (T : Set (PropForm α)) (hT : T ⊆ ⋃₀ C) (hfin : T.Finite) :
    Sat T := by
  obtain ⟨N, hN, hTN⟩ := hcover T hT hfin
  exact hfinsat N hN T hTN hfin

end Problems.compactness
