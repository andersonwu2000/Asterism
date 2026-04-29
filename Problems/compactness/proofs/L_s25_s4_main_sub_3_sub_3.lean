import Problems.compactness.Defs

namespace Problems.compactness

theorem s25_s4_main_sub_3_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hNeg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M)
    (p q : PropForm α) :
    p ∈ M → q ∈ M → PropForm.conj p q ∈ M := by sorry

end Problems.compactness
