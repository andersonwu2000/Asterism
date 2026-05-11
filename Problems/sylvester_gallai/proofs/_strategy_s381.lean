import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- Direct finite-extremal proof: minimise f over `(Q×ˢQ×ˢQ).filter (¬ Collinear ·)`
-- via `Finset.exists_min_image`. Nonempty witness is (x,y,z). `classical` is
-- needed since the custom `Collinear` predicate lacks `DecidablePred`.
theorem s381 :
    ∀ (Q : Finset (ℝ × ℝ)),
      (∀ p ∈ Q, ∀ q ∈ Q, p ≠ q → ∃ r ∈ Q, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ x ∈ Q, ∀ y ∈ Q, ∀ z ∈ Q, ¬ Collinear x y z →
      ∃ a ∈ Q, ∃ b ∈ Q, ∃ c ∈ Q, ¬ Collinear a b c ∧
        (∀ a' ∈ Q, ∀ b' ∈ Q, ∀ c' ∈ Q, ¬ Collinear a' b' c' →
          ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 /
              ((b.1 - a.1)^2 + (b.2 - a.2)^2) ≤
          ((c'.1 - a'.1) * (b'.2 - a'.2) - (c'.2 - a'.2) * (b'.1 - a'.1))^2 /
              ((b'.1 - a'.1)^2 + (b'.2 - a'.2)^2))  := by
  classical
  intro Q _hQ x hx y hy z hz hxyz
  set f : (ℝ×ℝ) × (ℝ×ℝ) × (ℝ×ℝ) → ℝ := fun t =>
    ((t.2.2.1 - t.1.1) * (t.2.1.2 - t.1.2) - (t.2.2.2 - t.1.2) * (t.2.1.1 - t.1.1))^2 /
      ((t.2.1.1 - t.1.1)^2 + (t.2.1.2 - t.1.2)^2) with hf
  set S : Finset ((ℝ×ℝ) × (ℝ×ℝ) × (ℝ×ℝ)) :=
    (Q ×ˢ Q ×ˢ Q).filter (fun t => ¬ Collinear t.1 t.2.1 t.2.2) with hS_def
  have hS : S.Nonempty := by
    refine ⟨(x, y, z), ?_⟩
    simp [S, hx, hy, hz, hxyz]
  obtain ⟨⟨a, b, c⟩, habc, hmin⟩ := S.exists_min_image f hS
  rw [Finset.mem_filter, Finset.mem_product, Finset.mem_product] at habc
  refine ⟨a, habc.1.1, b, habc.1.2.1, c, habc.1.2.2, habc.2, ?_⟩
  intro a' ha' b' hb' c' hc' hnc
  have hmem : (a', b', c') ∈ S := by
    rw [Finset.mem_filter, Finset.mem_product, Finset.mem_product]
    exact ⟨⟨ha', hb', hc'⟩, hnc⟩
  have := hmin (a', b', c') hmem
  simpa [f] using this

end Problems.sylvester_gallai
