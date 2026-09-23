import Mathlib
import Problems.Combinatorics.uc_mainline.Defs

/-!
# Theorem 10.1 of `uc_tight_coordinate.md` (O4 at a tight source pays nothing outside)

Setting of that section: fix a tight source `i` and write, as in the
catalogue's Section 4, `F = A u (B + i)`, `J = A u B`, `C = A cap B`,
`Q = A minus C`, `R = B minus C`, `j = |J|`, `c = |C|`. Tightness gives
`|A| = |B| = N/2`, so `|Q| = |R| = N/2 - c` and `j = N - c`. A **section** is
a `Q' <= J minus C` with the three legality conditions of the catalogue:
`Q'` lower in `J`, `C v Q' <= C`, and `Q' v Q' <= Q' u C`. Its endpoint is
`F_{Q'} = (C u Q') u ((J minus Q') + i)`.

> **Theorem 10.1 (O4 at a tight source pays nothing outside).** (cap,
> nonregular) Let `i` be tight. For every legal section `Q'`:
>
> 1. `F_{Q'}` is capped at every `k != i`, with the same slack as `F`;
> 2. `F_{Q'}` is capped at `i` iff `|Q'| >= |Q|`;
> 3. if `|Q'| >= |Q|` then `F_{Q'}` is nonregular, on the same active ground.

(`uc_tight_coordinate.md`, Section 10.  The proof of (3) uses that `C` is
nonempty, "in Frame D"; that is taken as an explicit hypothesis.)
`A = zeroSlice F i`, `B = oneSlice F i`, `C = edgeTrace F i`, `J = sliceUnion F i`,
`Q = zeroSlice F i \ edgeTrace F i`, `F_{Q'} = sectionEndpoint F i Q'`.
"Same slack" is stated as equality of `σ_k`, which contains "capped at `k`"
under the cap of `F`.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

set_option linter.unusedSectionVars false

variable {V : Type*} [DecidableEq V] [Fintype V]

/-! ## Finset plumbing

Small general-purpose lemmas used by the counting below; nothing here mentions
the union-closed vocabulary. -/

/-- Cardinality of a disjoint union (stated so as not to depend on the exact
Mathlib spelling of `card_union_of_disjoint`). -/
lemma card_union_disj {G H : Finset (Finset V)} (h : Disjoint G H) :
    (G ∪ H).card = G.card + H.card := by
  have h1 := Finset.card_union_add_card_inter G H
  rw [Finset.disjoint_iff_inter_eq_empty.mp h] at h1
  simpa using h1

/-- `filter` distributes over `∪`. -/
lemma filter_union_dist (G H : Finset (Finset V)) (p : Finset V → Prop) [DecidablePred p] :
    (G ∪ H).filter p = G.filter p ∪ H.filter p := by
  ext S; simp only [Finset.mem_filter, Finset.mem_union]; tauto

/-- `filter` distributes over `∩`. -/
lemma filter_inter_dist (G H : Finset (Finset V)) (p : Finset V → Prop) [DecidablePred p] :
    (G ∩ H).filter p = G.filter p ∩ H.filter p := by
  ext S; simp only [Finset.mem_filter, Finset.mem_inter]; tauto

/-- `filter` distributes over `\`. -/
lemma filter_sdiff_dist (G H : Finset (Finset V)) (p : Finset V → Prop) [DecidablePred p] :
    (G \ H).filter p = G.filter p \ H.filter p := by
  ext S; simp only [Finset.mem_filter, Finset.mem_sdiff]; tauto

/-- Filtering an image is the image of a filtered set (no injectivity needed). -/
lemma image_filter_comm (X : Finset (Finset V)) (f : Finset V → Finset V)
    (p : Finset V → Prop) [DecidablePred p] :
    (X.image f).filter p = (X.filter (fun a => p (f a))).image f := by
  ext b
  simp only [Finset.mem_filter, Finset.mem_image]
  constructor
  · rintro ⟨⟨a, ha, rfl⟩, hp⟩; exact ⟨a, ⟨ha, hp⟩, rfl⟩
  · rintro ⟨a, ⟨ha, hp⟩, rfl⟩; exact ⟨⟨a, ha, rfl⟩, hp⟩

/-! ## Degree plumbing -/

/-- Degrees are additive along a disjoint union. -/
lemma deg_union_of_disjoint {G H : Finset (Finset V)} (k : V) (h : Disjoint G H) :
    deg (G ∪ H) k = deg G k + deg H k := by
  unfold deg
  rw [filter_union_dist]
  exact card_union_disj (h.mono (Finset.filter_subset _ _) (Finset.filter_subset _ _))

/-- Inclusion–exclusion for degrees. -/
lemma deg_union_add_deg_inter (G H : Finset (Finset V)) (k : V) :
    deg (G ∪ H) k + deg (G ∩ H) k = deg G k + deg H k := by
  unfold deg
  rw [filter_union_dist, filter_inter_dist]
  exact Finset.card_union_add_card_inter _ _

/-- Degrees split along `G = (G \ H) ∪ H` for `H ⊆ G`. -/
lemma deg_sdiff_add {G H : Finset (Finset V)} (k : V) (h : H ⊆ G) :
    deg (G \ H) k + deg H k = deg G k := by
  unfold deg
  rw [filter_sdiff_dist]
  exact Finset.card_sdiff_add_card_eq_card (Finset.filter_subset_filter _ h)

/-- A family none of whose members contains `i` has degree `0` at `i`. -/
lemma deg_eq_zero_of_not_mem (X : Finset (Finset V)) (i : V) (hX : ∀ S ∈ X, i ∉ S) :
    deg X i = 0 := by
  unfold deg
  rw [Finset.filter_false_of_mem hX]
  exact Finset.card_empty

/-! ## The slices at a source -/

/-- Members of the zero slice avoid the source. -/
lemma not_mem_of_mem_zeroSlice {F : Finset (Finset V)} {i : V} {S : Finset V}
    (hS : S ∈ zeroSlice F i) : i ∉ S := (Finset.mem_filter.mp hS).2

/-- Members of the one slice avoid the source (they are `erase i` images). -/
lemma not_mem_of_mem_oneSlice {F : Finset (Finset V)} {i : V} {S : Finset V}
    (hS : S ∈ oneSlice F i) : i ∉ S := by
  simp only [oneSlice, Finset.mem_image, Finset.mem_filter] at hS
  obtain ⟨T, -, rfl⟩ := hS
  simp

/-- Members of `J = A ∪ B` avoid the source. -/
lemma not_mem_of_mem_sliceUnion {F : Finset (Finset V)} {i : V} {S : Finset V}
    (hS : S ∈ sliceUnion F i) : i ∉ S := by
  rcases Finset.mem_union.mp hS with h | h
  · exact not_mem_of_mem_zeroSlice h
  · exact not_mem_of_mem_oneSlice h

/-- `C = A ∩ B`: a trace `c` with `i ∉ c` lies in `B` iff `insert i c ∈ F`. -/
lemma edgeTrace_eq_inter (F : Finset (Finset V)) (i : V) :
    edgeTrace F i = zeroSlice F i ∩ oneSlice F i := by
  ext c
  simp only [edgeTrace, zeroSlice, oneSlice, Finset.mem_filter, Finset.mem_inter,
    Finset.mem_image]
  constructor
  · rintro ⟨hcF, hic, hins⟩
    exact ⟨⟨hcF, hic⟩, insert i c, ⟨hins, Finset.mem_insert_self _ _⟩, Finset.erase_insert hic⟩
  · rintro ⟨⟨hcF, hic⟩, T, ⟨hTF, hiT⟩, rfl⟩
    exact ⟨hcF, hic, by rwa [Finset.insert_erase hiT]⟩

lemma edgeTrace_subset_zeroSlice {F : Finset (Finset V)} {i : V} :
    edgeTrace F i ⊆ zeroSlice F i := by
  intro S hS
  rw [edgeTrace_eq_inter] at hS
  exact (Finset.mem_inter.mp hS).1

lemma edgeTrace_subset_oneSlice {F : Finset (Finset V)} {i : V} :
    edgeTrace F i ⊆ oneSlice F i := by
  intro S hS
  rw [edgeTrace_eq_inter] at hS
  exact (Finset.mem_inter.mp hS).2

lemma edgeTrace_subset_sliceUnion {F : Finset (Finset V)} {i : V} :
    edgeTrace F i ⊆ sliceUnion F i := fun _ hS =>
  Finset.mem_union_left _ (edgeTrace_subset_zeroSlice hS)

/-- `erase i` is injective on families of rows containing `i`. -/
lemma erase_injOn (i : V) (X : Finset (Finset V)) (hX : ∀ S ∈ X, i ∈ S) :
    Set.InjOn (fun S : Finset V => S.erase i) (↑X : Set (Finset V)) := by
  intro S hS T hT h
  have h' : S.erase i = T.erase i := h
  have h1 := hX S (Finset.mem_coe.mp hS)
  have h2 := hX T (Finset.mem_coe.mp hT)
  rw [← Finset.insert_erase h1, ← Finset.insert_erase h2, h']

/-- `insert i` is injective on families of rows avoiding `i`. -/
lemma insert_source_injOn (i : V) (X : Finset (Finset V)) (hX : ∀ S ∈ X, i ∉ S) :
    Set.InjOn (fun S : Finset V => insert i S) (↑X : Set (Finset V)) := by
  intro S hS T hT h
  have h' : insert i S = insert i T := h
  have h1 := hX S (Finset.mem_coe.mp hS)
  have h2 := hX T (Finset.mem_coe.mp hT)
  rw [← Finset.erase_insert h1, ← Finset.erase_insert h2, h']

/-- `|B| = #{S ∈ F : i ∈ S}`. -/
lemma oneSlice_card (F : Finset (Finset V)) (i : V) :
    (oneSlice F i).card = (F.filter (fun S => i ∈ S)).card := by
  unfold oneSlice
  exact Finset.card_image_of_injOn
    (erase_injOn i _ (fun S hS => (Finset.mem_filter.mp hS).2))

/-- `d_F(i) = |B|`. -/
lemma deg_source_eq (F : Finset (Finset V)) (i : V) : deg F i = (oneSlice F i).card := by
  unfold deg
  exact (oneSlice_card F i).symm

/-- `d_A(k) = #{S ∈ F : k ∈ S, i ∉ S}`. -/
lemma deg_zeroSlice (F : Finset (Finset V)) (i k : V) :
    deg (zeroSlice F i) k = (F.filter (fun S => k ∈ S ∧ i ∉ S)).card := by
  unfold deg zeroSlice
  congr 1
  ext S
  simp only [Finset.mem_filter]
  tauto

/-- `d_B(k) = #{S ∈ F : k ∈ S, i ∈ S}` for `k ≠ i`. -/
lemma deg_oneSlice (F : Finset (Finset V)) (i k : V) (hk : k ≠ i) :
    deg (oneSlice F i) k = (F.filter (fun S => k ∈ S ∧ i ∈ S)).card := by
  unfold deg oneSlice
  rw [image_filter_comm]
  rw [Finset.card_image_of_injOn (erase_injOn i _ (fun S hS =>
    (Finset.mem_filter.mp (Finset.filter_subset _ _ hS)).2))]
  congr 1
  ext S
  simp only [Finset.mem_filter, Finset.mem_erase]
  tauto

/-- `d_A(k) + d_B(k) = d_F(k)` for `k ≠ i`. -/
lemma deg_zeroSlice_add_deg_oneSlice (F : Finset (Finset V)) (i k : V) (hk : k ≠ i) :
    deg (zeroSlice F i) k + deg (oneSlice F i) k = deg F k := by
  rw [deg_zeroSlice, deg_oneSlice F i k hk]
  unfold deg
  have h1 : F.filter (fun S => k ∈ S ∧ i ∉ S)
      = (F.filter (fun S => k ∈ S)).filter (fun S => ¬ i ∈ S) := by
    ext S; simp only [Finset.mem_filter]; tauto
  have h2 : F.filter (fun S => k ∈ S ∧ i ∈ S)
      = (F.filter (fun S => k ∈ S)).filter (fun S => i ∈ S) := by
    ext S; simp only [Finset.mem_filter]; tauto
  rw [h1, h2, Nat.add_comm]
  exact Finset.card_filter_add_card_filter_not _

/-- `|A| + |B| = N`. -/
lemma card_zeroSlice_add_card_oneSlice (F : Finset (Finset V)) (i : V) :
    (zeroSlice F i).card + (oneSlice F i).card = F.card := by
  rw [oneSlice_card]
  unfold zeroSlice
  rw [Nat.add_comm]
  exact Finset.card_filter_add_card_filter_not _

/-- `|J| + |C| = |A| + |B|`. -/
lemma card_sliceUnion_add_card_edgeTrace (F : Finset (Finset V)) (i : V) :
    (sliceUnion F i).card + (edgeTrace F i).card
      = (zeroSlice F i).card + (oneSlice F i).card := by
  rw [edgeTrace_eq_inter]
  exact Finset.card_union_add_card_inter _ _

/-- `d_J(k) + d_C(k) = d_A(k) + d_B(k)`. -/
lemma deg_sliceUnion_add_deg_edgeTrace (F : Finset (Finset V)) (i k : V) :
    deg (sliceUnion F i) k + deg (edgeTrace F i) k
      = deg (zeroSlice F i) k + deg (oneSlice F i) k := by
  rw [edgeTrace_eq_inter]
  exact deg_union_add_deg_inter _ _ _

/-! ## The endpoint of a section -/

lemma section_subset_sliceUnion {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) : Q' ⊆ sliceUnion F i :=
  fun _ hS => (Finset.mem_sdiff.mp (hQ hS)).1

lemma section_disjoint_edgeTrace {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) : Disjoint (edgeTrace F i) Q' := by
  rw [Finset.disjoint_right]
  intro S hS
  exact (Finset.mem_sdiff.mp (hQ hS)).2

/-- The two parts of `F_{Q'}` are disjoint: the first avoids `i`, the second contains it. -/
lemma sectionEndpoint_disjoint_parts {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) :
    Disjoint (edgeTrace F i ∪ Q') ((sliceUnion F i \ Q').image (fun S => insert i S)) := by
  rw [Finset.disjoint_left]
  intro S hS hS2
  have hi : i ∉ S := by
    rcases Finset.mem_union.mp hS with h | h
    · exact not_mem_of_mem_zeroSlice (edgeTrace_subset_zeroSlice h)
    · exact not_mem_of_mem_sliceUnion (section_subset_sliceUnion hQ h)
  obtain ⟨T, -, hT⟩ := Finset.mem_image.mp hS2
  rw [← hT] at hi
  exact hi (Finset.mem_insert_self _ _)

/-- Every member of `C ∪ Q'` avoids `i`. -/
lemma not_mem_of_mem_first_part {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) : ∀ S ∈ edgeTrace F i ∪ Q', i ∉ S := by
  intro S hS
  rcases Finset.mem_union.mp hS with h | h
  · exact not_mem_of_mem_zeroSlice (edgeTrace_subset_zeroSlice h)
  · exact not_mem_of_mem_sliceUnion (section_subset_sliceUnion hQ h)

/-- `|F_{Q'}| = |C| + |J|`. -/
lemma sectionEndpoint_card_aux {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) :
    (sectionEndpoint F i Q').card = (edgeTrace F i).card + (sliceUnion F i).card := by
  unfold sectionEndpoint
  rw [card_union_disj (sectionEndpoint_disjoint_parts hQ),
    card_union_disj (section_disjoint_edgeTrace hQ),
    Finset.card_image_of_injOn (insert_source_injOn i _ (fun S hS =>
      not_mem_of_mem_sliceUnion (Finset.mem_sdiff.mp hS).1))]
  have h := Finset.card_sdiff_add_card_eq_card (section_subset_sliceUnion hQ)
  omega

/-- `|F_{Q'}| = N`. -/
lemma sectionEndpoint_card_eq {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) : (sectionEndpoint F i Q').card = F.card := by
  rw [sectionEndpoint_card_aux hQ]
  have h1 := card_sliceUnion_add_card_edgeTrace F i
  have h2 := card_zeroSlice_add_card_oneSlice F i
  omega

/-- Degree of an `insert i` image away from `i`. -/
lemma deg_image_insert_of_ne (X : Finset (Finset V)) (i k : V) (hk : k ≠ i)
    (hX : ∀ S ∈ X, i ∉ S) : deg (X.image (fun S => insert i S)) k = deg X k := by
  unfold deg
  rw [image_filter_comm,
    Finset.card_image_of_injOn (insert_source_injOn i _ (fun S hS =>
      hX S (Finset.filter_subset _ _ hS)))]
  congr 1
  ext S
  simp only [Finset.mem_filter, Finset.mem_insert, hk, false_or]

/-- Degree of an `insert i` image at `i`: every member contains `i`. -/
lemma deg_image_insert_at_source (X : Finset (Finset V)) (i : V) (hX : ∀ S ∈ X, i ∉ S) :
    deg (X.image (fun S => insert i S)) i = X.card := by
  unfold deg
  rw [image_filter_comm,
    Finset.card_image_of_injOn (insert_source_injOn i _ (fun S hS =>
      hX S (Finset.filter_subset _ _ hS)))]
  congr 1
  exact Finset.filter_true_of_mem (fun S _ => Finset.mem_insert_self i S)

/-- `d_{F_{Q'}}(k) = d_C(k) + d_J(k)` for `k ≠ i`. -/
lemma sectionEndpoint_deg_aux {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) (k : V) (hk : k ≠ i) :
    deg (sectionEndpoint F i Q') k = deg (edgeTrace F i) k + deg (sliceUnion F i) k := by
  unfold sectionEndpoint
  rw [deg_union_of_disjoint k (sectionEndpoint_disjoint_parts hQ),
    deg_union_of_disjoint k (section_disjoint_edgeTrace hQ),
    deg_image_insert_of_ne _ i k hk (fun S hS =>
      not_mem_of_mem_sliceUnion (Finset.mem_sdiff.mp hS).1)]
  have h := deg_sdiff_add (G := sliceUnion F i) (H := Q') k (section_subset_sliceUnion hQ)
  omega

/-- `d_{F_{Q'}}(k) = d_F(k)` for `k ≠ i`. -/
lemma sectionEndpoint_deg_eq {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) (k : V) (hk : k ≠ i) :
    deg (sectionEndpoint F i Q') k = deg F k := by
  rw [sectionEndpoint_deg_aux hQ k hk]
  have h1 := deg_sliceUnion_add_deg_edgeTrace F i k
  have h2 := deg_zeroSlice_add_deg_oneSlice F i k hk
  omega

/-- `d_{F_{Q'}}(i) = |J ∖ Q'|`. -/
lemma sectionEndpoint_deg_source {F : Finset (Finset V)} {i : V} {Q' : Finset (Finset V)}
    (hQ : Q' ⊆ sliceUnion F i \ edgeTrace F i) :
    deg (sectionEndpoint F i Q') i = (sliceUnion F i \ Q').card := by
  have hz : deg (edgeTrace F i ∪ Q') i = 0 :=
    deg_eq_zero_of_not_mem _ i (not_mem_of_mem_first_part hQ)
  unfold sectionEndpoint
  rw [deg_union_of_disjoint i (sectionEndpoint_disjoint_parts hQ), hz,
    deg_image_insert_at_source _ i (fun S hS =>
      not_mem_of_mem_sliceUnion (Finset.mem_sdiff.mp hS).1)]
  exact Nat.zero_add _

/-! ## Theorem 10.1 -/

/-- Theorem 10.1 (1): for every legal section `Q'` and every `k ≠ i`,
`σ_k(F_{Q'}) = σ_k(F)` (the same slack; capped at `k` when `F` is). -/
theorem section_sigma_outside (F : Finset (Finset V)) (i : V) (Q' : Finset (Finset V))
    (hQ : LegalSection F i Q') (k : V) (hk : k ≠ i) :
    sigma (sectionEndpoint F i Q') k = sigma F k := by
  have hQsub := hQ.1
  unfold sigma
  rw [sectionEndpoint_card_eq hQsub, sectionEndpoint_deg_eq hQsub k hk]

#print axioms section_sigma_outside

/-- Theorem 10.1 (1), cap form: if `F` is capped then `F_{Q'}` is capped at every `k ≠ i`. -/
theorem section_capped_outside (F : Finset (Finset V)) (i : V) (Q' : Finset (Finset V))
    (hcap : Capped F) (hQ : LegalSection F i Q') (k : V) (hk : k ≠ i) :
    0 ≤ sigma (sectionEndpoint F i Q') k := by
  rw [section_sigma_outside F i Q' hQ k hk]
  exact hcap k

#print axioms section_capped_outside

/-- Theorem 10.1 (2): for tight `i`, `F_{Q'}` is capped at `i` iff `|Q'| ≥ |Q|`. -/
theorem section_capped_at_source_iff (F : Finset (Finset V)) (i : V) (Q' : Finset (Finset V))
    (hi : Tight F i) (hQ : LegalSection F i Q') :
    0 ≤ sigma (sectionEndpoint F i Q') i ↔
      (zeroSlice F i \ edgeTrace F i).card ≤ Q'.card := by
  have hQsub := hQ.1
  have hti : (F.card : ℤ) - 2 * (deg F i : ℤ) = 0 := hi
  have hdi : deg F i = (oneSlice F i).card := deg_source_eq F i
  have hab := card_zeroSlice_add_card_oneSlice F i
  have hju := card_sliceUnion_add_card_edgeTrace F i
  have hjq := Finset.card_sdiff_add_card_eq_card (section_subset_sliceUnion hQsub)
  have hcg := Finset.card_sdiff_add_card_eq_card
    (edgeTrace_subset_zeroSlice (F := F) (i := i))
  unfold sigma
  rw [sectionEndpoint_card_eq hQsub, sectionEndpoint_deg_source hQsub]
  omega

#print axioms section_capped_at_source_iff

/-- Theorem 10.1 (3): for tight `i`, `F` nonregular and `C ≠ ∅`, if `|Q'| ≥ |Q|`
then `F_{Q'}` is nonregular, on the same active ground. -/
theorem section_nonregular (F : Finset (Finset V)) (i : V) (Q' : Finset (Finset V))
    (hi : Tight F i) (hnr : ¬ Regular F) (hC : (edgeTrace F i).Nonempty)
    (hQ : LegalSection F i Q')
    (hsize : (zeroSlice F i \ edgeTrace F i).card ≤ Q'.card) :
    ¬ Regular (sectionEndpoint F i Q') ∧ ground (sectionEndpoint F i Q') = ground F := by
  have hQsub := hQ.1
  -- `i` is active on both sides, because `C` is nonempty.
  have hCpos : 0 < (edgeTrace F i).card := Finset.card_pos.mpr hC
  have hFi : Active F i := by
    have h1 : (edgeTrace F i).card ≤ (oneSlice F i).card :=
      Finset.card_le_card edgeTrace_subset_oneSlice
    have h3 : deg F i = (oneSlice F i).card := deg_source_eq F i
    unfold Active
    omega
  have hEi : Active (sectionEndpoint F i Q') i := by
    have h0 : deg (sectionEndpoint F i Q') i = (sliceUnion F i \ Q').card :=
      sectionEndpoint_deg_source hQsub
    have h1 : edgeTrace F i ⊆ sliceUnion F i \ Q' := by
      intro S hS
      refine Finset.mem_sdiff.mpr ⟨edgeTrace_subset_sliceUnion hS, ?_⟩
      intro hSQ
      exact (Finset.mem_sdiff.mp (hQsub hSQ)).2 hS
    have h3 := Finset.card_le_card h1
    unfold Active
    omega
  -- the active grounds agree coordinatewise
  have hground : ground (sectionEndpoint F i Q') = ground F := by
    unfold ground
    ext k
    simp only [Finset.mem_filter, Finset.mem_univ, true_and]
    by_cases hk : k = i
    · subst hk
      exact ⟨fun _ => hFi, fun _ => hEi⟩
    · unfold Active
      rw [sectionEndpoint_deg_eq hQsub k hk]
  refine ⟨?_, hground⟩
  -- the nonregular coordinate of `F` is not `i`, and its slack is unchanged
  obtain ⟨j, hja, hjs⟩ : ∃ j : V, Active F j ∧ sigma F j ≠ 0 := by
    by_contra hcon
    exact hnr (fun j hj => by
      by_contra hne
      exact hcon ⟨j, hj, hne⟩)
  have hji : j ≠ i := by
    rintro rfl
    exact hjs hi
  intro hreg
  have hactive : Active (sectionEndpoint F i Q') j := by
    unfold Active
    rw [sectionEndpoint_deg_eq hQsub j hji]
    exact hja
  have hzero := hreg j hactive
  rw [section_sigma_outside F i Q' hQ j hji] at hzero
  exact hjs hzero

#print axioms section_nonregular

end Problems.Combinatorics.uc_mainline
