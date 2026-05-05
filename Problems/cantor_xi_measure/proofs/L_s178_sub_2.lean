import Mathlib

namespace Problems.cantor_xi_measure

theorem s178_sub_2 : ∀ (p q : ℕ → ENNReal) (a : ENNReal),
    (∀ n, a ≤ p n) → (∀ n, p n = q n) →
    (∀ (x y z : ENNReal), x ≤ y → y = z → x ≤ z) →
    ∀ n, a ≤ q n := by grind

end Problems.cantor_xi_measure
