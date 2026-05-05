import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s84_sub_1
import Problems.sylvester_gallai.proofs.L_s84_sub_2

namespace Problems.sylvester_gallai

open Classical in
theorem s84 (P : Finset (ℝ × ℝ))
    (h_noncol : ∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c)
    (h_skolem : ∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q)
    (h_witness : ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r)
    (h_nonempty : ((P ×ˢ P ×ˢ P).filter
        (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
          t.1 ≠ t.2.1 ∧ ¬ Collinear t.1 t.2.1 t.2.2)).Nonempty) :
    ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r ∧
      ∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
        ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
          ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2)  := by
  obtain ⟨t, ht_mem, ht_min⟩ := Finset.exists_min_image
    ((P ×ˢ P ×ˢ P).filter
      (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
        t.1 ≠ t.2.1 ∧ ¬ Collinear t.1 t.2.1 t.2.2))
    (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
      ((t.2.1.1 - t.1.1) * (t.2.2.2 - t.1.2)
         - (t.2.1.2 - t.1.2) * (t.2.2.1 - t.1.1))^2 /
        ((t.2.1.1 - t.1.1)^2 + (t.2.1.2 - t.1.2)^2))
    h_nonempty
  obtain ⟨ht1P, ht21P, ht22P, ht_ne, ht_ncol⟩ :=
    s84_sub_2 P h_noncol h_skolem h_witness h_nonempty t ht_mem
  refine ⟨t.1, ht1P, t.2.1, ht21P, t.2.2, ht22P, ht_ne, ht_ncol, ?_⟩
  intro p' hp' q' hq' r' hr' hpq' hncol'
  exact ht_min _
    (s84_sub_1 P h_noncol h_skolem h_witness h_nonempty
      p' hp' q' hq' r' hr' hpq' hncol')

end Problems.sylvester_gallai
