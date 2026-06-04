import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs

namespace Problems.Minif2f.imo_1987_p4

-- nonfixed_split_lt_gt: trichotomy splits non-fixed set into {a < g a} ∪ {g a < a} (disjoint)
theorem nonfixed_split_lt_gt :
    ∀ (g : ℕ → ℕ), (∀ a, a < 1987 → g a < 1987) →
      (∀ a, a < 1987 → g (g a) = a) →
      (Finset.filter (fun a => g a ≠ a) (Finset.range 1987)).card
        = (Finset.filter (fun a => a < g a) (Finset.range 1987)).card
          + (Finset.filter (fun a => g a < a) (Finset.range 1987)).card := by
  intro g _hg _hgg
  have h_disj : Disjoint
      (Finset.filter (fun a => a < g a) (Finset.range 1987))
      (Finset.filter (fun a => g a < a) (Finset.range 1987)) := by
    simp only [Finset.disjoint_filter]
    intro a _ h1 h2; omega
  have h_union : Finset.filter (fun a => g a ≠ a) (Finset.range 1987) =
      Finset.filter (fun a => a < g a) (Finset.range 1987) ∪
      Finset.filter (fun a => g a < a) (Finset.range 1987) := by
    ext a
    simp [Finset.mem_filter, Finset.mem_union, Finset.mem_range]
    omega
  rw [h_union, Finset.card_union_of_disjoint h_disj]

end Problems.Minif2f.imo_1987_p4
