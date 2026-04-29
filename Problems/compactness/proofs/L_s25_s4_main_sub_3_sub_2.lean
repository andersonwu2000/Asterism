import Problems.compactness.Defs

namespace Problems.compactness

theorem s25_s4_main_sub_3_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hNeg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M)
    (p q : PropForm α) :
    PropForm.conj p q ∈ M → q ∈ M := by trivial

end Problems.compactness
