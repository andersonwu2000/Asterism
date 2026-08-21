import Mathlib

set_option maxHeartbeats 400000

open Set Metric Filter Real
open scoped EuclideanGeometry

namespace Problems.Erdos.p100

def DistancesSeparated (A : Finset ℝ²) : Prop :=
  ∀ p₁ q₁ p₂ q₂, p₁ ∈ A → q₁ ∈ A → p₂ ∈ A → q₂ ∈ A →
    dist p₁ q₁ ≠ dist p₂ q₂ →
    |dist p₁ q₁ - dist p₂ q₂| ≥ 1

end Problems.Erdos.p100
