import Mathlib
import Problems.Combinatorics.uc_mainline.Defs
import Problems.Combinatorics.uc_mainline.T_projection_accounts
import Problems.Combinatorics.uc_mainline.T_witness_number_deficit
import Problems.Combinatorics.uc_mainline.T_section_pays_nothing_outside
import Problems.Combinatorics.uc_mainline.T_gt1_gives_target

/-!
# Theorem 8.33 of `uc_tight_coordinate.md` (deficit two collapses the residual)

> **Theorem 8.33 (deficit two collapses the residual).** (D, cap, sep) If some
> rare coordinate has deficit two then `T_b` is empty, so N1 fails at **every**
> tight source and `H = A_x` is a common fold at no tight source. Neither (D+),
> nor Proposition 4(2), nor hypothesis (P) is used.

(`uc_tight_coordinate.md`, Section 8.)  Vocabulary of that section:
`T_b = {x ∈ T : every rare coordinate implies x}` (Theorem 8.20);
**N1** at `x` is `d_{A_x}(j) ≤ d_{B_x}(j)` for every coordinate `j` (Lemma 8.15);
a common fold `H = A_x` is a downward bijection `B_x → A_x` (`IsFold`).
Hypothesis (D) is `|V|`-minimality in the capped nonregular class with every
coordinate active (`FrameD`), (cap) is contained in it, (sep) is `Separating`.
The three conclusions are the three clauses of the sentence.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

variable {V : Type*} [DecidableEq V] [Fintype V]

/-! ## Helpers for clause 1

The route is Theorem 3.1 of `uc_minimal_deficit_pair.md` with `y' := y`, in the
shorter form recorded in `notes/deficit_two_notes.md`: under `y ⇒ x` with `x`
tight and `σ_y = 2` the `x`-only rows are a single row `{x} ∪ c₀`, the edge
family `C_x` is `∅` or `{c₀}`, every `x`-avoiding row lies below `c₀`, and every
coordinate off `c₀` is rare with `σ ≥ 2`; so `π_x(F)` is capped and nonregular
on one coordinate less, against `|V|`-minimality.
-/

section DeficitTwo

variable {F : Finset (Finset V)} {x y : V}

/-- Under `y ⇒ x`, no `x`-edge trace contains `y` (an edge trace avoids `x`). -/
theorem dt_edgeTrace_deg_y_eq_zero (himp : Implies F y x) :
    deg (edgeTrace F x) y = 0 := by
  rw [deg_eq_card_filter, Finset.card_eq_zero, Finset.filter_eq_empty_iff]
  intro c hc hyc
  obtain ⟨hcF, hxc, -⟩ := mem_edgeTrace.mp hc
  exact hxc (himp c hcF hyc)

/-- With `x` tight, `σ_y = 2` and `y ⇒ x`, exactly one row contains `x` and
avoids `y`. -/
theorem dt_card_xOnly (hx : Tight F x) (hy : sigma F y = 2) (himp : Implies F y x) :
    (F.filter (fun S => x ∈ S ∧ y ∉ S)).card = 1 := by
  have e1 : F.filter (fun S => x ∈ S ∧ y ∈ S)
      = (F.filter (fun S => x ∈ S)).filter (fun S => y ∈ S) := by
    ext S; simp only [Finset.mem_filter]; tauto
  have e2 : F.filter (fun S => x ∈ S ∧ y ∉ S)
      = (F.filter (fun S => x ∈ S)).filter (fun S => ¬ y ∈ S) := by
    ext S; simp only [Finset.mem_filter]; tauto
  have hsplit : (F.filter (fun S => x ∈ S ∧ y ∈ S)).card
      + (F.filter (fun S => x ∈ S ∧ y ∉ S)).card = deg F x := by
    rw [e1, e2, deg_eq_card_filter]
    exact Finset.card_filter_add_card_filter_not _
  have himpEq : F.filter (fun S => x ∈ S ∧ y ∈ S) = F.filter (fun S => y ∈ S) := by
    ext S
    simp only [Finset.mem_filter]
    exact ⟨fun h => ⟨h.1, h.2.2⟩, fun h => ⟨h.1, himp S h.1 h.2, h.2⟩⟩
  rw [himpEq, ← deg_eq_card_filter] at hsplit
  have hx' : sigma F x = 0 := hx
  simp only [sigma] at hx' hy
  omega

/-- `c ↦ c ∪ {x}` injects the `x`-edge traces into the `x`-only rows. -/
theorem dt_edgeTrace_card_le (hxy : y ≠ x) (himp : Implies F y x) :
    (edgeTrace F x).card ≤ (F.filter (fun S => x ∈ S ∧ y ∉ S)).card := by
  refine Finset.card_le_card_of_injOn (fun c => insert x c) ?_ ?_
  · intro c hc
    obtain ⟨hcF, hxc, hins⟩ := mem_edgeTrace.mp hc
    refine Finset.mem_filter.mpr ⟨hins, Finset.mem_insert_self x c, ?_⟩
    intro hy'
    rcases Finset.mem_insert.mp hy' with h | h
    · exact hxy h
    · exact hxc (himp c hcF h)
  · intro a ha b hb h
    rw [Finset.mem_coe] at ha hb
    have hxa := (mem_edgeTrace.mp ha).2.1
    have hxb := (mem_edgeTrace.mp hb).2.1
    have h' : insert x a = insert x b := h
    calc a = (insert x a).erase x := (Finset.erase_insert hxa).symm
      _ = (insert x b).erase x := by rw [h']
      _ = b := Finset.erase_insert hxb

/-- With a unique `x`-only row and an `x`-edge trace `c`, every row avoiding `x`
lies below `c` (the article's `X ⊆ ↓y₀`). -/
theorem dt_zeroRow_subset (hUC : UnionClosed F) (hxy : y ≠ x) (himp : Implies F y x)
    (hone : (F.filter (fun S => x ∈ S ∧ y ∉ S)).card = 1)
    {c : Finset V} (hc : c ∈ edgeTrace F x) {a : Finset V} (haF : a ∈ F) (hxa : x ∉ a) :
    a ⊆ c := by
  obtain ⟨hcF, hxc, hins⟩ := mem_edgeTrace.mp hc
  have hyc : y ∉ c := fun h => hxc (himp c hcF h)
  have hya : y ∉ a := fun h => hxa (himp a haF h)
  have hmem1 : insert x c ∈ F.filter (fun S => x ∈ S ∧ y ∉ S) := by
    refine Finset.mem_filter.mpr ⟨hins, Finset.mem_insert_self x c, ?_⟩
    intro h
    rcases Finset.mem_insert.mp h with h | h
    · exact hxy h
    · exact hyc h
  have hmem2 : a ∪ insert x c ∈ F.filter (fun S => x ∈ S ∧ y ∉ S) := by
    refine Finset.mem_filter.mpr ⟨hUC a haF _ hins, ?_, ?_⟩
    · exact Finset.mem_union_right _ (Finset.mem_insert_self x c)
    · intro h
      rcases Finset.mem_union.mp h with h | h
      · exact hya h
      · rcases Finset.mem_insert.mp h with h | h
        · exact hxy h
        · exact hyc h
  have heq : a ∪ insert x c = insert x c :=
    Finset.card_le_one.mp (le_of_eq hone) _ hmem2 _ hmem1
  intro z hz
  have hz' : z ∈ insert x c := by
    rw [← heq]
    exact Finset.mem_union_left _ hz
  rcases Finset.mem_insert.mp hz' with h | h
  · exact absurd hz (show z ∉ a by rw [h]; exact hxa)
  · exact h

/-- A coordinate `k ≠ x` outside the edge trace `c` misses every row of the zero
slice and misses the `x`-only row, hence has `σ_k ≥ 2`. -/
theorem dt_sigma_ge_two (hx : Tight F x) {c : Finset V} (hc : c ∈ edgeTrace F x)
    (hsub : ∀ a ∈ F, x ∉ a → a ⊆ c) {k : V} (hk : k ≠ x) (hkc : k ∉ c) :
    2 ≤ sigma F k := by
  obtain ⟨hcF, hxc, hins⟩ := mem_edgeTrace.mp hc
  have hmemx : insert x c ∈ F.filter (fun S => x ∈ S) :=
    Finset.mem_filter.mpr ⟨hins, Finset.mem_insert_self x c⟩
  have hsubset : F.filter (fun S => k ∈ S)
      ⊆ (F.filter (fun S => x ∈ S)).erase (insert x c) := by
    intro S hS
    obtain ⟨hSF, hkS⟩ := Finset.mem_filter.mp hS
    have hxS : x ∈ S := by
      by_contra hx'
      exact hkc (hsub S hSF hx' hkS)
    refine Finset.mem_erase.mpr ⟨?_, Finset.mem_filter.mpr ⟨hSF, hxS⟩⟩
    intro h
    rw [h] at hkS
    rcases Finset.mem_insert.mp hkS with h' | h'
    · exact hk h'
    · exact hkc h'
  have hcard := Finset.card_le_card hsubset
  rw [Finset.card_erase_of_mem hmemx] at hcard
  have hpos : 0 < (F.filter (fun S => x ∈ S)).card := Finset.card_pos.mpr ⟨_, hmemx⟩
  have hdk : deg F k = (F.filter (fun S => k ∈ S)).card := deg_eq_card_filter F k
  have hdx : deg F x = (F.filter (fun S => x ∈ S)).card := deg_eq_card_filter F x
  have hx' : sigma F x = 0 := hx
  simp only [sigma] at hx' ⊢
  omega

end DeficitTwo

/-- Theorem 8.33, clause 1: under (D, cap, sep), a rare coordinate of deficit
two forces `T_b = ∅`: no tight `x` is implied by every rare coordinate. -/
theorem deficit_two_Tb_empty (F : Finset (Finset V)) (hD : FrameD F) (hsep : Separating F)
    (h2 : ∃ y : V, sigma F y = 2) :
    ∀ x : V, Tight F x → ∃ y : V, Rare F y ∧ ¬ Implies F y x := by
  obtain ⟨hUC, h0, hact, hcap, -, hmin⟩ := hD
  obtain ⟨y, hy⟩ := h2
  intro x hx
  refine ⟨y, ?_, ?_⟩
  · show 0 < sigma F y
    rw [hy]; norm_num
  intro himp
  have hx' : sigma F x = 0 := hx
  have hxy : y ≠ x := by
    rintro rfl
    omega
  have hdegy : deg (edgeTrace F x) y = 0 := dt_edgeTrace_deg_y_eq_zero himp
  have hone : (F.filter (fun S => x ∈ S ∧ y ∉ S)).card = 1 := dt_card_xOnly hx hy himp
  have hcle : (edgeTrace F x).card ≤ 1 := by
    have h := dt_edgeTrace_card_le hxy himp
    omega
  -- `π_x(F)` is not regular: at `y` the edge family pays at most `1 < 2 = σ_y`.
  have hnotreg : ¬ Regular (proj F x) := by
    rw [proj_regular_iff F x hact]
    intro hreg
    have h := hreg y hxy
    have hsig : sigma (edgeTrace F x) y = ((edgeTrace F x).card : ℤ) := by
      simp only [sigma, hdegy]
      norm_num
    rw [hsig, hy] at h
    omega
  -- `π_x(F)` is capped.
  have hcapped : Capped (proj F x) := by
    rw [proj_capped_iff]
    intro k hk
    have hcapk := hcap k
    rcases Finset.eq_empty_or_nonempty (edgeTrace F x) with he | ⟨c, hc⟩
    · have hd : deg (edgeTrace F x) k = 0 := by
        rw [deg_eq_card_filter, he, Finset.filter_empty, Finset.card_empty]
      have hc0 : (edgeTrace F x).card = 0 := by rw [he, Finset.card_empty]
      have hsig : sigma (edgeTrace F x) k = 0 := by
        simp only [sigma, hd, hc0]
        norm_num
      omega
    · have hsingle : edgeTrace F x = {c} :=
        Finset.eq_singleton_iff_unique_mem.mpr
          ⟨hc, fun z hz => Finset.card_le_one.mp hcle z hz c hc⟩
      have hc1 : (edgeTrace F x).card = 1 := by rw [hsingle, Finset.card_singleton]
      by_cases hkc : k ∈ c
      · have hd : deg (edgeTrace F x) k = 1 := by
          rw [deg_eq_card_filter, hsingle, Finset.filter_singleton, if_pos hkc,
            Finset.card_singleton]
        have hsig : sigma (edgeTrace F x) k = -1 := by
          simp only [sigma, hd, hc1]
          norm_num
        omega
      · have hd : deg (edgeTrace F x) k = 0 := by
          rw [deg_eq_card_filter, hsingle, Finset.filter_singleton, if_neg hkc,
            Finset.card_empty]
        have hsig : sigma (edgeTrace F x) k = 1 := by
          simp only [sigma, hd, hc1]
          norm_num
        have hsub : ∀ a ∈ F, x ∉ a → a ⊆ c := fun a haF hxa =>
          dt_zeroRow_subset hUC hxy himp hone hc haF hxa
        have h2k := dt_sigma_ge_two hx hc hsub hk hkc
        omega
  -- `π_x(F)` lives on one coordinate less, contradicting `|V|`-minimality.
  have hg := hmin (proj F x) (proj_unionClosed F x hUC) (proj_empty_mem F x h0) hcapped hnotreg
  have hgF : ground F = (Finset.univ : Finset V) := by
    simp only [ground]
    exact Finset.filter_true_of_mem (fun j _ => hact j)
  have hsub : ground (proj F x) ⊆ Finset.univ.erase x := by
    intro j hj
    refine Finset.mem_erase.mpr ⟨?_, Finset.mem_univ j⟩
    intro hjx
    have hja : Active (proj F x) j := (Finset.mem_filter.mp hj).2
    rw [hjx, Active, proj_deg_self] at hja
    exact absurd hja (lt_irrefl 0)
  have hcard := Finset.card_le_card hsub
  rw [Finset.card_erase_of_mem (Finset.mem_univ x), Finset.card_univ] at hcard
  rw [hgF, Finset.card_univ] at hg
  have hpos : 0 < Fintype.card V := Fintype.card_pos_iff.mpr ⟨x⟩
  omega

/-! ## Helpers for clauses 2 and 3

Clause 2 is Theorem 8.31 (1) ⇒ (3) specialised to deficit two: if N1 held at a
tight `x`, the zero slice `A_x` would be capped (`dt_zeroSlice_capped`), hence
regular by `|V|`-minimality on one coordinate less (`dt_zeroSlice_regular`),
which forces every coordinate active in `A_x` to be tight in `F`
(`dt_tight_of_active_zeroSlice`) — contradicting the rare non-implier produced
by clause 1.  Clause 3 is Lemma 8.15: a fold pushes `A_x` into `B_x` degreewise
(`dt_fold_deg_le`), i.e. N1, which clause 2 refutes.
-/

section DeficitTwoN1

variable {F : Finset (Finset V)} {x : V}

/-- The zero slice pays nothing at its own source. -/
theorem dt_deg_zeroSlice_self (F : Finset (Finset V)) (x : V) :
    deg (zeroSlice F x) x = 0 :=
  deg_eq_zero_of_not_mem _ _ (fun _ hS => not_mem_of_mem_zeroSlice hS)

/-- Under N1 at a tight source, the zero slice is capped: `2 d_A(j) ≤ d_A(j) +
d_B(j) = d_F(j) ≤ N/2 = |A|`. -/
theorem dt_zeroSlice_capped (hx : Tight F x) (hcap : Capped F)
    (hN1 : ∀ j : V, deg (zeroSlice F x) j ≤ deg (oneSlice F x) j) :
    Capped (zeroSlice F x) := by
  intro j
  have hcards := card_zeroSlice_eq_card_oneSlice F x hx
  have hsum := card_zeroSlice_add_card_oneSlice F x
  by_cases hj : j = x
  · have hz := dt_deg_zeroSlice_self F x
    rw [hj]
    simp only [sigma, hz]
    omega
  · have hsplit := deg_zeroSlice_add_deg_oneSlice F x j hj
    have hcj := hcap j
    have hn := hN1 j
    simp only [sigma] at hcj ⊢
    omega

/-- A capped zero slice is regular: it is union-closed with `∅` and lives on one
coordinate less, so `|V|`-minimality forbids it from being nonregular. -/
theorem dt_zeroSlice_regular (hUC : UnionClosed F) (h0 : ∅ ∈ F)
    (hact : ∀ j : V, Active F j) (hmin : Minimal F) (hcapA : Capped (zeroSlice F x)) :
    Regular (zeroSlice F x) := by
  by_contra hnr
  have hg := hmin _ (zeroSlice_unionClosed F x hUC) (zeroSlice_empty_mem F x h0) hcapA hnr
  have hgF : ground F = (Finset.univ : Finset V) := by
    simp only [ground]
    exact Finset.filter_true_of_mem (fun j _ => hact j)
  have hsubg : ground (zeroSlice F x) ⊆ Finset.univ.erase x := by
    intro j hj
    refine Finset.mem_erase.mpr ⟨?_, Finset.mem_univ j⟩
    intro hjx
    have hja : Active (zeroSlice F x) j := (Finset.mem_filter.mp hj).2
    rw [hjx, Active, dt_deg_zeroSlice_self] at hja
    exact absurd hja (lt_irrefl 0)
  have hcard := Finset.card_le_card hsubg
  rw [Finset.card_erase_of_mem (Finset.mem_univ x), Finset.card_univ] at hcard
  rw [hgF, Finset.card_univ] at hg
  have hpos : 0 < Fintype.card V := Fintype.card_pos_iff.mpr ⟨x⟩
  omega

/-- Under N1 at a tight source with the zero slice regular, every coordinate
active in the zero slice is tight in `F`: `d_F(j) = d_A(j) + d_B(j) ≥ 2 d_A(j)
= |A| = N/2 ≥ d_F(j)`. -/
theorem dt_tight_of_active_zeroSlice (hx : Tight F x) (hcap : Capped F)
    (hN1 : ∀ j : V, deg (zeroSlice F x) j ≤ deg (oneSlice F x) j)
    (hregA : Regular (zeroSlice F x)) {j : V} (hj : Active (zeroSlice F x) j) :
    Tight F j := by
  have hne : j ≠ x := by
    intro h
    rw [h, Active, dt_deg_zeroSlice_self] at hj
    exact absurd hj (lt_irrefl 0)
  have hsig0 : sigma (zeroSlice F x) j = 0 := hregA j hj
  have hsplit := deg_zeroSlice_add_deg_oneSlice F x j hne
  have hn := hN1 j
  have hcards := card_zeroSlice_eq_card_oneSlice F x hx
  have hsum := card_zeroSlice_add_card_oneSlice F x
  have hcj := hcap j
  show sigma F j = 0
  simp only [sigma] at hsig0 hcj ⊢
  omega

/-- Lemma 8.15: a downward bijection `β : B_x → A_x` pushes degrees down, i.e.
N1 holds at `x`.  Indeed `A_x ∩ {j ∈ ·}` is the `β`-image of
`B_x ∩ {j ∈ β ·} ⊆ B_x ∩ {j ∈ ·}`. -/
theorem dt_fold_deg_le (h : IsFold F x) (j : V) :
    deg (zeroSlice F x) j ≤ deg (oneSlice F x) j := by
  obtain ⟨β, hbij, hsubs⟩ := h
  rw [deg_eq_card_filter, deg_eq_card_filter]
  have himg : (zeroSlice F x).filter (fun a => j ∈ a)
      = ((oneSlice F x).filter (fun b => j ∈ β b)).image β := by
    ext a
    simp only [Finset.mem_filter, Finset.mem_image]
    constructor
    · rintro ⟨haA, hja⟩
      obtain ⟨b, hb, hba⟩ := hbij.surjOn (Finset.mem_coe.mpr haA)
      refine ⟨b, ⟨Finset.mem_coe.mp hb, ?_⟩, hba⟩
      rw [hba]; exact hja
    · rintro ⟨b, ⟨hbB, hjb⟩, hba⟩
      have hmem := hbij.mapsTo (Finset.mem_coe.mpr hbB)
      rw [hba] at hmem hjb
      exact ⟨Finset.mem_coe.mp hmem, hjb⟩
  rw [himg, Finset.card_image_of_injOn
    (hbij.injOn.mono (Finset.coe_subset.mpr (Finset.filter_subset _ _)))]
  refine Finset.card_le_card ?_
  intro b hb
  simp only [Finset.mem_filter] at hb ⊢
  exact ⟨hb.1, hsubs b hb.1 hb.2⟩

end DeficitTwoN1

/-- Theorem 8.33, clause 2: N1 fails at every tight source. -/
theorem deficit_two_N1_fails (F : Finset (Finset V)) (hD : FrameD F) (hsep : Separating F)
    (h2 : ∃ y : V, sigma F y = 2) :
    ∀ x : V, Tight F x → ∃ j : V, deg (oneSlice F x) j < deg (zeroSlice F x) j := by
  intro x hx
  by_contra hcon
  push Not at hcon
  have hUC := hD.1
  have h0 := hD.2.1
  have hact := hD.2.2.1
  have hcap := hD.2.2.2.1
  have hmin := hD.2.2.2.2.2
  have hcapA : Capped (zeroSlice F x) := dt_zeroSlice_capped hx hcap hcon
  have hregA : Regular (zeroSlice F x) := dt_zeroSlice_regular hUC h0 hact hmin hcapA
  -- Clause 1: a rare coordinate that does not imply `x`.
  obtain ⟨y, hyrare, hyimp⟩ := deficit_two_Tb_empty F hD hsep h2 x hx
  have hex : ∃ S ∈ F, y ∈ S ∧ x ∉ S := by
    by_contra hno
    push Not at hno
    exact hyimp hno
  obtain ⟨S, hSF, hyS, hxS⟩ := hex
  have hactA : Active (zeroSlice F x) y := by
    rw [Active, deg_eq_card_filter, Finset.card_pos]
    exact ⟨S, Finset.mem_filter.mpr ⟨mem_zeroSlice.mpr ⟨hSF, hxS⟩, hyS⟩⟩
  have htight : sigma F y = 0 := dt_tight_of_active_zeroSlice hx hcap hcon hregA hactA
  have hrare : 0 < sigma F y := hyrare
  omega

/-- Theorem 8.33, clause 3: `H = A_x` is a common fold at no tight source. -/
theorem deficit_two_no_fold (F : Finset (Finset V)) (hD : FrameD F) (hsep : Separating F)
    (h2 : ∃ y : V, sigma F y = 2) :
    ∀ x : V, Tight F x → ¬ IsFold F x := by
  intro x hx hfold
  obtain ⟨j, hj⟩ := deficit_two_N1_fails F hD hsep h2 x hx
  have hle := dt_fold_deg_le hfold j
  omega

#print axioms deficit_two_Tb_empty
#print axioms deficit_two_N1_fails
#print axioms deficit_two_no_fold

end Problems.Combinatorics.uc_mainline
