import Mathlib
import Problems.Combinatorics.uc_mainline.Defs
import Problems.Combinatorics.uc_mainline.T_projection_accounts

/-!
# Theorem A of `uc_minimal_deficit_pair.md` (the witness number is a difference of deficits)

> **Theorem A (the witness number is a difference of deficits).** For every
> `k ≠ x`,
>
>     D(x → k) = |C_x| − 2 d_{C_x}(k) − σ_k(F) = σ_k(C_x) − σ_k(F),        (10)
>
> `π_x(F)` is capped at `k` iff `D(x → k) ≤ 0`, and
>
>     π_x(F) capped   ⟺  σ_k(C_x) ≤ σ_k(F)  for every k ≠ x,
>     π_x(F) regular  ⟺  σ_k(C_x) = σ_k(F)  for every k ≠ x.

(`uc_minimal_deficit_pair.md`, Section 5b.)  `D(x → k)` is the witness number
of Lemma 2.3 (7), `|X ∩ Y| − |Z ∩ W| − σ_k(F)`, which is `witnessD F x k`.
The regularity clause is read in the article's setting, where every
coordinate of `V` is active in `F` (Section 1), and is stated with that
hypothesis.
-/

namespace Problems.Combinatorics.uc_mainline

open Finset

variable {V : Type*} [DecidableEq V] [Fintype V]

-- As in `T_projection_accounts.lean`, nothing here needs `[Fintype V]`; the instance is kept
-- in the signatures so that the whole main line shares one context.
set_option linter.unusedSectionVars false

/-! ## Removing a pair of coordinates -/

/-- `S ∖ {x, k}` is the double erasure. -/
theorem sdiff_pair_eq_erase_erase (S : Finset V) (x k : V) :
    S \ ({x, k} : Finset V) = (S.erase x).erase k := by
  ext a
  simp only [Finset.mem_sdiff, Finset.mem_erase, Finset.mem_insert, Finset.mem_singleton, not_or]
  tauto

/-! ## The four patterns at `(x, k)` -/

/-- The pattern `∅`: `S ∩ {x, k} = ∅` iff `S` avoids both coordinates. -/
theorem inter_pair_eq_empty_iff (S : Finset V) (x k : V) :
    S ∩ ({x, k} : Finset V) = ∅ ↔ x ∉ S ∧ k ∉ S := by
  constructor
  · intro h
    constructor
    · intro hx
      have hx' : x ∈ S ∩ ({x, k} : Finset V) :=
        Finset.mem_inter.mpr ⟨hx, Finset.mem_insert_self x {k}⟩
      rw [h] at hx'
      exact absurd hx' (Finset.notMem_empty x)
    · intro hk
      have hk' : k ∈ S ∩ ({x, k} : Finset V) :=
        Finset.mem_inter.mpr ⟨hk, Finset.mem_insert_of_mem (Finset.mem_singleton_self k)⟩
      rw [h] at hk'
      exact absurd hk' (Finset.notMem_empty k)
  · rintro ⟨hx, hk⟩
    rw [Finset.eq_empty_iff_forall_notMem]
    intro a ha
    rw [Finset.mem_inter] at ha
    rcases Finset.mem_insert.mp ha.2 with rfl | ha3
    · exact hx ha.1
    · rw [Finset.mem_singleton] at ha3
      subst ha3
      exact hk ha.1

/-- The pattern `{x}`: `S ∩ {x, k} = {x}` iff `S` contains `x` and avoids `k`. -/
theorem inter_pair_eq_left_iff (S : Finset V) (x k : V) (hxk : x ≠ k) :
    S ∩ ({x, k} : Finset V) = {x} ↔ x ∈ S ∧ k ∉ S := by
  constructor
  · intro h
    have hx : x ∈ S := by
      have hx' : x ∈ S ∩ ({x, k} : Finset V) := by
        rw [h]; exact Finset.mem_singleton_self x
      exact (Finset.mem_inter.mp hx').1
    refine ⟨hx, fun hk => ?_⟩
    have hk' : k ∈ S ∩ ({x, k} : Finset V) :=
      Finset.mem_inter.mpr ⟨hk, Finset.mem_insert_of_mem (Finset.mem_singleton_self k)⟩
    rw [h, Finset.mem_singleton] at hk'
    exact hxk hk'.symm
  · rintro ⟨hx, hk⟩
    ext a
    simp only [Finset.mem_inter, Finset.mem_insert, Finset.mem_singleton]
    constructor
    · rintro ⟨haS, (rfl | rfl)⟩
      · rfl
      · exact absurd haS hk
    · rintro rfl
      exact ⟨hx, Or.inl rfl⟩

/-- The pattern `{k}`: `S ∩ {x, k} = {k}` iff `S` avoids `x` and contains `k`. -/
theorem inter_pair_eq_right_iff (S : Finset V) (x k : V) (hxk : x ≠ k) :
    S ∩ ({x, k} : Finset V) = {k} ↔ x ∉ S ∧ k ∈ S := by
  constructor
  · intro h
    have hk : k ∈ S := by
      have hk' : k ∈ S ∩ ({x, k} : Finset V) := by
        rw [h]; exact Finset.mem_singleton_self k
      exact (Finset.mem_inter.mp hk').1
    refine ⟨fun hx => ?_, hk⟩
    have hx' : x ∈ S ∩ ({x, k} : Finset V) :=
      Finset.mem_inter.mpr ⟨hx, Finset.mem_insert_self x {k}⟩
    rw [h, Finset.mem_singleton] at hx'
    exact hxk hx'
  · rintro ⟨hx, hk⟩
    ext a
    simp only [Finset.mem_inter, Finset.mem_insert, Finset.mem_singleton]
    constructor
    · rintro ⟨haS, (rfl | rfl)⟩
      · exact absurd haS hx
      · rfl
    · rintro rfl
      exact ⟨hk, Or.inr rfl⟩

/-- The pattern `{x, k}`: `S ∩ {x, k} = {x, k}` iff `S` contains both coordinates. -/
theorem inter_pair_eq_pair_iff (S : Finset V) (x k : V) :
    S ∩ ({x, k} : Finset V) = {x, k} ↔ x ∈ S ∧ k ∈ S := by
  constructor
  · intro h
    constructor
    · have hx' : x ∈ S ∩ ({x, k} : Finset V) := by
        rw [h]; exact Finset.mem_insert_self x {k}
      exact (Finset.mem_inter.mp hx').1
    · have hk' : k ∈ S ∩ ({x, k} : Finset V) := by
        rw [h]; exact Finset.mem_insert_of_mem (Finset.mem_singleton_self k)
      exact (Finset.mem_inter.mp hk').1
  · rintro ⟨hx, hk⟩
    ext a
    simp only [Finset.mem_inter, Finset.mem_insert, Finset.mem_singleton]
    constructor
    · rintro ⟨-, h⟩
      exact h
    · rintro (rfl | rfl)
      · exact ⟨hx, Or.inl rfl⟩
      · exact ⟨hk, Or.inr rfl⟩

/-! ## Membership in the four pattern classes at `(x, k)` -/

/-- Membership in `X`: the rows avoiding both coordinates are their own traces. -/
theorem mem_patX {F : Finset (Finset V)} {x k : V} {c : Finset V} :
    c ∈ patX F x k ↔ c ∈ F ∧ x ∉ c ∧ k ∉ c := by
  simp only [patX, patternClass, Finset.mem_image, Finset.mem_filter]
  constructor
  · rintro ⟨S, ⟨hS, hint⟩, rfl⟩
    obtain ⟨hx, hk⟩ := (inter_pair_eq_empty_iff S x k).mp hint
    have hSS : S \ ({x, k} : Finset V) = S := by
      rw [sdiff_pair_eq_erase_erase, Finset.erase_eq_of_notMem hx,
        Finset.erase_eq_of_notMem hk]
    rw [hSS]
    exact ⟨hS, hx, hk⟩
  · rintro ⟨hc, hx, hk⟩
    refine ⟨c, ⟨hc, (inter_pair_eq_empty_iff c x k).mpr ⟨hx, hk⟩⟩, ?_⟩
    rw [sdiff_pair_eq_erase_erase, Finset.erase_eq_of_notMem hx, Finset.erase_eq_of_notMem hk]

/-- Membership in `Y`: the traces of the rows containing `x` and avoiding `k`. -/
theorem mem_patY {F : Finset (Finset V)} {x k : V} {c : Finset V} (hxk : x ≠ k) :
    c ∈ patY F x k ↔ x ∉ c ∧ k ∉ c ∧ insert x c ∈ F := by
  simp only [patY, patternClass, Finset.mem_image, Finset.mem_filter]
  constructor
  · rintro ⟨S, ⟨hS, hint⟩, rfl⟩
    obtain ⟨hx, hk⟩ := (inter_pair_eq_left_iff S x k hxk).mp hint
    have hSS : S \ ({x, k} : Finset V) = S.erase x := by
      rw [sdiff_pair_eq_erase_erase,
        Finset.erase_eq_of_notMem (fun h => hk (Finset.mem_of_mem_erase h))]
    rw [hSS, Finset.insert_erase hx]
    exact ⟨Finset.notMem_erase x S, fun h => hk (Finset.mem_of_mem_erase h), hS⟩
  · rintro ⟨hx, hk, hins⟩
    refine ⟨insert x c, ⟨hins, (inter_pair_eq_left_iff _ x k hxk).mpr
      ⟨Finset.mem_insert_self x c, ?_⟩⟩, ?_⟩
    · intro h
      rcases Finset.mem_insert.mp h with rfl | h'
      · exact hxk rfl
      · exact hk h'
    · rw [sdiff_pair_eq_erase_erase, Finset.erase_insert hx, Finset.erase_eq_of_notMem hk]

/-- Membership in `Z`: the traces of the rows containing `k` and avoiding `x`. -/
theorem mem_patZ {F : Finset (Finset V)} {x k : V} {c : Finset V} (hxk : x ≠ k) :
    c ∈ patZ F x k ↔ x ∉ c ∧ k ∉ c ∧ insert k c ∈ F := by
  simp only [patZ, patternClass, Finset.mem_image, Finset.mem_filter]
  constructor
  · rintro ⟨S, ⟨hS, hint⟩, rfl⟩
    obtain ⟨hx, hk⟩ := (inter_pair_eq_right_iff S x k hxk).mp hint
    have hSS : S \ ({x, k} : Finset V) = S.erase k := by
      rw [sdiff_pair_eq_erase_erase, Finset.erase_eq_of_notMem hx]
    rw [hSS, Finset.insert_erase hk]
    exact ⟨fun h => hx (Finset.mem_of_mem_erase h), Finset.notMem_erase k S, hS⟩
  · rintro ⟨hx, hk, hins⟩
    have hxins : x ∉ insert k c := by
      intro h
      rcases Finset.mem_insert.mp h with rfl | h'
      · exact hxk rfl
      · exact hx h'
    refine ⟨insert k c, ⟨hins, (inter_pair_eq_right_iff _ x k hxk).mpr
      ⟨hxins, Finset.mem_insert_self k c⟩⟩, ?_⟩
    rw [sdiff_pair_eq_erase_erase, Finset.erase_eq_of_notMem hxins, Finset.erase_insert hk]

/-- Membership in `W`: the traces of the rows containing both coordinates. -/
theorem mem_patW {F : Finset (Finset V)} {x k : V} {c : Finset V} (hxk : x ≠ k) :
    c ∈ patW F x k ↔ x ∉ c ∧ k ∉ c ∧ insert x (insert k c) ∈ F := by
  simp only [patW, patternClass, Finset.mem_image, Finset.mem_filter]
  constructor
  · rintro ⟨S, ⟨hS, hint⟩, rfl⟩
    obtain ⟨hx, hk⟩ := (inter_pair_eq_pair_iff S x k).mp hint
    rw [sdiff_pair_eq_erase_erase,
      Finset.insert_erase (Finset.mem_erase.mpr ⟨fun h => hxk h.symm, hk⟩),
      Finset.insert_erase hx]
    exact ⟨fun h => (Finset.notMem_erase x S) (Finset.mem_of_mem_erase h),
      Finset.notMem_erase k (S.erase x), hS⟩
  · rintro ⟨hx, hk, hins⟩
    have hxins : x ∉ insert k c := by
      intro h
      rcases Finset.mem_insert.mp h with rfl | h'
      · exact hxk rfl
      · exact hx h'
    refine ⟨insert x (insert k c), ⟨hins, (inter_pair_eq_pair_iff _ x k).mpr
      ⟨Finset.mem_insert_self x _, Finset.mem_insert_of_mem (Finset.mem_insert_self k c)⟩⟩, ?_⟩
    rw [sdiff_pair_eq_erase_erase, Finset.erase_insert hxins, Finset.erase_insert hk]

/-! ## The two intersections are the `k`-halves of the edge traces -/

/-- `X ∩ Y` is the family of `x`-edges avoiding `k`. -/
theorem patX_inter_patY_eq (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) :
    patX F x k ∩ patY F x k = (edgeTrace F x).filter (fun c => k ∉ c) := by
  ext c
  rw [Finset.mem_inter, Finset.mem_filter, mem_patX, mem_patY hxk, mem_edgeTrace]
  tauto

/-- `Z ∩ W` is carried onto the family of `x`-edges containing `k` by `c ↦ c + k`. -/
theorem patZ_inter_patW_image (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) :
    (patZ F x k ∩ patW F x k).image (fun c => insert k c)
      = (edgeTrace F x).filter (fun c => k ∈ c) := by
  ext d
  simp only [Finset.mem_image, Finset.mem_inter, Finset.mem_filter, mem_patZ hxk, mem_patW hxk,
    mem_edgeTrace]
  constructor
  · rintro ⟨c, ⟨⟨hxc, hkc, hZ⟩, ⟨-, -, hW⟩⟩, rfl⟩
    refine ⟨⟨hZ, ?_, hW⟩, Finset.mem_insert_self k c⟩
    intro h
    rcases Finset.mem_insert.mp h with rfl | h'
    · exact hxk rfl
    · exact hxc h'
  · rintro ⟨⟨hd, hxd, hins⟩, hkd⟩
    have hxe : x ∉ d.erase k := fun h => hxd (Finset.mem_of_mem_erase h)
    have hke : k ∉ d.erase k := Finset.notMem_erase k d
    have hid : insert k (d.erase k) = d := Finset.insert_erase hkd
    exact ⟨d.erase k, ⟨⟨hxe, hke, by rw [hid]; exact hd⟩,
      ⟨hxe, hke, by rw [hid]; exact hins⟩⟩, hid⟩

/-- `|Z ∩ W|` is the number of `x`-edges containing `k`. -/
theorem card_patZ_inter_patW (F : Finset (Finset V)) (x k : V) (hxk : x ≠ k) :
    (patZ F x k ∩ patW F x k).card = ((edgeTrace F x).filter (fun c => k ∈ c)).card := by
  rw [← patZ_inter_patW_image F x k hxk]
  refine (Finset.card_image_of_injOn ?_).symm
  intro a ha b hb hab
  have hka : k ∉ a := ((mem_patZ hxk).mp (Finset.mem_inter.mp (Finset.mem_coe.mp ha)).1).2.1
  have hkb : k ∉ b := ((mem_patZ hxk).mp (Finset.mem_inter.mp (Finset.mem_coe.mp hb)).1).2.1
  have hab' : insert k a = insert k b := hab
  have h : (insert k a).erase k = (insert k b).erase k := by rw [hab']
  rwa [Finset.erase_insert hka, Finset.erase_insert hkb] at h

/-! ## The projection's deficit splits off the edge-trace deficit -/

/-- `d_{π_x(F)}(x) = 0`: no member of the projection contains `x`. -/
theorem proj_deg_self (F : Finset (Finset V)) (x : V) : deg (proj F x) x = 0 := by
  rw [deg_eq_card_filter, Finset.card_eq_zero, Finset.filter_eq_empty_iff]
  intro c hc
  obtain ⟨S, -, rfl⟩ := mem_proj.mp hc
  exact Finset.notMem_erase x S

/-- The additive form of Theorem A: `σ_k(π_x(F)) + σ_k(C_x) = σ_k(F)` for `k ≠ x`. -/
theorem proj_sigma_add (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    sigma (proj F x) k + sigma (edgeTrace F x) k = sigma F k := by
  have hcard := proj_card_add_edgeTrace_card F x
  have hdeg := proj_deg_add_edgeTrace_deg F x k hk
  simp only [sigma]
  omega

/-! ## Theorem A -/

/-- Theorem A, identity (10): `D(x → k) = σ_k(C_x) − σ_k(F)` for `k ≠ x`. -/
theorem witnessD_eq_sigma_sub (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    witnessD F x k = sigma (edgeTrace F x) k - sigma F k := by
  have hXY : (patX F x k ∩ patY F x k).card
      = ((edgeTrace F x).filter (fun c => k ∉ c)).card := by
    rw [patX_inter_patY_eq F x k hk.symm]
  have hZW := card_patZ_inter_patW F x k hk.symm
  have hsplit : ((edgeTrace F x).filter (fun c => k ∈ c)).card
      + ((edgeTrace F x).filter (fun c => k ∉ c)).card = (edgeTrace F x).card :=
    Finset.card_filter_add_card_filter_not (s := edgeTrace F x) (fun c => k ∈ c)
  have hdeg : deg (edgeTrace F x) k = ((edgeTrace F x).filter (fun c => k ∈ c)).card := rfl
  simp only [witnessD, sigma, hXY, hZW, hdeg]
  omega

/-- Theorem A, pointwise cap: `π_x(F)` is capped at `k ≠ x` iff `D(x → k) ≤ 0`. -/
theorem proj_capped_at_iff (F : Finset (Finset V)) (x k : V) (hk : k ≠ x) :
    0 ≤ sigma (proj F x) k ↔ witnessD F x k ≤ 0 := by
  have h1 := proj_sigma_add F x k hk
  have h2 := witnessD_eq_sigma_sub F x k hk
  omega

/-- Theorem A, cap clause: `π_x(F)` is capped iff `σ_k(C_x) ≤ σ_k(F)` for every `k ≠ x`. -/
theorem proj_capped_iff (F : Finset (Finset V)) (x : V) :
    Capped (proj F x) ↔ ∀ k, k ≠ x → sigma (edgeTrace F x) k ≤ sigma F k := by
  constructor
  · intro h k hk
    have h1 := proj_sigma_add F x k hk
    have h2 := h k
    omega
  · intro h j
    by_cases hj : j = x
    · rw [hj]
      have h0 := proj_deg_self F x
      simp only [sigma]
      omega
    · have h1 := proj_sigma_add F x j hj
      have h2 := h j hj
      omega

/-- Theorem A, regularity clause (every coordinate active in `F`):
`π_x(F)` is regular iff `σ_k(C_x) = σ_k(F)` for every `k ≠ x`. -/
theorem proj_regular_iff (F : Finset (Finset V)) (x : V) (hact : ∀ j : V, Active F j) :
    Regular (proj F x) ↔ ∀ k, k ≠ x → sigma (edgeTrace F x) k = sigma F k := by
  constructor
  · intro h k hk
    have h1 := proj_sigma_add F x k hk
    have h2 := h k (proj_active F x k hk (hact k))
    omega
  · intro h j hj
    by_cases hjx : j = x
    · exfalso
      rw [hjx] at hj
      have h0 := proj_deg_self F x
      simp only [Active] at hj
      omega
    · have h1 := proj_sigma_add F x j hjx
      have h2 := h j hjx
      omega

#print axioms witnessD_eq_sigma_sub
#print axioms proj_capped_at_iff
#print axioms proj_capped_iff
#print axioms proj_regular_iff

end Problems.Combinatorics.uc_mainline
