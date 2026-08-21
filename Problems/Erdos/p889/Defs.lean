import Mathlib

set_option maxHeartbeats 400000

open Finset Nat Filter Topology

namespace Problems.Erdos.p889

def v (n k : ℕ) : ℕ :=
  ((n + k).primeFactors.filter (fun p =>
    ∀ i ∈ range k, ¬ p ∣ n + i)).card

noncomputable def v₀ (n : ℕ) : ℕ∞ :=
  ⨆ k, (v n k : ℕ∞)

end Problems.Erdos.p889
