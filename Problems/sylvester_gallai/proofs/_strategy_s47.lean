import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s47_sub_1
import Problems.sylvester_gallai.proofs.L_s47_sub_2

namespace Problems.sylvester_gallai

theorem s47 : ∀ (P : Finset (ℝ × ℝ)) (p a b : ℝ × ℝ),
    p ∈ P → a ∈ P → b ∈ P →
    a ≠ b → ¬ Collinear p a b →
    (∀ q ∈ P, ∀ x ∈ P, ∀ y ∈ P,
      x ≠ y → ¬ Collinear q x y →
      ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
      ((x.1 - y.1) ^ 2 + (x.2 - y.2) ^ 2) ≤
      ((q.1 - y.1) * (x.2 - y.2) - (q.2 - y.2) * (x.1 - y.1)) ^ 2 *
      ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2)) →
    (∀ (p' a' b' c' : ℝ × ℝ),
      ¬ Collinear p' a' b' → Collinear a' b' c' →
      a' ≠ b' → c' ≠ a' → c' ≠ b' →
      ∃ x ∈ ({a', b', c'} : Finset (ℝ × ℝ)),
      ∃ z ∈ ({a', b', c'} : Finset (ℝ × ℝ)),
        x ≠ z ∧ ¬ Collinear x p' z ∧
        ((x.1 - z.1) * (p'.2 - z.2) - (x.2 - z.2) * (p'.1 - z.1)) ^ 2 *
        ((a'.1 - b'.1) ^ 2 + (a'.2 - b'.2) ^ 2) <
        ((p'.1 - b'.1) * (a'.2 - b'.2) - (p'.2 - b'.2) * (a'.1 - b'.1)) ^ 2 *
        ((p'.1 - z.1) ^ 2 + (p'.2 - z.2) ^ 2)) →
    ∀ r ∈ P, Collinear a b r → r = a ∨ r = b  := by
  intro P p a b hp ha hb hab hnc hmin hkelly
  intro r hr hcol
  by_contra hne
  push Not at hne
  obtain ⟨hna, hnb⟩ := hne
  obtain ⟨xk, hxk_mem, zk, hzk_mem, hne_xkzk, hnc_xkpzk, hlt⟩ :=
    hkelly p a b r hnc hcol hab hna hnb
  have hxk_P := s47_sub_1 P a b r xk ha hb hr hxk_mem
  have hzk_P := s47_sub_1 P a b r zk ha hb hr hzk_mem
  have hpz := s47_sub_2 xk p zk hnc_xkpzk
  have hge := hmin xk hxk_P p hp zk hzk_P hpz hnc_xkpzk
  linarith

end Problems.sylvester_gallai
