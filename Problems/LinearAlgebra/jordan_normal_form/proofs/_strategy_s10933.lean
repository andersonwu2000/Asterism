import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct proof: enumerate {q | S q} via its sorted order-embedding.
-- Take s := univ.filter S, witness p := s.card and b t := (s.orderEmbOfFin rfl t : ℕ).
-- StrictMono / bound / iff come from orderEmbOfFin's strict monotonicity, range = s, and
-- Fin.val injectivity; the first-start = 0 case uses minimality of the index-0 element
-- (0 ∈ s by h0, monotonicity forces b 0 ≤ 0); 0 < n → 0 < p from card_pos via 0 ∈ s.
theorem s10933 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (b : Fin p → ℕ),
      StrictMono b ∧ (∀ t : Fin p, b t < n) ∧
      (∀ t : Fin p, (t : ℕ) = 0 → b t = 0) ∧
      (0 < n → 0 < p) ∧
      (∀ q : Fin n, (S q ↔ ∃ t : Fin p, b t = (q : ℕ)))  := by
  classical
  set s : Finset (Fin n) := Finset.univ.filter (fun q => S q) with hs
  refine ⟨s.card, fun t => ((s.orderEmbOfFin rfl t : Fin n) : ℕ), ?_, ?_, ?_, ?_, ?_⟩
  · intro a b hab
    exact Fin.lt_def.mp ((s.orderEmbOfFin rfl).strictMono hab)
  · intro t
    exact (s.orderEmbOfFin rfl t).isLt
  · intro t ht
    have hn : 0 < n := lt_of_le_of_lt (Nat.zero_le _) (s.orderEmbOfFin rfl t).isLt
    have h0mem : (⟨0, hn⟩ : Fin n) ∈ s := by
      rw [hs, Finset.mem_filter]; exact ⟨Finset.mem_univ _, h0 ⟨0, hn⟩ rfl⟩
    have hr : (⟨0, hn⟩ : Fin n) ∈ Set.range (s.orderEmbOfFin (rfl : s.card = s.card)) := by
      rw [Finset.range_orderEmbOfFin]; exact Finset.mem_coe.mpr h0mem
    obtain ⟨t', ht'⟩ := hr
    have hle : t ≤ t' := by rw [Fin.le_def, ht]; exact Nat.zero_le _
    have hmono := (s.orderEmbOfFin rfl).monotone hle
    rw [ht'] at hmono
    have hle0 : (s.orderEmbOfFin rfl t).val ≤ 0 := Fin.le_def.mp hmono
    simpa using hle0
  · intro hn
    refine Finset.card_pos.mpr ⟨⟨0, hn⟩, ?_⟩
    rw [hs, Finset.mem_filter]
    exact ⟨Finset.mem_univ _, h0 ⟨0, hn⟩ rfl⟩
  · intro q
    constructor
    · intro hSq
      have hqs : q ∈ s := by rw [hs, Finset.mem_filter]; exact ⟨Finset.mem_univ _, hSq⟩
      have hr : q ∈ Set.range (s.orderEmbOfFin (rfl : s.card = s.card)) := by
        rw [Finset.range_orderEmbOfFin]; exact Finset.mem_coe.mpr hqs
      obtain ⟨t, ht⟩ := hr
      exact ⟨t, by simp only [ht]⟩
    · rintro ⟨t, ht⟩
      have heq : s.orderEmbOfFin rfl t = q := Fin.val_injective ht
      have hmem : s.orderEmbOfFin rfl t ∈ s := s.orderEmbOfFin_mem rfl t
      rw [heq, hs, Finset.mem_filter] at hmem
      exact hmem.2

end Problems.LinearAlgebra.jordan_normal_form
