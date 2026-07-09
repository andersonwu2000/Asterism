import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.DisjointOrbit
import Library.Geometry.BanachTarski.FixedFreeAction
import Library.Geometry.BanachTarski.HilbertHotel
import Library.Geometry.BanachTarski.OrbitSection
import Library.Geometry.BanachTarski.SO3Embedding
import Library.Geometry.BanachTarski.SphereDecompPieces
import Library.Geometry.BanachTarski.TowerLemmas

open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.DisjointOrbit
open Library.Geometry.BanachTarski.FixedFreeAction
open Library.Geometry.BanachTarski.HilbertHotel
open Library.Geometry.BanachTarski.OrbitSection
open Library.Geometry.BanachTarski.SO3Embedding
open Library.Geometry.BanachTarski.SphereDecompPieces
open Library.Geometry.BanachTarski.TowerLemmas

namespace Library.Geometry.BanachTarski.SphereDecomp

theorem paradoxical_transfer_along_equidecomp
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (hsrc : h.source = A) (htgt : h.target = B)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧ f.target = B ∧ g.target = B) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)), Disjoint f.source g.source ∧
        f.source ∪ g.source = A ∧ f.target = A ∧ g.target = A  := by
  obtain ⟨f, g, hdisj, hunion, hftgt, hgtgt⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  have hfs : f.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_left
  have hgs : g.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_right
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), ?_, ?_, ?_, ?_⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target h f hft hfs]; exact hsrc
  · rw [transfer_target h g hgt hgs]; exact hsrc

/-- For a piecewise isometry `f` that equals `ρ` on `T` and the identity off `T`, with `ρ 0 = 0`,
produce an `IsDecompOn` finset `{ρ, 1}` for `f` over any set `A`, with every element fixing 0.
This is the key origin-fixing bookkeeping lemma for the Hilbert-hotel shift. -/
theorem is_decomp_hilbert_origin_fixing (A T : Set E) (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S ∧ ∀ s ∈ S, s 0 = 0 := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{ρ, 1}, ?_, ?_⟩
  · intro a _
    by_cases hT : a ∈ T
    · exact ⟨ρ, Finset.mem_insert_self ρ {1}, hf a hT⟩
    · exact ⟨1, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)),
        by rw [hf' a hT]; rfl⟩
  · intro s hs
    simp only [Finset.mem_insert, Finset.mem_singleton] at hs
    rcases hs with rfl | rfl
    · exact hρ0
    · rfl


set_option maxHeartbeats 1000000 in
-- The norm computation on `EuclideanSpace ℝ (Fin 3)` exceeds the default whnf budget.
/-- The orbit tower $\bigcup_{n \in \mathbb{N}} \rho^n(D)$ of an origin-fixing isometry `ρ` is
contained in `Metric.sphere 0 1`, provided `D ⊆ Metric.sphere 0 1`. Since `ρ` fixes the origin,
$\|\rho^n(d)\| = \|d\| = 1$ for every $d \in D$ (by induction on `n`). -/
theorem hotel_subset_sphere (D : Set E) (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0)
    (hDs : D ⊆ Metric.sphere (0 : E) 1) :
    (⋃ n : ℕ, (ρ ^ n) '' D) ⊆ Metric.sphere (0 : E) 1 := by
  have hnorm : ∀ (g : E ≃ᵢ E), g 0 = 0 → ∀ z, ‖g z‖ = ‖z‖ := by
    intro g hg z
    calc ‖g z‖ = dist (g z) 0 := (dist_zero_right _).symm
      _ = dist (g z) (g 0) := by rw [hg]
      _ = dist z 0 := g.isometry.dist_eq z 0
      _ = ‖z‖ := dist_zero_right _
  have hfix : ∀ n : ℕ, (ρ ^ n) 0 = 0 := by
    intro n
    induction n with
    | zero => simp
    | succ k ih => rw [pow_succ]; change (ρ ^ k) (ρ 0) = 0; rw [hρ0, ih]
  intro x hx
  simp only [Set.mem_iUnion, Set.mem_image] at hx
  obtain ⟨n, d, hd, rfl⟩ := hx
  rw [Metric.mem_sphere, dist_zero_right, hnorm (ρ ^ n) (hfix n) d]
  have := hDs hd
  rw [Metric.mem_sphere, dist_zero_right] at this
  exact this


/-- Hilbert-hotel absorption on the sphere: constructs an equidecomposition
`h : S² ≃ S² \ D` for any countable `D ⊆ S²` with `0 ∉ D`, together with origin-fixing
realizing finsets `Sh`, `Sh'` for `h` and `h.symm`. The shift is performed by an
origin-fixing rotation `ρ` that pushes the orbit tower `T = ⋃ ρⁿ(D)` up by one step. -/
theorem sphere_hilbert_hotel_absorb_origin_fixing
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D) :
    ∃ (h : Equidecomp E (E ≃ᵢ E)) (Sh Sh' : Finset (E ≃ᵢ E)),
      h.source = Metric.sphere (0 : E) 1 ∧
      h.target = Metric.sphere (0 : E) 1 \ D ∧
      Equidecomp.IsDecompOn h.toFun h.source Sh ∧
      Equidecomp.IsDecompOn h.symm.toFun h.symm.source Sh' ∧
      (∀ s ∈ Sh, s 0 = 0) ∧ (∀ s ∈ Sh', s 0 = 0) := by
  classical
  obtain ⟨ρ, hρ0, hdisj⟩ := exists_rotation_pairwise_disjoint_orbit_off_origin D hDc hD0
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hTdef
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hDT : D ⊆ T := fun x hx => Set.mem_iUnion.mpr ⟨0, by simpa using hx⟩
  have hTA : T ⊆ Metric.sphere (0 : E) 1 := hotel_subset_sphere D ρ hρ0 hDs
  have hms := map_source_hilbert (Metric.sphere (0 : E) 1) D T ρ f hf hf' hDT hTA hshift
  have hmt := map_target_hilbert (Metric.sphere (0 : E) 1) D T ρ g hg hg' hDT hTA hshift
  have hli := left_inv_hilbert (Metric.sphere (0 : E) 1) D T ρ f g hf hf' hg hg' hshift
  have hri := right_inv_hilbert (Metric.sphere (0 : E) 1) D T ρ f g hf hf' hg hg' hshift
  obtain ⟨Sh, hSh, hSh0⟩ :=
    is_decomp_hilbert_origin_fixing (Metric.sphere (0 : E) 1) T ρ hρ0 f hf hf'
  have hρ0' : ρ.symm 0 = 0 := by
    have := ρ.symm_apply_apply 0; rwa [hρ0] at this
  obtain ⟨Sh', hSh', hSh'0⟩ :=
    is_decomp_hilbert_origin_fixing (Metric.sphere (0 : E) 1 \ D) T ρ.symm hρ0' g hg hg'
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g (Metric.sphere (0 : E) 1)
      (Metric.sphere (0 : E) 1 \ D) hms hmt hli hri) ⟨Sh, hSh⟩, Sh, Sh', rfl, rfl,
    hSh, hSh', hSh0, hSh'0⟩


/-- Given two origin-fixing equidecompositions `e₁`, `e₂` with realizing finsets `S₁`, `S₂`,
produce an origin-fixing finset for `e₁.trans e₂`: the finset `Finset.image₂ (· * ·) S₂ S₁`
of pairwise products. The `IsDecompOn` property uses `mul_smul`; origin-fixing follows from
$(g_2 \cdot g_1)(0) = g_2(g_1(0)) = g_2(0) = 0$. -/
theorem decomp_trans_origin_fixing
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (S₁ S₂ : Finset (E ≃ᵢ E))
    (hd₁ : Equidecomp.IsDecompOn e₁.toFun e₁.source S₁)
    (hd₂ : Equidecomp.IsDecompOn e₂.toFun e₂.source S₂)
    (h0₁ : ∀ s ∈ S₁, s 0 = 0) (h0₂ : ∀ s ∈ S₂, s 0 = 0) :
    ∃ S : Finset (E ≃ᵢ E),
      Equidecomp.IsDecompOn (e₁.trans e₂).toFun (e₁.trans e₂).source S ∧
      (∀ s ∈ S, s 0 = 0) := by
  classical
  refine ⟨Finset.image₂ (· * ·) S₂ S₁, ?_, ?_⟩
  · intro a ha
    rw [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source] at ha
    obtain ⟨ha1, ha2⟩ := ha
    obtain ⟨g₁, hg₁, hfa⟩ := hd₁ a ha1
    obtain ⟨g₂, hg₂, hfb⟩ := hd₂ (e₁.toFun a) ha2
    refine ⟨g₂ * g₁, Finset.mem_image₂_of_mem hg₂ hg₁, ?_⟩
    change e₂.toFun (e₁.toFun a) = (g₂ * g₁) • a
    rw [hfb, hfa, mul_smul]
  · intro s hs
    obtain ⟨g₂, hg₂, g₁, hg₁, rfl⟩ := Finset.mem_image₂.mp hs
    calc (g₂ * g₁) 0 = g₂ (g₁ 0) := rfl
      _ = g₂ 0 := by rw [h0₁ g₁ hg₁]
      _ = 0 := h0₂ g₂ hg₂


/-- Transfer a paradoxical equidecomposition with origin-fixing data from `B` to `A` along `h`.
Given `h : A ≃ B` (with origin-fixing decomp sets `Sh`, `Sh'`) and a `B`-paradox with
origin-fixing finsets `Sf`, `Sg`, constructs the conjugated `A`-paradox
`h.trans (f.trans h.symm)`, `h.trans (g.trans h.symm)` with composite origin-fixing finsets
(built by composing the per-factor finsets via `decomp_trans_origin_fixing`). -/
theorem paradoxical_transfer_along_equidecomp_origin_fixing
    (A B : Set E) (h : Equidecomp E (E ≃ᵢ E)) (Sh Sh' : Finset (E ≃ᵢ E))
    (hsrc : h.source = A) (htgt : h.target = B)
    (hdec_h : Equidecomp.IsDecompOn h.toFun h.source Sh)
    (hdec_h' : Equidecomp.IsDecompOn h.symm.toFun h.symm.source Sh')
    (h0h : ∀ s ∈ Sh, s 0 = 0) (h0h' : ∀ s ∈ Sh', s 0 = 0)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = B ∧
        f.target = B ∧ g.target = B ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = A ∧
      f.target = A ∧ g.target = A ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0) := by
  obtain ⟨f, g, Sf, Sg, hdisj, hunion, hftgt, hgtgt, hdec_f, hdec_g, h0f, h0g⟩ := hp
  have hft : f.target = h.target := hftgt.trans htgt.symm
  have hgt : g.target = h.target := hgtgt.trans htgt.symm
  have hfs : f.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_left
  have hgs : g.source ⊆ h.target := by rw [htgt, ← hunion]; exact Set.subset_union_right
  obtain ⟨Sfh, hdec_fh, h0fh⟩ :=
    decomp_trans_origin_fixing f h.symm Sf Sh' hdec_f hdec_h' h0f h0h'
  obtain ⟨Sf', hdec_f', h0f'⟩ :=
    decomp_trans_origin_fixing h (f.trans h.symm) Sh Sfh hdec_h hdec_fh h0h h0fh
  obtain ⟨Sgh, hdec_gh, h0gh⟩ :=
    decomp_trans_origin_fixing g h.symm Sg Sh' hdec_g hdec_h' h0g h0h'
  obtain ⟨Sg', hdec_g', h0g'⟩ :=
    decomp_trans_origin_fixing h (g.trans h.symm) Sh Sgh hdec_h hdec_gh h0h h0gh
  refine ⟨h.trans (f.trans h.symm), h.trans (g.trans h.symm), Sf', Sg',
    ?_, ?_, ?_, ?_, hdec_f', hdec_g', h0f', h0g'⟩
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_disjoint h f g hdisj
  · rw [transfer_source h f hft, transfer_source h g hgt]
    exact transfer_union A B h f g hsrc htgt hunion
  · rw [transfer_target h f hft hfs]; exact hsrc
  · rw [transfer_target h g hgt hgs]; exact hsrc


/-- Transfer the paradoxical decomposition of `S² \ D` to `S²`, threading the origin-fixing
data. A Hilbert-hotel absorption equidecomp `h : S² ≃ S² \ D` (built from a rotation fixing 0)
is composed with `paradoxical_transfer_along_equidecomp_origin_fixing` to lift the paradox from
`S² \ D` to `S²` while preserving the origin-fixing decomposition sets. -/
theorem absorb_countable_paradoxical_origin_fixing
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D)
    (hp : ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0) := by
  obtain ⟨h, Sh, Sh', hsrc, htgt, hdec_h, hdec_h', h0h, h0h'⟩ :=
    sphere_hilbert_hotel_absorb_origin_fixing D hDc hDs hD0
  exact paradoxical_transfer_along_equidecomp_origin_fixing
    (Metric.sphere (0 : E) 1) (Metric.sphere (0 : E) 1 \ D)
    h Sh Sh' hsrc htgt hdec_h hdec_h' h0h h0h' hp

/-- Alias for `is_decomp_hilbert_origin_fixing` with a piecewise isometry syntax:
given `f` that equals `ρ` on `T` and is the identity off `T`, produces a finset `S ⊆ E ≃ᵢ E`
witnessing `IsDecompOn f A S` with every element of `S` fixing the origin. -/
theorem is_decomp_piecewise_isometry_origin_fixing (A T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) (hρ0 : ρ 0 = 0) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S ∧ ∀ s ∈ S, s 0 = 0 :=
  is_decomp_hilbert_origin_fixing A T ρ hρ0 f hf hf'


/-- Using a Hilbert-hotel shift by `ρ := φ(of 1)⁻¹`, absorb the empty-word part of `M` into the
letter-1 part. Concretely, constructs an equidecomposition from the non-letter-0 set `A ⊆ M` to
`A \ D` (words starting with generator 1), with origin-fixing realizing finset (since `ρ` fixes
0 via `hfix0`). -/
theorem absorb_empty_word_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (_hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (_hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (_hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (Sa : Finset (E ≃ᵢ E)),
      e.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      e.target = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      Equidecomp.IsDecompOn e.toFun e.source Sa ∧
      (∀ s ∈ Sa, s 0 = 0) := by
  classical
  set ρ : E ≃ᵢ E := (φ (FreeGroup.of 1))⁻¹ with hρ_def
  set D : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none} with hD_def
  set A : Set E := {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
    with hA_def
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hT_def
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  have hDT : D ⊆ T := by
    intro x hx; rw [hT_def]; exact Set.mem_iUnion.mpr ⟨0, x, hx, by simp⟩
  have hTA : T ⊆ A := tower_subset_source φ M hinv rep wrd hcoh
  have hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D)) :=
    orbit_tower_disjoint φ M hinv rep wrd hcoh
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hAD : A \ D = {x | x ∈ M ∧
      ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
       (FreeGroup.toWord (wrd x)).head? = some (1, false))} := letter1_source_eq_diff M wrd
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hρ0 : ρ 0 = 0 := by
    have heq : ρ = φ ((FreeGroup.of 1)⁻¹) := by rw [hρ_def, map_inv]
    rw [heq]; exact hfix0 _
  obtain ⟨S, hSdec, hSfix⟩ := is_decomp_piecewise_isometry_origin_fixing A T ρ f hf hf' hρ0
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) ⟨S, hSdec⟩,
    S, rfl, hAD, hSdec, hSfix⟩


/-- Build an equidecomposition from the letter-0 subset of `M` (words whose first letter is
generator 0 or its inverse) to all of `M`, with an origin-fixing realizing finset `{1, φ(of 0)}`.
The `A`-piece (starting with `(0, true)`) maps to itself; the `B`-piece is shifted by `φ(of 0)`. -/
theorem build_letter0_equidecomp_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (_hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (_hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (_hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (f : Equidecomp E (E ≃ᵢ E)) (Sf : Finset (E ≃ᵢ E)),
      f.source = {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      f.target = M ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      (∀ s ∈ Sf, s 0 = 0) := by
  classical
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 0) with hg0
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)} with hA
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} with hB
  set S₀ : Set E :=
    {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} with hS₀def
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hfdef
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hgdef
  have hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x :=
    fun x hx w => (hcoh x hx w).2
  have hsplit : (fun x => g0 • x) '' B = M \ A := letter0_split φ M hinv wrd hwrd
  have hS₀ : S₀ = A ∪ B := letter0_source_eq_union M wrd
  have hAB : Disjoint A B := letter0_pieces_disjoint M wrd
  have hAM : A ⊆ M := fun x hx => hx.1
  have hfA : ∀ x ∈ A, f x = x := by intro x hx; simp only [hfdef]; rw [if_pos hx]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hx; simp only [hfdef]; rw [if_neg hx]
  have hgA : ∀ y ∈ A, g y = y := by intro y hy; simp only [hgdef]; rw [if_pos hy]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hy; simp only [hgdef]; rw [if_neg hy]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  obtain ⟨hms0, hmt0, hli0, hri0⟩ := hlaws
  have hms : ∀ x ∈ S₀, f x ∈ M := by intro x hx; rw [hS₀] at hx; exact hms0 x hx
  have hmt : ∀ y ∈ M, g y ∈ S₀ := by intro y hy; rw [hS₀]; exact hmt0 y hy
  have hli : ∀ x ∈ S₀, g (f x) = x := by intro x hx; rw [hS₀] at hx; exact hli0 x hx
  have hri : ∀ y ∈ M, f (g y) = y := hri0
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  have hdecS : Equidecomp.IsDecompOn f S₀ {1, g0} := by
    rw [hS₀]
    intro a _
    by_cases hA' : a ∈ A
    · exact ⟨1, Finset.mem_insert_self 1 {g0}, by rw [hfA a hA']; simp⟩
    · exact ⟨g0, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)), hfnA a hA'⟩
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f S₀ S := ⟨{1, g0}, hdecS⟩
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g S₀ M hms hmt hli hri) hdec,
    {1, g0}, rfl, rfl, hdecS, ?_⟩
  intro s hs
  rw [Finset.mem_insert, Finset.mem_singleton] at hs
  rcases hs with rfl | rfl
  · rfl
  · exact hfix0 (FreeGroup.of 0)


/-- Build an equidecomposition from the letter-1 subset of `M` (words whose first letter is
generator 1 or its inverse) to all of `M`, with an origin-fixing realizing finset `{1, φ(of 1)}`.
The letter-1 and letter-1-inverse pieces partition the source; `φ(of 1)` maps the inverse piece
onto `M \ A` via the free-action coherence, and `φ w 0 = 0` gives the origin-fixing property. -/
theorem b_letter_equidecomp_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (_hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (_hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (_hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (Sb : Finset (E ≃ᵢ E)),
      e.source = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      e.target = M ∧
      Equidecomp.IsDecompOn e.toFun e.source Sb ∧
      (∀ s ∈ Sb, s 0 = 0) := by
  classical
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 1) with hg0
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)} with hA
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} with hB
  set Src : Set E :=
    {x | x ∈ M ∧ ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
        (FreeGroup.toWord (wrd x)).head? = some (1, false))} with hSrcdef
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hfdef
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hgdef
  have hsplit : (fun x => g0 • x) '' B = M \ A :=
    b_letter_split φ M hinv wrd (fun x hxM w => (hcoh x hxM w).2)
  have hSrc : Src = A ∪ B := by
    ext x
    simp only [hSrcdef, hA, hB, Set.mem_setOf_eq, Set.mem_union]
    tauto
  have hAB : Disjoint A B := b_letter_pieces_disjoint M wrd
  have hAM : A ⊆ M := fun x hx => hx.1
  have hfA : ∀ x ∈ A, f x = x := by intro x hx; simp only [hfdef]; rw [if_pos hx]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hx; simp only [hfdef]; rw [if_neg hx]
  have hgA : ∀ y ∈ A, g y = y := by intro y hy; simp only [hgdef]; rw [if_pos hy]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hy; simp only [hgdef]; rw [if_neg hy]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  obtain ⟨hms0, hmt0, hli0, hri0⟩ := hlaws
  have hms : ∀ x ∈ Src, f x ∈ M := by intro x hx; rw [hSrc] at hx; exact hms0 x hx
  have hmt : ∀ y ∈ M, g y ∈ Src := by intro y hy; rw [hSrc]; exact hmt0 y hy
  have hli : ∀ x ∈ Src, g (f x) = x := by intro x hx; rw [hSrc] at hx; exact hli0 x hx
  have hri : ∀ y ∈ M, f (g y) = y := hri0
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  have hdecS : Equidecomp.IsDecompOn f Src {1, g0} := by
    rw [hSrc]
    intro a _
    by_cases hA' : a ∈ A
    · exact ⟨1, Finset.mem_insert_self 1 {g0}, by rw [hfA a hA']; simp⟩
    · exact ⟨g0, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)), hfnA a hA'⟩
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f Src S := ⟨{1, g0}, hdecS⟩
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g Src M hms hmt hli hri) hdec,
    {1, g0}, rfl, rfl, hdecS, ?_⟩
  intro s hs
  rw [Finset.mem_insert, Finset.mem_singleton] at hs
  rcases hs with rfl | rfl
  · rfl
  · exact hfix0 (FreeGroup.of 1)


/-- Compose two origin-fixing equidecompositions into one, with witness `e := e₁.trans e₂`
and realizing finset `S := Finset.image₂ (· * ·) S₂ S₁`. Source and target follow from
`PartialEquiv.trans`; `IsDecompOn` is checked using `mul_smul`; the origin-fixing property
holds because $(g_2 \cdot g_1)(0) = g_2(g_1(0)) = g_2(0) = 0$. -/
theorem equidecomp_trans_glue_origin_fixing
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (h : e₁.target = e₂.source)
    (S₁ S₂ : Finset (E ≃ᵢ E))
    (hd₁ : Equidecomp.IsDecompOn e₁.toFun e₁.source S₁)
    (hd₂ : Equidecomp.IsDecompOn e₂.toFun e₂.source S₂)
    (h0₁ : ∀ s ∈ S₁, s 0 = 0) (h0₂ : ∀ s ∈ S₂, s 0 = 0) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E)),
      e.source = e₁.source ∧ e.target = e₂.target ∧
      Equidecomp.IsDecompOn e.toFun e.source S ∧
      (∀ s ∈ S, s 0 = 0) := by
  classical
  refine ⟨e₁.trans e₂, Finset.image₂ (· * ·) S₂ S₁, ?_, ?_, ?_, ?_⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source]
    rw [← h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx; exact ⟨hx, e₁.map_source' hx⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_target]
    rw [h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx; exact ⟨hx, e₂.map_target' hx⟩
  · intro a ha
    rw [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source] at ha
    obtain ⟨ha1, ha2⟩ := ha
    obtain ⟨g₁, hg₁, hfa⟩ := hd₁ a ha1
    obtain ⟨g₂, hg₂, hfb⟩ := hd₂ (e₁.toFun a) ha2
    refine ⟨g₂ * g₁, Finset.mem_image₂_of_mem hg₂ hg₁, ?_⟩
    change e₂.toFun (e₁.toFun a) = (g₂ * g₁) • a
    rw [hfb, hfa, mul_smul]
  · intro s hs
    obtain ⟨g₂, hg₂, g₁, hg₁, rfl⟩ := Finset.mem_image₂.mp hs
    calc (g₂ * g₁) 0 = g₂ (g₁ 0) := rfl
      _ = g₂ 0 := by rw [h0₁ g₁ hg₁]
      _ = 0 := h0₂ g₂ hg₂


/-- Build an equidecomposition from the non-letter-0 subset of `M` to all of `M`, with an
origin-fixing realizing finset. The construction composes `absorb_empty_word_origin_fixing` and
`b_letter_equidecomp_origin_fixing` via `equidecomp_trans_glue_origin_fixing`; the composite
finset `S₂ * S₁` consists of products of elements fixing 0, hence also fixes 0. -/
theorem build_non_letter0_equidecomp_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (g : Equidecomp E (E ≃ᵢ E)) (Sg : Finset (E ≃ᵢ E)),
      g.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      g.target = M ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sg, s 0 = 0) := by
  obtain ⟨e₂, Sb, he₂s, he₂t, hd₂, h0₂⟩ :=
    b_letter_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨e₁, Sa, he₁s, he₁t, hd₁, h0₁⟩ :=
    absorb_empty_word_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨e, S, hes, het, hd, h0⟩ :=
    equidecomp_trans_glue_origin_fixing e₁ e₂ (by rw [he₁t, he₂s]) Sa Sb hd₁ hd₂ h0₁ h0₂
  exact ⟨e, S, by rw [hes, he₁s], by rw [het, he₂t],
    by rw [hes, he₁s] at hd ⊢; exact hd, h0⟩


/-- Lift a free $F_2$-isometry action to a paradoxical equidecomposition of `M` with
origin-fixing realizing finsets `Sf`, `Sg`. The orbit address map `(rep, wrd)` from
`orbit_address_of_free_action` partitions `M` by "first generator letter = 0?"; the two pieces
are built by `build_letter0_equidecomp_origin_fixing` and
`build_non_letter0_equidecomp_origin_fixing`, each providing an origin-fixing finset. -/
theorem paradoxical_of_free_isometry_action_origin_fixing
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = M ∧
      f.target = M ∧
      g.target = M ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0) := by
  obtain ⟨rep, wrd, hx, hcoh⟩ := orbit_address_of_free_action φ M hinv hfree
  obtain ⟨f, Sf, hfs, hft, hfdec, hf0⟩ :=
    build_letter0_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨g, Sg, hgs, hgt, hgdec, hg0⟩ :=
    build_non_letter0_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  refine ⟨f, g, Sf, Sg, ?_, ?_, hft, hgt, hfdec, hgdec, hf0, hg0⟩
  · rw [hfs, hgs, Set.disjoint_left]
    rintro x ⟨_, hp⟩ ⟨_, hnp⟩
    exact hnp hp
  · rw [hfs, hgs]
    ext x
    simp only [Set.mem_union, Set.mem_setOf_eq]
    constructor
    · rintro (⟨hxM, _⟩ | ⟨hxM, _⟩) <;> exact hxM
    · intro hxM
      by_cases hp : (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0
      · exact Or.inl ⟨hxM, hp⟩
      · exact Or.inr ⟨hxM, hp⟩


/-- Existence of a paradoxical equidecomposition of `S² \ D` for some countable set `D` of
fixed points, with every realizing isometry fixing the origin. The free $F_2$-isometry action
on the sphere is used to construct `D` and the two-piece paradox. -/
theorem sphere_minus_fixed_paradoxical_origin_fixing :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
        Disjoint f.source g.source ∧
        f.source ∪ g.source = Metric.sphere (0 : E) 1 \ D ∧
        f.target = Metric.sphere (0 : E) 1 \ D ∧
        g.target = Metric.sphere (0 : E) 1 \ D ∧
        Equidecomp.IsDecompOn f.toFun f.source Sf ∧
        Equidecomp.IsDecompOn g.toFun g.source Sg ∧
        (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0) := by
  obtain ⟨φ, hinj, hfix0, hfin⟩ := exists_free_isometry_embedding
  obtain ⟨D, hcount, hsub, h0, hinv, hfree⟩ := fixed_free_action_off_countable φ hfix0 hfin
  exact ⟨D, hcount, hsub, h0,
    paradoxical_of_free_isometry_action_origin_fixing φ hinj
      (Metric.sphere (0 : E) 1 \ D) hinv hfree hfix0⟩


/-- **Paradoxical decomposition of the unit sphere with origin-fixing isometries.**
The unit sphere `Metric.sphere (0 : E) 1` admits a paradoxical equidecomposition: two disjoint
equidecompositions `f`, `g` whose union covers `S²` and each maps back onto `S²`, with every
realizing isometry fixing the origin.

The proof obtains a countable fixed-point set `D` and the paradox on `S² \ D` from
`sphere_minus_fixed_paradoxical_origin_fixing`, then absorbs `D` via
`absorb_countable_paradoxical_origin_fixing`. -/
theorem sphere_paradoxical_origin_fixing :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.sphere (0 : E) 1 ∧
      f.target = Metric.sphere (0 : E) 1 ∧
      g.target = Metric.sphere (0 : E) 1 ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0) := by
  obtain ⟨D, hDc, hDs, hD0, hp⟩ := sphere_minus_fixed_paradoxical_origin_fixing
  exact absorb_countable_paradoxical_origin_fixing D hDc hDs hD0 hp


end Library.Geometry.BanachTarski.SphereDecomp
