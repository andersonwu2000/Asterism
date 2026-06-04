import Mathlib

namespace Library.LinearAlgebra.JordanForm.ChainPartition

-- fin_sigma_offset_decomp: q = prefix_sum(block) + within_block offset via finSigmaFinEquiv
-- Rounds through finSigmaFinEquiv_apply: simp closes the roundtrip, linarith extracts arithmetic.
theorem fin_sigma_offset_decomp {p : ℕ} (l : Fin p → ℕ) :
    ∀ q : Fin (∑ t, l t), (q : ℕ) =
      (∑ j : Fin ↑(finSigmaFinEquiv.symm q).1,
        l (Fin.castLE (finSigmaFinEquiv.symm q).1.isLt.le j))
      + ((finSigmaFinEquiv.symm q).2 : ℕ) := by
  intro q
  have h := q.isLt
  have key : (finSigmaFinEquiv (finSigmaFinEquiv.symm q) : ℕ) = (q : ℕ) := by
    simp
  simp only [finSigmaFinEquiv_apply] at key
  linarith [key]

-- entry_kind: Builder
-- start_offset_zero_fin_sigma: block-start iff offset=0 via finSigmaFinEquiv.symm uniqueness
theorem start_offset_zero_fin_sigma {p : ℕ} (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t)
    (S : Fin (∑ t, l t) → Prop)
    (hstart : ∀ q : Fin (∑ t, l t), (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ))) :
    ∀ q : Fin (∑ t, l t),
      (S q ↔ ((finSigmaFinEquiv.symm q).2 : ℕ) = 0) := by
  intro q
  rw [hstart]
  set σ := finSigmaFinEquiv.symm q with hσ_def
  have hq_val : (q : ℕ) = ∑ i : Fin σ.1, l (Fin.castLE σ.1.2.le i) + σ.2 := by
    have happ := @finSigmaFinEquiv_apply p l σ
    have heq : finSigmaFinEquiv σ = q := finSigmaFinEquiv.apply_symm_apply q
    exact_mod_cast heq ▸ happ
  constructor
  · rintro ⟨t, ht⟩
    have hfwd : finSigmaFinEquiv ⟨t, ⟨0, hpos t⟩⟩ = q := by
      ext
      rw [finSigmaFinEquiv_apply]
      simp only [add_zero]
      exact_mod_cast ht
    have hσ_eq : (⟨t, ⟨0, hpos t⟩⟩ : Σ i : Fin p, Fin (l i)) = σ :=
      finSigmaFinEquiv.injective
        (hfwd.trans (finSigmaFinEquiv.apply_symm_apply q).symm)
    rw [← hσ_eq]
  · intro h
    exact ⟨σ.1, by omega⟩

-- Recast `Fin n ≅ Fin (∑ l)` via `subst hsum`, then take `e := finSigmaFinEquiv.symm`
-- (position ↦ block × within-block offset) with `o t := ∑_{j<t} l j` (prefix sums of
-- block lengths). Split into two strictly simpler claims:
--   `fin_sigma_offset_decomp` — pure `finSigmaFinEquiv_apply` rewrite (no S, no hstart).
--   `start_offset_zero_fin_sigma` — start-iff-offset-zero at the concrete equiv (re-uses the
--     prefix-sum uniqueness lemma proved at sibling level).
theorem block_equiv_from_gaps {n p : ℕ} (S : Fin n → Prop) (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t) (hsum : ∑ t, l t = n)
    (hstart : ∀ q : Fin n, (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ))) :
    ∃ (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0))   := by
  subst hsum
  have h_offset_decomp : ∀ q : Fin (∑ t, l t), (q : ℕ) =
      (∑ j : Fin ↑(finSigmaFinEquiv.symm q).1,
        l (Fin.castLE (finSigmaFinEquiv.symm q).1.isLt.le j))
      + ((finSigmaFinEquiv.symm q).2 : ℕ) := fin_sigma_offset_decomp l
  have h_start_iff : ∀ q : Fin (∑ t, l t),
      (S q ↔ ((finSigmaFinEquiv.symm q).2 : ℕ) = 0) :=
    start_offset_zero_fin_sigma l hpos S hstart
  exact ⟨finSigmaFinEquiv.symm,
    fun t => ∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j),
    h_offset_decomp, h_start_iff⟩

theorem start_iff_g_val {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∀ q : Fin n, (S q ↔ ∃ t : Fin p, (g t : ℕ) = (q : ℕ)) := by grind

-- entry_kind: Builder
-- Witness: l t = B(t+1) - B(t) where B i = if i < p then b ⟨i,_⟩ else n.
-- Positivity: B strictly increases (StrictMono b / hlt).
-- Sum = n: Finset.sum_range_tsub telescopes B p - B 0 = n - 0.
-- Prefix = b t: same telescoping to B t - B 0 = b t.
-- Self-contained (no sibling imports) to avoid triggering rebuild of broken _strategy_s10936.
theorem gaps_from_boundary {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = b t) := by
  -- Extended boundary on ℕ
  set B : ℕ → ℕ := fun i => if h : i < p then b ⟨i, h⟩ else n with hB_def
  have hBmono : Monotone B := by
    intro i j hij
    simp only [hB_def]
    by_cases hi : i < p
    · by_cases hj : j < p
      · rw [dif_pos hi, dif_pos hj]
        exact hmono.le_iff_le.2 (Fin.mk_le_mk.2 hij)
      · rw [dif_pos hi, dif_neg hj]; exact (hlt ⟨i, hi⟩).le
    · have hj : ¬ j < p := fun hc => hi (Nat.lt_of_le_of_lt hij hc)
      rw [dif_neg hi, dif_neg hj]
  have hB_val : ∀ t : Fin p, B t.val = b t := fun t => dif_pos t.isLt
  have hBp : B p = n := dif_neg (lt_irrefl p)
  have hB0 : B 0 = 0 := by
    simp only [hB_def]
    rcases Nat.eq_zero_or_pos p with rfl | hp0
    · -- p = 0 forces n = 0 via hp
      rw [dif_neg (Nat.lt_irrefl 0)]
      rcases Nat.eq_zero_or_pos n with rfl | hn
      · rfl
      · have := hp hn; omega
    · rw [dif_pos hp0]; exact hzero ⟨0, hp0⟩ rfl
  refine ⟨fun t => B (t.val + 1) - B t.val, ?_, ?_, ?_⟩
  · -- Positivity
    intro t
    apply Nat.sub_pos_of_lt
    simp only [hB_def, dif_pos t.isLt]
    by_cases h : t.val + 1 < p
    · rw [dif_pos h]; exact hmono (by simp [Fin.lt_def])
    · rw [dif_neg h]; exact hlt t
  · -- Total sum = n
    rw [Fin.sum_univ_eq_sum_range (fun i => B (i + 1) - B i) p,
        Finset.sum_range_tsub hBmono, hBp, hB0, Nat.sub_zero]
  · -- Prefix sums = b t
    intro t
    -- Fin.castLE preserves .val, so simp it away before telescoping
    simp only [Fin.val_castLE]
    rw [Fin.sum_univ_eq_sum_range (fun i => B (i + 1) - B i) t.val,
        Finset.sum_range_tsub hBmono, hB_val t, hB0, Nat.sub_zero]

-- entry_kind: Builder
-- pos_p_when_pos_n: 0 < n implies 0 < p by finding element 0 in range g via h0 + hrange
theorem pos_p_when_pos_n {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    0 < n → 0 < p := by
  intro hn
  have hq : (⟨0, hn⟩ : Fin n) ∈ Set.range g := (hrange ⟨0, hn⟩).mp (h0 ⟨0, hn⟩ rfl)
  obtain ⟨i, _⟩ := hq
  exact Nat.pos_of_ne_zero (Fin.pos i).ne'

-- entry_kind: Builder
-- start_enum_at_zero: if g is StrictMono with range = S, and S contains the
-- zeroth element, then g 0 = 0
theorem start_enum_at_zero {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∀ t : Fin p, (t : ℕ) = 0 → (g t : ℕ) = 0 := by
  intro t ht
  have hn : 0 < n := Nat.lt_of_le_of_lt (Nat.zero_le _) (g t).isLt
  have hS0 : S ⟨0, hn⟩ := h0 ⟨0, hn⟩ rfl
  obtain ⟨t', ht'⟩ := (hrange ⟨0, hn⟩).mp hS0
  -- ht' : g t' = ⟨0, hn⟩
  have ht'val : (t' : ℕ) = 0 := by
    by_contra h
    have h_pos : 0 < (t' : ℕ) := Nat.pos_of_ne_zero h
    have hp' : 0 < p := Nat.lt_trans h_pos t'.isLt
    have hlt : (⟨0, hp'⟩ : Fin p) < t' := Fin.mk_lt_mk.mpr h_pos
    have hlt2 := hmono hlt
    rw [Fin.lt_def] at hlt2
    simp [ht'] at hlt2
  have htval_eq : t = t' := Fin.ext (by omega)
  rw [htval_eq, ht']

-- Instantiate `gaps_from_boundary` at `b t := (g t : ℕ)`.
-- Premises:
--  * StrictMono b ← `hmono` (Fin order is val-defined)
--  * b t < n ← `Fin.isLt`
--  * t = 0 → b t = 0 ← sub-goal `start_enum_at_zero`
--  * 0 < n → 0 < p ← sub-goal `pos_p_when_pos_n`
theorem gaps_for_starts {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (g t : ℕ))  := by
  exact gaps_from_boundary (fun t => (g t : ℕ))
    (fun a b hab => hmono hab)
    (fun t => (g t).isLt)
    (start_enum_at_zero S h0 p g hmono hrange)
    (pos_p_when_pos_n S h0 p g hmono hrange)

-- Read the gap lengths off the given monotone start-enumeration `g`: set boundaries
-- `b t := (g t : ℕ)`, build the gaps from those boundaries, and transfer the start
-- characterisation along the prefix-sum identity `prefix_t = (g t : ℕ)`.
--   `gaps_for_starts` — gaps `l` (positive, summing to `n`) whose `t`-th prefix sum is `(g t : ℕ)`.
--   `start_iff_g_val` — `S q` iff `q` is one of the enumerated start values `(g t : ℕ)`.
-- Both are strictly simpler: the first drops the `S`-characterisation to a per-index identity,
-- the second is a pure `hrange` + `Fin.val`-injectivity rewrite.
theorem gaps_of_starts {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ (l : Fin p → ℕ),
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ q : Fin n, (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ)))  := by
  have h_gaps := gaps_for_starts S h0 p g hmono hrange
  have h_iff := start_iff_g_val S h0 p g hmono hrange
  obtain ⟨l, hpos, hsum, hprefix⟩ := h_gaps
  refine ⟨l, hpos, hsum, fun q => ?_⟩
  rw [h_iff q]
  exact exists_congr fun t => by rw [hprefix t]

theorem start_enumeration {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (g : Fin p → Fin n), StrictMono g ∧ ∀ q : Fin n, S q ↔ q ∈ Set.range g  := by
  classical
  let T : Finset (Fin n) := Finset.univ.filter S
  refine ⟨T.card, T.orderEmbOfFin rfl, (T.orderEmbOfFin rfl).strictMono, ?_⟩
  intro q
  rw [Finset.range_orderEmbOfFin]
  simp [T]

theorem partition_from_enumeration {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ (p' : ℕ) (l : Fin p' → ℕ) (e : Fin n ≃ Σ t : Fin p', Fin (l t)) (o : Fin p' → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0)) := by
  -- `gaps_of_starts`: turn the ordered start enumeration `g` into block lengths `l : Fin p → ℕ`
  --   (gaps between consecutive starts), with prefix-sum of the first `t` blocks recovering the
  --   `t`-th start, so `S q ↔ q` is some block boundary.
  have h_gaps := gaps_of_starts S h0 p g hmono hrange
  obtain ⟨l, hpos, hsum, hstart⟩ := h_gaps
  -- `block_equiv_from_gaps`: from the gap data build the contiguous-block bijection `e` and
  --   prefix-sum offsets `o`, giving the offset decomposition and the `S q ↔ position-0` alignment.
  have h_equiv := block_equiv_from_gaps S l hpos hsum hstart
  obtain ⟨e, o, ho, halign⟩ := h_equiv
  exact ⟨p, l, e, o, ho, halign⟩

-- Cut `Fin n` at the start set `S` into contiguous blocks, then read off both alignments.
-- `start_enumeration` lists the start indices in strictly-increasing order (`g` with
--   `Set.range g = {q | S q}`); `partition_from_enumeration` turns that ordered list into the
--   block data `(p, l, e, o)` (block t = the gap between consecutive starts) and verifies the
--   offset decomposition + the `S q ↔ position 0` alignment. The first sub-goal is pure Finset
--   enumeration (`orderEmbOfFin`); the second is monotone arithmetic with the start order
--   already discovered — neither re-states the parent.
theorem chain_block_partition {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (l : Fin p → ℕ) (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0))  := by
  obtain ⟨p, g, hmono, hrange⟩ := start_enumeration S h0
  exact partition_from_enumeration S h0 p g hmono hrange

end Library.LinearAlgebra.JordanForm.ChainPartition
