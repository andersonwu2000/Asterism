import Mathlib.Algebra.Homology.HomologySequence
import Mathlib.Algebra.Homology.QuasiIso
import Mathlib.Algebra.Homology.Refinements
import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
import Library.AlgebraicTopology.MayerVietoris.SmallSimplicesTheorem

/-!
# The Mayer–Vietoris long exact sequence

This file assembles the long exact Mayer–Vietoris sequence in singular homology from the
short exact sequence of chain complexes `mv_short_complex` (built in `ShortExactComplex`) and
the quasi-isomorphism between the small-simplices subcomplex `C(A) + C(B)` and the full
singular chain complex `C(X)` (established via the refinement facts of
`SmallSimplicesTheorem`).

Most of the file develops that small-simplices quasi-isomorphism: a general abelian-category
criterion identifying injectivity/surjectivity of a `homologyMap` with an element-level
cycle-descent property (`homology_map_injective_of_cycle_descent`, `homology_incl_epi`), fed
by the topological refinement facts `singular_small_cycle_homologous` and
`singular_small_boundary_small` from `SmallSimplicesTheorem`.

## Main statements

* `mv_incl_quasi_iso`: the inclusion of the small-simplices subcomplex into the full singular
  chain complex is a quasi-isomorphism.
* `mv_les_exact_pair`, `mv_les_exact_inter`, `mv_les_exact_total`: exactness of the
  **Mayer–Vietoris long exact sequence** at each of its three spots.

## Main definitions

* `chain_complex_top_iso`: the isomorphism identifying `supported_chain_complex X ⊤` with
  mathlib's `X.chainComplex`.
* `mv_delta`: the Mayer–Vietoris connecting homomorphism, transported along the
  small-simplices quasi-isomorphism.
-/

open CategoryTheory
open CategoryTheory Simplicial
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.MayerVietoris.SmallSimplicesTheorem

namespace Library.AlgebraicTopology.MayerVietoris.LongExactSequence

/-- A cycle `c` of `K` whose image under `K.iCycles` equals a boundary `K.d (j + 1) j w'`
already represents the zero class of `K.homologyπ j`. -/
theorem homology_pi_zero_of_boundary
    {R : Type} [Ring R] {K : ChainComplex (ModuleCat R) ℕ} (j : ℕ) :
    ∀ (c : K.cycles j) (w' : K.X (j + 1)),
      ConcreteCategory.hom (K.iCycles j) c = ConcreteCategory.hom (K.d (j + 1) j) w' →
      ConcreteCategory.hom (K.homologyπ j) c = 0 := by
  intro c w' hcw'
  have hmono : Function.Injective (ConcreteCategory.hom (K.iCycles j)) := by
    rw [← ModuleCat.mono_iff_injective]
    infer_instance
  have hc : ConcreteCategory.hom (K.toCycles (j + 1) j) w' = c := by
    apply hmono
    rw [← CategoryTheory.comp_apply, K.toCycles_i, hcw']
  rw [← hc, ← CategoryTheory.comp_apply, K.toCycles_comp_homologyπ]
  simp

/-- `Finsupp.linearCombination R id` is surjective, hence an epimorphism as a `ModuleCat`
hom, via `ModuleCat.epi_iff_surjective` and `Finsupp.linearCombination_id_surjective`. -/
theorem epi_linear_combination_id
    {R : Type} [Ring R] {A₁ : ModuleCat R} :
    Epi (ModuleCat.ofHom (Finsupp.linearCombination R (id : A₁ → A₁))) := by
  rw [ModuleCat.epi_iff_surjective]
  exact Finsupp.linearCombination_id_surjective R A₁

/-- Postcomposing the generator map `linearCombination R id` with `y₂ : A₁ ⟶ K.X i` splits,
via the pointwise lift data `xf`/`wf` witnessing `h`, as `linearCombination R xf ≫ φ.f i`
plus a boundary term `linearCombination R wf ≫ K.d (i + 1) i`. -/
theorem linearCombination_id_comp_eq
    {R : Type} [Ring R]
    {K L : ChainComplex (ModuleCat R) ℕ} (φ : L ⟶ K) (i : ℕ)
    {A₁ : ModuleCat R} (y₂ : A₁ ⟶ K.X i)
    (xf : A₁ → L.X i) (wf : A₁ → K.X (i + 1))
    (h : ∀ a, y₂.hom a = (φ.f i).hom (xf a) + (K.d (i + 1) i).hom (wf a)) :
    ModuleCat.ofHom (Finsupp.linearCombination R (id : A₁ → A₁)) ≫ y₂
      = ModuleCat.ofHom (Finsupp.linearCombination R xf) ≫ φ.f i
        + ModuleCat.ofHom (Finsupp.linearCombination R wf) ≫ K.d (i + 1) i := by aesop

/-- Package the pointwise lift hypothesis `hpt` into total lift functions `xf`, `wf`
on `A₁` (via the `choose` tactic, i.e. `Classical.choice`). -/
theorem pointwise_choice
    {R : Type} [Ring R]
    {K L : ChainComplex (ModuleCat R) ℕ} (φ : L ⟶ K) (i : ℕ)
    (hpt : ∀ (c : K.X i), (K.d i (i - 1)).hom c = 0 →
        ∃ (x : L.X i), (L.d i (i - 1)).hom x = 0 ∧
          ∃ (w : K.X (i + 1)), c = (φ.f i).hom x + (K.d (i + 1) i).hom w)
    {A₁ : ModuleCat R} (y₂ : A₁ ⟶ K.X i)
    (hy₂ : y₂ ≫ K.d i (i - 1) = 0) :
    ∃ (xf : A₁ → L.X i) (wf : A₁ → K.X (i + 1)),
      ∀ a, (L.d i (i - 1)).hom (xf a) = 0 ∧
           y₂.hom a = (φ.f i).hom (xf a) + (K.d (i + 1) i).hom (wf a) := by
  have h : ∀ a, (K.d i (i - 1)).hom (y₂.hom a) = 0 := by
    intro a
    have hy₂' : (y₂ ≫ K.d i (i - 1)).hom = (0 : A₁ ⟶ K.X (i - 1)).hom := by rw [hy₂]
    simpa [ModuleCat.hom_comp, ModuleCat.hom_zero] using congrFun (congrArg DFunLike.coe hy₂') a
  choose xf hxf wf hwf using fun a => hpt (y₂.hom a) (h a)
  exact ⟨xf, wf, fun a => ⟨hxf a, hwf a⟩⟩

/-- Lifts `xf` satisfying the cycle condition `hxf` assemble, via `linearCombination`,
into a chain map whose composite with the differential `L.d i (i - 1)` vanishes. -/
theorem linearCombination_comp_d_eq_zero
    {R : Type} [Ring R]
    {L : ChainComplex (ModuleCat R) ℕ} (i : ℕ)
    {A₁ : ModuleCat R} (xf : A₁ → L.X i)
    (hxf : ∀ a, (L.d i (i - 1)).hom (xf a) = 0) :
    ModuleCat.ofHom (Finsupp.linearCombination R xf) ≫ L.d i (i - 1) = 0 := by aesop

/-- Free-module refinement: with `A' := A₁ →₀ R` the free module on the carrier of `A₁`
and `π` the canonical surjection `linearCombination R id`, the per-element lift data
(`xf`, `wf`) extracted from the pointwise hypothesis `hpt` via `pointwise_choice` assembles
into linear maps `x₂`, `y₁` satisfying the cycle condition and the main identity on
generators. -/
theorem epi_refinement_of_pointwise
    {R : Type} [Ring R]
    {K L : ChainComplex (ModuleCat R) ℕ} (φ : L ⟶ K) (i : ℕ)
    (hpt : ∀ (c : K.X i), (K.d i (i - 1)).hom c = 0 →
        ∃ (x : L.X i), (L.d i (i - 1)).hom x = 0 ∧
          ∃ (w : K.X (i + 1)), c = (φ.f i).hom x + (K.d (i + 1) i).hom w) :
    ∀ ⦃A₁ : ModuleCat R⦄ (y₂ : A₁ ⟶ K.X i),
      y₂ ≫ K.d i (i - 1) = 0 →
        ∃ (A' : ModuleCat R) (π : A' ⟶ A₁), ∃ (_ : Epi π),
          ∃ (x₂ : A' ⟶ L.X i),
          ∃ (_ : x₂ ≫ L.d i (i - 1) = 0),
          ∃ (y₁ : A' ⟶ K.X (i + 1)),
            π ≫ y₂ = x₂ ≫ φ.f i + y₁ ≫ K.d (i + 1) i := by
  intro A₁ y₂ hy₂
  obtain ⟨xf, wf, hxw⟩ := pointwise_choice φ i hpt y₂ hy₂
  exact ⟨ModuleCat.of R (A₁ →₀ R),
    ModuleCat.ofHom (Finsupp.linearCombination R (id : A₁ → A₁)),
    epi_linear_combination_id,
    ModuleCat.ofHom (Finsupp.linearCombination R xf),
    linearCombination_comp_d_eq_zero i xf (fun a => (hxw a).1),
    ModuleCat.ofHom (Finsupp.linearCombination R wf),
    linearCombination_id_comp_eq φ i y₂ xf wf (fun a => (hxw a).2)⟩

/-- The differential of `supported_chain_complex`, on the underlying `Finsupp`, is the
alternating face-map sum: `simp only [supported_chain_complex]` unfolds it to
`LinearMap.restrict` of the transported categorical differential, and
`transported_differential_eq_lmapdomain_sum` rewrites that raw composite to
`∑ (-1) ^ j • lmapDomain (δ j)`. -/
theorem supported_d_apply_val
    {R : Type} [Ring R] (X : SSet.{0}) (A : X.Subcomplex) (n : ℕ)
    (v : (supported_chain_complex (R := R) X A).X (n + 1)) :
    ((ConcreteCategory.hom ((supported_chain_complex (R := R) X A).d (n + 1) n)) v).val
      = (∑ j : Fin (n + 2), (-1 : ℤ) ^ (j : ℕ) • Finsupp.lmapDomain R R (X.δ j)) v.val := by
  simp only [supported_chain_complex, ChainComplex.of_d, transported_differential_eq_lmapdomain_sum]
  rfl

/-- `Finsupp.supported` of a subcomplex sup splits as the sup of the `Finsupp.supported`
of each piece, via `Subfunctor.max_obj` (a sup is objectwise a union) and
`Finsupp.supported_union`. -/
theorem support_union_obj_eq
    {R : Type} [Ring R] {X : TopCat.{0}} (A B : Set X) (m : ℕ) :
    Finsupp.supported R R
        ((singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B).obj (Opposite.op ⦋m⦌))
      = Finsupp.supported R R {τ : (TopCat.toSSet.obj X) _⦋m⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R {τ : (TopCat.toSSet.obj X) _⦋m⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌) τ) ⊆ B} := by
  rw [CategoryTheory.Subfunctor.max_obj, Finsupp.supported_union]
  rfl

/-- A cycle `z` of `supported_chain_complex (A ⊔ B)` whose image in `supported_chain_complex ⊤`
bounds already bounds within `supported_chain_complex (A ⊔ B)`, granted the raw-`Finsupp`
descent fact `hbd`. -/
theorem incl_cycle_descent
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (_hA : IsOpen A) (_hB : IsOpen B) (_hAB : A ∪ B = Set.univ) (i : ℕ)
    (hbd : ∀ (n : ℕ) (z : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
        (w : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R),
        z ∈ (Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
            Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}) →
        z = (∑ j : Fin (n + 2), (-1 : ℤ) ^ (j : ℕ)
            • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ j)) w →
        ∃ w' : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R,
          w' ∈ (Finsupp.supported R R
                {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
                  Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ A} ⊔
              Finsupp.supported R R
                {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
                  Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ B}) ∧
            z = (∑ j : Fin (n + 2), (-1 : ℤ) ^ (j : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ j)) w')
    (z : (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).X i)
    (_hz : (ConcreteCategory.hom
        ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).d i
                (i - 1))) z = 0)
    (hbound : ∃ w, (ConcreteCategory.hom
          ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f
            i)) z =
        (ConcreteCategory.hom
          ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d (i + 1) i)) w) :
    ∃ w', z = (ConcreteCategory.hom
        ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).d (i + 1) i))
        w' := by
  obtain ⟨w, hw⟩ := hbound
  have h_diff : ∀ (A' : (TopCat.toSSet.obj X).Subcomplex) (m : ℕ)
      (v : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) A').X (m + 1)),
      ((ConcreteCategory.hom
          ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) A').d (m + 1) m)) v).val
        = (∑ j : Fin (m + 2), (-1 : ℤ) ^ (j : ℕ) •
            Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ j)) v.val :=
    fun A' m v => supported_d_apply_val (TopCat.toSSet.obj X) A' m v
  have h_supp : ∀ (m : ℕ),
      Finsupp.supported R R
          ((singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B).obj (Opposite.op ⦋m⦌))
        = Finsupp.supported R R {τ : (TopCat.toSSet.obj X) _⦋m⦌ |
              Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌) τ) ⊆ A} ⊔
          Finsupp.supported R R {τ : (TopCat.toSSet.obj X) _⦋m⦌ |
              Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌) τ) ⊆ B} :=
    fun m => support_union_obj_eq A B m
  have hzw : (z.val : (TopCat.toSSet.obj X) _⦋i⦌ →₀ R)
      = (∑ j : Fin (i + 2), (-1 : ℤ) ^ (j : ℕ)
          • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ j)) w.val := by
    have hv := Subtype.ext_iff.mp hw
    rw [h_diff ⊤ i w] at hv
    exact hv
  have hmem : (z.val : (TopCat.toSSet.obj X) _⦋i⦌ →₀ R) ∈
      Finsupp.supported R R {τ | Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋i⦌) τ) ⊆ A} ⊔
      Finsupp.supported R R {τ | Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋i⦌) τ) ⊆ B} := by
    rw [← h_supp i]; exact z.2
  obtain ⟨w'val, hw'mem, hw'eq⟩ := hbd i z.val w.val hmem hzw
  rw [← h_supp (i + 1)] at hw'mem
  refine ⟨⟨w'val, hw'mem⟩, ?_⟩
  apply Subtype.ext
  rw [h_diff (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B) i ⟨w'val, hw'mem⟩]
  exact hw'eq

/-- The degree-`0` differential `d 0 (0 - 1)` of any supported complex is zero, since
`ComplexShape.down ℕ` has no `Rel` at `(0, 0)` (and `0 - 1 = 0` in `ℕ`). -/
theorem d_zero_supported_eq_zero {R : Type} [Ring R] {X : TopCat.{0}}
    (S : (TopCat.toSSet.obj X).Subcomplex)
    (y : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) S).X 0) :
    ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) S).d 0 (0 - 1)).hom y = 0 := by
  have h0 : (0 : ℕ) - 1 = 0 := rfl
  rw [h0, HomologicalComplex.shape _ 0 0 (by simp [ComplexShape.down_Rel])]
  simp

/-- Unfold `singular_subcomplex_of_set` to its underlying range-predicate set; then
`Subfunctor.max_obj` and `Finsupp.supported_union` give the sup decomposition. -/
theorem singular_supported_sup_eq
    {R : Type} [Ring R] {X : TopCat.{0}} (A B : Set X) (m : ℕ) :
    Finsupp.supported R R
        ((singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B).obj (Opposite.op ⦋m⦌))
      = (Finsupp.supported R R
            {τ : (TopCat.toSSet.obj X) _⦋m⦌ |
              Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌) τ) ⊆ A} ⊔
          Finsupp.supported R R
            {τ : (TopCat.toSSet.obj X) _⦋m⦌ |
              Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌) τ) ⊆ B} :
            Submodule R ((TopCat.toSSet.obj X) _⦋m⦌ →₀ R)) := support_union_obj_eq A B m

/-- Restating `supported_d_apply_val` for a general subcomplex `A` (not just `⊤`): the
differential of `supported_chain_complex X A`, on the underlying `Finsupp`, is the
alternating face-map sum `∑ (-1) ^ i • lmapDomain (δ i)`. -/
theorem supp_diff_apply_coe
    {R : Type} [Ring R] {X : TopCat.{0}}
    (A : (TopCat.toSSet.obj X).Subcomplex) (m : ℕ)
    (y : Finsupp.supported R R (A.obj (Opposite.op ⦋m + 1⦌))) :
    (((supported_chain_complex (R := R) (TopCat.toSSet.obj X) A).d (m + 1) m).hom y).val
      = (∑ i : Fin (m + 2), (-1 : ℤ) ^ (i : ℕ) •
          Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) y.val :=
  supported_d_apply_val (TopCat.toSSet.obj X) A m y

/-- The barycentric-subdivision step of the small-simplices refinement: a `⊤`-cycle `c`
in degree `n + 1` equals an `{A, B}`-small cycle `x` plus a boundary `∂w`. -/
theorem small_cycle_refinement_succ
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ)
    (c : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X (n + 1))
    (hc : ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d (n + 1) n).hom c = 0) :
    ∃ (x : (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).X (n + 1)),
      ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).d (n + 1)
            n).hom x = 0 ∧
      ∃ (w : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X (n + 1 + 1)),
        c = ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f
                (n + 1)).hom x
          + ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d (n + 1 + 1)
              (n + 1)).hom w := by
  -- Translate the ⊤-cycle `c` to the raw Finsupp alternating-face-sum form, invoke the
  -- proved barycentric refinement `singular_small_cycle_homologous`, then translate the
  -- resulting small cycle `z'` + prism boundary `w` back through the supported-chain-complex
  -- dictionary: `supp_diff_apply_coe` (categorical `d` = Σ (-1)ⁱ lmapDomain δᵢ on `.val`) and
  -- `singular_supported_sup_eq` (support of `A ⊔ B` = supp A ⊔ supp B).
  have hz : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) •
      Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) c.val = 0 := by
    have hb := supp_diff_apply_coe (R := R) (X := X) ⊤ n c
    rw [← hb, hc]; rfl
  obtain ⟨z', w, hsupp, hcyc, hbdy⟩ :=
    singular_small_cycle_homologous hA hB hAB n c.val hz
  have hz'mem : z' ∈ Finsupp.supported R R
      ((singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B).obj
        (Opposite.op ⦋n + 1⦌)) := by
    rw [singular_supported_sup_eq]; exact hsupp
  have hwmem : w ∈ Finsupp.supported R R
      ((⊤ : (TopCat.toSSet.obj X).Subcomplex).obj (Opposite.op ⦋n + 2⦌)) := by
    rw [Subfunctor.top_obj, Set.top_eq_univ, Finsupp.supported_univ]; exact Submodule.mem_top
  refine ⟨⟨z', hz'mem⟩, ?_, ⟨w, hwmem⟩, ?_⟩
  · apply Subtype.ext
    have hb := supp_diff_apply_coe (R := R) (X := X)
      (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B) n ⟨z', hz'mem⟩
    rw [hb]; exact hcyc
  · apply Subtype.ext
    have hb := supp_diff_apply_coe (R := R) (X := X) ⊤ (n + 1) ⟨w, hwmem⟩
    have hincl : (((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f
          (n + 1)).hom ⟨z', hz'mem⟩).val = z' := rfl
    erw [AddMemClass.coe_add]
    rw [hincl, hb]
    change (c.val : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R) = z' +
      (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) •
        Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) w
    rw [← hbdy]; abel

/-- `homologyπ` is surjective on underlying modules: an epimorphism
(`HomologicalComplex.instEpiHomologyπ`) that, in `ModuleCat R`, is surjective
(`ModuleCat.epi_iff_surjective`). -/
theorem homology_pi_surjective {R : Type} [Ring R] {K : ChainComplex (ModuleCat R) ℕ} (j : ℕ) :
    ∀ (α : K.homology j),
      ∃ c : K.cycles j, CategoryTheory.ConcreteCategory.hom (K.homologyπ j) c = α := by
  exact (ModuleCat.epi_iff_surjective (K.homologyπ j)).1
    (HomologicalComplex.instEpiHomologyπ K j)

/-- Every `0`-simplex is `{A, B}`-small when `A ∪ B = univ`: its range is a subsingleton
(a `0`-simplex has subsingleton domain), so if that single point lies in `A` (resp. `B`)
the whole range does, placing `σ` in `singular_subcomplex_of_set X A` (resp. `X B`), hence
in their sup. -/
theorem zero_simplex_mem_cover {X : TopCat.{0}} {A B : Set X}
    (hAB : A ∪ B = Set.univ)
    (σ : (TopCat.toSSet.obj X) _⦋0⦌) :
    σ ∈ (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B).obj
          (Opposite.op ⦋0⦌) := by
  rw [CategoryTheory.Subfunctor.max_obj]
  simp only [singular_subcomplex_of_set, Set.mem_union, Set.mem_setOf_eq]
  set f := ⇑((X.toSSetObjEquiv (Opposite.op ⦋0⦌)) σ) with hf
  -- a 0-simplex has a subsingleton domain, so its range is a subsingleton
  have h_ss : Set.Subsingleton (Set.range f) := Set.subsingleton_range f
  rcases (Set.range f).eq_empty_or_nonempty with he | ⟨p, hp⟩
  · left; rw [he]; exact Set.empty_subset _
  · -- the single point `p` lies in `A ∪ B = univ`, so `range ⊆ A` or `range ⊆ B`
    rcases (hAB ▸ Set.mem_univ p : p ∈ A ∪ B) with hpA | hpB
    · exact Or.inl fun x hx => (h_ss hx hp) ▸ hpA
    · exact Or.inr fun x hx => (h_ss hx hp) ▸ hpB

/-- Degree-`0` small-simplices refinement: every `0`-simplex lies in `A` or `B` (since
`A ∪ B = univ` and a `0`-simplex has singleton range), so a top-supported `0`-chain `c` is
already `{A, B}`-small: `x := c.val` retyped into the `A ⊔ B` support, via
`zero_simplex_mem_cover`, witnesses it. -/
theorem zero_chain_small_witness {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hAB : A ∪ B = Set.univ)
    (c : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X 0) :
    ∃ (x : (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).X 0),
      ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
          (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f
            0).hom x
        = c := by
  have h_cover := zero_simplex_mem_cover (A := A) (B := B) hAB
  refine ⟨⟨c.val, ?_⟩, ?_⟩
  · rw [Finsupp.mem_supported]
    intro s hs
    exact h_cover s
  · apply Subtype.ext
    rfl

/-- Degree-`0` small-simplices refinement: `d 0 (0 - 1) = d 0 0 = 0` (not consecutive in
`ComplexShape.down`), so both `hc` and the `∂x = 0` conjunct are vacuous, and every
`0`-simplex lies in `A` or `B` (since `A ∪ B = univ`), so `c` is already `{A, B}`-small:
take `x` to be the coerced witness `zero_chain_small_witness` and `w = 0`. -/
theorem small_cycle_refinement_zero
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (_hA : IsOpen A) (_hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (c : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X 0)
    (_hc : ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d 0 (0 - 1)).hom c = 0) :
    ∃ (x : (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).X 0),
      ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).d 0
            (0 - 1)).hom x = 0 ∧
      ∃ (w : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X (0 + 1)),
        c = ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f
                0).hom x
          + ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d (0 + 1) 0).hom w := by
  have h_d := fun y => d_zero_supported_eq_zero (R := R)
    (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B) y
  have h_witness := zero_chain_small_witness (R := R) hAB c
  obtain ⟨x, hx⟩ := h_witness
  refine ⟨x, h_d x, 0, ?_⟩
  rw [map_zero, add_zero]
  exact hx.symm

/-- Small-simplices refinement, pointwise: every `⊤`-cycle `c` in degree `i` equals an
`{A, B}`-small cycle `x` plus a boundary `∂w`. Degree `0` is `small_cycle_refinement_zero`
(every `0`-chain is already small); degree `n + 1` is the barycentric-subdivision crux
`small_cycle_refinement_succ`. -/
theorem small_cycle_refinement_pointwise
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (i : ℕ)
    (c : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X i)
    (hc : ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d i (i - 1)).hom c = 0) :
    ∃ (x : (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).X i),
      ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).d i
            (i - 1)).hom x = 0 ∧
      ∃ (w : (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).X (i + 1)),
        c = ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f
                i).hom x
          + ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).d (i + 1) i).hom w := by
  cases i with
  | zero => exact small_cycle_refinement_zero hA hB hAB c hc
  | succ n => exact small_cycle_refinement_succ hA hB hAB n c hc

/-- Refinement obligation for `Epi (homologyMap incl i)`: the pure `ModuleCat` packaging
`epi_refinement_of_pointwise` (free-module refinement of `A₁`, assembling per-element data
into linear maps) fed by the topological pointwise crux
`small_cycle_refinement_pointwise`. -/
theorem homology_incl_epi_refinement
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (i : ℕ) :
    ∀ ⦃A₁ : ModuleCat R⦄ (y₂ : A₁ ⟶ (supported_chain_complex (TopCat.toSSet.obj X) ⊤).X i),
      y₂ ≫ (supported_chain_complex (TopCat.toSSet.obj X) ⊤).d i (i - 1) = 0 →
        ∃ (A' : ModuleCat R) (π : A' ⟶ A₁), ∃ (_ : Epi π),
          ∃ (x₂ : A' ⟶ (supported_chain_complex (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).X i),
          ∃ (_ : x₂ ≫ (supported_chain_complex (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B)).d i (i - 1) = 0),
          ∃ (y₁ : A' ⟶ (supported_chain_complex (TopCat.toSSet.obj X) ⊤).X (i + 1)),
            π ≫ y₂ = x₂ ≫ (supported_chain_complex_incl (TopCat.toSSet.obj X)
                (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)).f i
              + y₁ ≫ (supported_chain_complex (TopCat.toSSet.obj X) ⊤).d (i + 1) i :=
  epi_refinement_of_pointwise
    (supported_chain_complex_incl (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) i
    (small_cycle_refinement_pointwise hA hB hAB i)

/-- Epi on homology via the abelian-category refinement criterion
`epi_homologyMap_iff_up_to_refinements` (in `ModuleCat R`): every cycle in the target
`C(X)` lifts, up to a boundary, to the image of a source cycle from `C(A) + C(B)`, which is
`homology_incl_epi_refinement`. -/
theorem homology_incl_epi
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (i : ℕ) :
    Epi (HomologicalComplex.homologyMap
      (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) i) := by
  rw [HomologicalComplex.epi_homologyMap_iff_up_to_refinements _ (i+1) i (i-1)
    (by simp [ComplexShape.prev])
    (by
      rcases i with _ | m
      · exact (ComplexShape.down ℕ).next_eq_self' 0 (fun k hk => by simp [ComplexShape.down] at hk)
      · exact (ComplexShape.down ℕ).next_eq' (show (ComplexShape.down ℕ).Rel (m + 1) m from rfl))]
  exact homology_incl_epi_refinement (R := R) (X := X) (A := A) (B := B) hA hB hAB i

/-- Exactness at cycles: a cycle killed by `homologyπ` lifts through `toCycles`.
`homologyIsCokernel` makes `homologyπ` the cokernel of `toCycles (j + 1) j`, so the short
complex `toCycles ⟶ homologyπ` is exact, and `moduleCat_exact_iff` turns
`homologyπ z = 0` into the desired preimage `w` with `toCycles w = z`. -/
theorem toCycles_preimage_of_homology_pi_zero {R : Type} [Ring R]
    {L : ChainComplex (ModuleCat R) ℕ} (j : ℕ) (z : L.cycles j)
    (h : CategoryTheory.ConcreteCategory.hom (L.homologyπ j) z = 0) :
    ∃ w : L.X (j + 1),
      CategoryTheory.ConcreteCategory.hom (L.toCycles (j + 1) j) w = z := by
  let T' := CategoryTheory.ShortComplex.mk (L.toCycles (j+1) j) (L.homologyπ j)
    (L.toCycles_comp_homologyπ (j+1) j)
  have hT' : T'.Exact :=
    T'.exact_of_g_is_cokernel (L.homologyIsCokernel (j+1) j ((ComplexShape.down ℕ).prev_eq' rfl))
  exact (CategoryTheory.ShortComplex.moduleCat_exact_iff T').mp hT' z h

/-- A cycle `z` with zero homology class has `iCycles z` a boundary: lift `z` through
`toCycles` to some `w : L.X (j + 1)` via `toCycles_preimage_of_homology_pi_zero`, then
`toCycles_i` (`toCycles ≫ iCycles = d`) turns the lift into `iCycles z = d w`. -/
theorem cycle_boundary_of_homology_pi_zero {R : Type} [Ring R]
    {L : ChainComplex (ModuleCat R) ℕ} (j : ℕ) (z : L.cycles j) :
    CategoryTheory.ConcreteCategory.hom (L.homologyπ j) z = 0 →
    ∃ w : L.X (j + 1), CategoryTheory.ConcreteCategory.hom (L.iCycles j) z =
      CategoryTheory.ConcreteCategory.hom (L.d (j + 1) j) w := by
  intro h
  have h_pre := toCycles_preimage_of_homology_pi_zero j z h
  have h_id : ∀ w : L.X (j + 1),
      CategoryTheory.ConcreteCategory.hom (L.iCycles j)
          (CategoryTheory.ConcreteCategory.hom (L.toCycles (j + 1) j) w) =
        CategoryTheory.ConcreteCategory.hom (L.d (j + 1) j) w := by
    intro w
    rw [← CategoryTheory.ConcreteCategory.comp_apply, HomologicalComplex.toCycles_i]
  obtain ⟨w, hw⟩ := h_pre
  refine ⟨w, ?_⟩
  rw [← hw]
  exact h_id w

/-- A cycle `c` in `K` whose homology class dies under `φ` maps to a boundary in `L`: push
the hypothesis through `homologyπ_naturality` to see that `cyclesMap φ c` has trivial
homology class in `L`, apply `cycle_boundary_of_homology_pi_zero` for its bounding `w`, and
transport `iCycles` back across `φ` via `cyclesMap_i`. -/
theorem image_boundary_of_homologyMap_eq_zero {R : Type} [Ring R]
    {K L : ChainComplex (ModuleCat R) ℕ}
    (φ : K ⟶ L) (j : ℕ) (c : K.cycles j) :
    CategoryTheory.ConcreteCategory.hom (HomologicalComplex.homologyMap φ j)
        (CategoryTheory.ConcreteCategory.hom (K.homologyπ j) c) = 0 →
    ∃ w : L.X (j + 1),
      CategoryTheory.ConcreteCategory.hom (φ.f j)
          (CategoryTheory.ConcreteCategory.hom (K.iCycles j) c) =
        CategoryTheory.ConcreteCategory.hom (L.d (j + 1) j) w := by
  intro h
  have hnat := HomologicalComplex.homologyπ_naturality φ j
  have hz : CategoryTheory.ConcreteCategory.hom (L.homologyπ j)
      (CategoryTheory.ConcreteCategory.hom (HomologicalComplex.cyclesMap φ j) c) = 0 := by
    rw [← CategoryTheory.comp_apply, ← hnat, CategoryTheory.comp_apply]; exact h
  obtain ⟨w, hw⟩ := cycle_boundary_of_homology_pi_zero (L := L) j
    (CategoryTheory.ConcreteCategory.hom (HomologicalComplex.cyclesMap φ j) c) hz
  refine ⟨w, ?_⟩
  rw [← hw]
  have hci := HomologicalComplex.cyclesMap_i φ j
  rw [← CategoryTheory.comp_apply, ← hci, CategoryTheory.comp_apply]

/-- Represent a homology class killed by `homologyMap φ` and exhibit its bounding witness:
`homology_pi_surjective` picks a cycle `c` representing `α`, `iCycles_d` gives the cycle
condition, and `image_boundary_of_homologyMap_eq_zero` (from `homologyMap φ α = 0`, rewritten
via `hc`) produces `w` with `φ.f c = L.d w`. -/
theorem cycle_rep_with_boundary
    {R : Type} [Ring R] {K L : ChainComplex (ModuleCat R) ℕ} (φ : K ⟶ L) (j : ℕ) :
    ∀ (α : K.homology j),
      ConcreteCategory.hom (HomologicalComplex.homologyMap φ j) α = 0 →
      ∃ (c : K.cycles j),
        ConcreteCategory.hom (K.homologyπ j) c = α ∧
        ConcreteCategory.hom (K.d j (j - 1)) (ConcreteCategory.hom (K.iCycles j) c) = 0 ∧
        ∃ w : L.X (j + 1),
          ConcreteCategory.hom (φ.f j) (ConcreteCategory.hom (K.iCycles j) c) =
            ConcreteCategory.hom (L.d (j + 1) j) w := by
  intro α hα
  have h_surj := homology_pi_surjective j α
  obtain ⟨c, hc⟩ := h_surj
  have h_id : ConcreteCategory.hom (K.d j (j - 1)) (ConcreteCategory.hom (K.iCycles j) c) = 0 := by
    have h := HomologicalComplex.iCycles_d K j (j - 1)
    rw [← ConcreteCategory.comp_apply, h]
    simp
  have h_bound := image_boundary_of_homologyMap_eq_zero φ j c
  refine ⟨c, hc, h_id, ?_⟩
  apply h_bound
  rw [hc]
  exact hα

/-- Injectivity of `homologyMap φ j` from an element-level cycle-descent hypothesis:
reduce to kernel-triviality (`injective_iff_map_eq_zero`), represent a killed class by a
cycle `c` whose `φ`-image bounds in `L` (`cycle_rep_with_boundary`), descend the boundary to
`K` via `hdesc`, and conclude `homologyπ c = 0` via `homology_pi_zero_of_boundary`. -/
theorem homology_map_injective_of_cycle_descent
    {R : Type} [Ring R] {K L : ChainComplex (ModuleCat R) ℕ} (φ : K ⟶ L) (j : ℕ)
    (hdesc : ∀ z : K.X j,
        (ConcreteCategory.hom (K.d j (j - 1))) z = 0 →
        (∃ w : L.X (j + 1),
          (ConcreteCategory.hom (φ.f j)) z = (ConcreteCategory.hom (L.d (j + 1) j)) w) →
        ∃ w' : K.X (j + 1),
          z = (ConcreteCategory.hom (K.d (j + 1) j)) w') :
    Function.Injective
      ⇑(ConcreteCategory.hom (HomologicalComplex.homologyMap φ j)) := by
  rw [injective_iff_map_eq_zero]
  intro α hα
  obtain ⟨c, hc, hz, w, hw⟩ := cycle_rep_with_boundary φ j α hα
  obtain ⟨w', hw'⟩ := hdesc (ConcreteCategory.hom (K.iCycles j) c) hz ⟨w, hw⟩
  rw [← hc]
  exact homology_pi_zero_of_boundary j c w' hw'

/-- Mono half of the small-simplices quasi-iso, via a clean cleave of the categorical
homology reasoning (`homology_map_injective_of_cycle_descent`, reducing
`Injective (homologyMap φ i)` to an element-level cycle-descent hypothesis) from the
concrete differential bookkeeping (`incl_cycle_descent`, fed by the topological descent
fact `hbd`). -/
theorem homology_mono_of_boundary_descent
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (i : ℕ)
    (hbd : ∀ (n : ℕ) (z : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
        (w : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R),
        z ∈ (Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
            Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}) →
        z = (∑ j : Fin (n + 2), (-1 : ℤ) ^ (j : ℕ)
            • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ j)) w →
        ∃ w' : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R,
          w' ∈ (Finsupp.supported R R
                {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
                  Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ A} ⊔
              Finsupp.supported R R
                {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
                  Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ B}) ∧
            z = (∑ j : Fin (n + 2), (-1 : ℤ) ^ (j : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ j)) w') :
    Function.Injective
      ⇑(ConcreteCategory.hom (HomologicalComplex.homologyMap
        (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
          (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) i)) := by
  apply homology_map_injective_of_cycle_descent
  intro z hz hbound
  exact incl_cycle_descent hA hB hAB i hbd z hz hbound

/-- Mono half of the small-simplices quasi-iso: `Mono (homologyMap incl i)` in `ModuleCat R`
is equivalent to injectivity, and the whole topological content — a small `n`-chain that
bounds in `C(X)` already bounds by a *small* `(n + 1)`-chain — is
`singular_small_boundary_small`, fed through the homological-algebra bridge
`homology_mono_of_boundary_descent`. -/
theorem homology_incl_mono
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (i : ℕ) :
    Mono (HomologicalComplex.homologyMap
      (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) i) := by
  rw [ModuleCat.mono_iff_injective]
  refine homology_mono_of_boundary_descent hA hB hAB i ?_
  intro n z w hz hzw
  exact singular_small_boundary_small hA hB hAB n z w hz hzw

/-- The inclusion of the small-simplices subcomplex `C(A) + C(B)` into the full singular chain
complex `C(X)` is a quasi-isomorphism: degreewise, `homologyMap` is an isomorphism since
`ModuleCat R` is balanced, split into homology injectivity (`homology_incl_mono`, from
`singular_small_boundary_small`) and homology surjectivity (`homology_incl_epi`, from
`singular_small_cycle_homologous`). -/
theorem mv_incl_quasi_iso {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) :
    QuasiIso (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) := by
  rw [quasiIso_iff]
  intro i
  rw [quasiIsoAt_iff_isIso_homologyMap]
  have hmono := homology_incl_mono (R := R) (X := X) hA hB hAB i
  have hepi := homology_incl_epi (R := R) (X := X) hA hB hAB i
  exact isIso_of_mono_of_epi _

/-- Exactness of the **Mayer–Vietoris long exact sequence** at `H_n(C(A) ⊕ C(B))`, the middle
spot, with the third term transported along the small-simplices quasi-iso to `H_n(C(X))`. Base
exactness is `mv_short_complex_short_exact.homology_exact₂ n` (the snake-lemma LES);
post-composing `g` with the iso `homologyMap incl n` (an iso by `mv_incl_quasi_iso`) is absorbed
by `ShortComplex.exact_of_iso` through the identity/`isoOfQuasiIsoAt` `isoMk`. -/
theorem mv_les_exact_pair {R : Type} [Ring R] {X : TopCat.{0}}
    {A B : Set X} (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ) :
    (CategoryTheory.ShortComplex.mk
      (HomologicalComplex.homologyMap
        (mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).f n)
      (HomologicalComplex.homologyMap
        (mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).g n
        ≫ HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) n)
      (by
        rw [← CategoryTheory.Category.assoc, ← HomologicalComplex.homologyMap_comp,
          (mv_short_complex (R := R) (TopCat.toSSet.obj X)
            (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).zero,
          HomologicalComplex.homologyMap_zero, CategoryTheory.Limits.zero_comp])).Exact := by
  haveI hq : QuasiIsoAt (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) n :=
    (mv_incl_quasi_iso (R := R) (X := X) hA hB hAB).quasiIsoAt n
  have hSE := mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
    (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)
  refine ShortComplex.exact_of_iso ?_ (hSE.homology_exact₂ n)
  exact ShortComplex.isoMk (Iso.refl _) (Iso.refl _)
    (isoOfQuasiIsoAt (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) n)
    (by simp [mv_short_complex]) (by simp [mv_short_complex])

/-- Exactness of the **Mayer–Vietoris long exact sequence** at `H_n(C(A ∩ B))`, the
connecting-map spot, with the source `H_{n+1}` transported along the small-simplices quasi-iso
to `H_{n+1}(C(X))`. Base exactness is
`mv_short_complex_short_exact.homology_exact₁ (n+1) n rfl` (the snake-lemma LES);
pre-composing the connecting map `δ` with `inv (homologyMap incl (n+1))` (an iso, by
`QuasiIso`) is absorbed by `ShortComplex.exact_of_iso` through the `isoOfQuasiIsoAt`/identity
`isoMk`. -/
theorem mv_les_exact_inter {R : Type} [Ring R] {X : TopCat.{0}}
    {A B : Set X} (_hA : IsOpen A) (_hB : IsOpen B) (_hAB : A ∪ B = Set.univ) (n : ℕ)
    [inst : QuasiIso (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))] :
    (ShortComplex.mk
      (inv (HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
            (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
          (n + 1))
        ≫ (mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
            (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).δ (n + 1) n rfl)
      (HomologicalComplex.homologyMap
        (mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).f n)
      (by
        simp only [Category.assoc]
        exact IsIso.eq_inv_comp _ |>.mp
          ((mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A)
              (singular_subcomplex_of_set X B)).δ_comp (n + 1) n rfl))).Exact := by
  have hSE := mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
    (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)
  refine ShortComplex.exact_of_iso ?_ (hSE.homology_exact₁ (n + 1) n rfl)
  exact ShortComplex.isoMk
    (isoOfQuasiIsoAt (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) (n + 1))
    (Iso.refl _) (Iso.refl _)
    (by
      simp only [isoOfQuasiIsoAt_hom, Iso.refl_hom, Category.comp_id]
      erw [IsIso.hom_inv_id_assoc])
    (by simp [mv_short_complex])

/-- The degreewise isomorphism identifying `supported_chain_complex X ⊤` with mathlib's
`X.chainComplex`: `⊤.obj = univ` gives `Finsupp.supported R R _ = ⊤` (`Finsupp.supported_univ`),
so `Submodule.topEquiv` identifies the `⊤`-supported piece with the whole module, and
`chain_complex_x_iso_finsupp.symm` transports back to `X.chainComplex`. -/
noncomputable def chain_complex_top_iso_x {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) :
    (supported_chain_complex (R := R) X ⊤).X n ≅ (X.chainComplex (ModuleCat.of R R)).X n := by
  have h : Finsupp.supported R R ((⊤ : X.Subcomplex).obj (Opposite.op ⦋n⦌)) = ⊤ := by
    rw [CategoryTheory.Subfunctor.top_obj, Set.top_eq_univ, Finsupp.supported_univ]
  exact (LinearEquiv.ofEq _ _ h ≪≫ₗ Submodule.topEquiv).toModuleIso ≪≫
    (chain_complex_x_iso_finsupp X n).symm

/-- The isomorphisms `chain_complex_top_iso_x` commute with the differentials: unfold
`chain_complex_top_iso_x` to `topEquiv/ofEq ≪≫ chain_complex_x_iso_finsupp.symm` (via `hcomp`),
reduce the differential of `supported_chain_complex X ⊤` to the transported-differential
restriction (`ChainComplex.of_d`), and cancel the resulting `chain_complex_x_iso_finsupp`
conjugation via `Iso.hom_inv_id` on the underlying element. -/
theorem chain_complex_top_iso_comm {R : Type u} [Ring R] (X : SSet.{u}) :
    ∀ (i j : ℕ), (ComplexShape.down ℕ).Rel i j →
      (chain_complex_top_iso_x (R := R) X i).hom ≫ (X.chainComplex (ModuleCat.of R R)).d i j
        = (supported_chain_complex (R := R) X ⊤).d i j
            ≫ (chain_complex_top_iso_x (R := R) X j).hom := by
  have hcomp : ∀ (n : ℕ) (v : X _⦋n⦌ →₀ R)
      (hv : v ∈ Finsupp.supported R R ((⊤ : X.Subcomplex).obj (Opposite.op ⦋n⦌))),
      ModuleCat.Hom.hom (chain_complex_top_iso_x (R := R) X n).hom ⟨v, hv⟩
        = ModuleCat.Hom.hom (chain_complex_x_iso_finsupp (R := R) X n).inv v := by
    intro n v hv
    simp only [chain_complex_top_iso_x, Iso.trans_hom, Iso.symm_hom, ModuleCat.hom_comp,
      LinearEquiv.toModuleIso_hom, LinearMap.comp_apply]
    rfl
  intro i j hij
  obtain rfl : i = j + 1 := hij.symm
  apply ModuleCat.hom_ext
  apply LinearMap.ext
  intro y
  simp only [supported_chain_complex]
  rw [ChainComplex.of_d]
  obtain ⟨x, hx⟩ := y
  have hcancel : ∀ z : (X.chainComplex (ModuleCat.of R R)).X j,
      ModuleCat.Hom.hom (chain_complex_x_iso_finsupp (R := R) X j).inv
          (ModuleCat.Hom.hom (chain_complex_x_iso_finsupp (R := R) X j).hom z) = z := by
    intro z
    have h2 : ModuleCat.Hom.hom
        ((chain_complex_x_iso_finsupp (R := R) X j).hom
          ≫ (chain_complex_x_iso_finsupp (R := R) X j).inv) z = z := by
      rw [Iso.hom_inv_id]; rfl
    simp
  change
      ModuleCat.Hom.hom ((X.chainComplex (ModuleCat.of R R)).d (j + 1) j)
        (ModuleCat.Hom.hom (chain_complex_top_iso_x (R := R) X (j + 1)).hom ⟨x, hx⟩)
      = ModuleCat.Hom.hom (chain_complex_top_iso_x (R := R) X j).hom
          (⟨ModuleCat.Hom.hom
              ((chain_complex_x_iso_finsupp (R := R) X (j + 1)).inv
                ≫ (X.chainComplex (ModuleCat.of R R)).d (j + 1) j
                ≫ (chain_complex_x_iso_finsupp (R := R) X j).hom)
              x,
            supported_d_stable X ⊤ j (Submodule.mem_map_of_mem hx)⟩ :
            Finsupp.supported R R ((⊤ : X.Subcomplex).obj (Opposite.op ⦋j⦌)))
  rw [hcomp, hcomp]
  simp only [ModuleCat.hom_comp, LinearMap.comp_apply]
  rw [hcancel]

/-- Identify `supported_chain_complex X ⊤` with mathlib's `X.chainComplex` via
`HomologicalComplex.Hom.isoOfComponents`, from the degreewise isomorphism
`chain_complex_top_iso_x` and the commuting squares `chain_complex_top_iso_comm`. -/
noncomputable def chain_complex_top_iso {R : Type u} [Ring R] (X : SSet.{u}) :
    supported_chain_complex (R := R) X ⊤ ≅ X.chainComplex (ModuleCat.of R R) :=
  HomologicalComplex.Hom.isoOfComponents
    (fun n => chain_complex_top_iso_x (R := R) X n)
    (chain_complex_top_iso_comm (R := R) X)

/-- The Mayer–Vietoris connecting homomorphism `H_{n+1}(C(X)) ⟶ H_n(C(A ∩ B))`: the snake-lemma
connecting map `δ` of `mv_short_complex_short_exact`, precomposed with the inverse of the
small-simplices quasi-isomorphism to transport its source from `H_{n+1}(C(A) + C(B))` to
`H_{n+1}(C(X))`. -/
noncomputable def mv_delta {R : Type} [Ring R] {X : TopCat.{0}}
    {A B : Set X} (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ) :=
  haveI : IsIso (HomologicalComplex.homologyMap
      (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
      (n + 1)) :=
    (quasiIsoAt_iff_isIso_homologyMap _ (n + 1)).mp
      ((mv_incl_quasi_iso (R := R) (X := X) hA hB hAB).quasiIsoAt (n + 1))
  inv (HomologicalComplex.homologyMap
      (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
      (n + 1))
    ≫ (mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
        (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).δ (n + 1) n rfl

/-- Exactness of the **Mayer–Vietoris long exact sequence** at `H_{n+1}(C(X))`, the third spot:
the composite `H_{n+1}(C(A) ⊕ C(B)) ⟶ H_{n+1}(C(X)) ⟶ H_n(C(A ∩ B))` (via `mv_delta`) is exact,
transported from the snake-lemma exactness `mv_short_complex_short_exact.homology_exact₃` along
the small-simplices quasi-isomorphism. -/
theorem mv_les_exact_total {R : Type} [Ring R] {X : TopCat.{0}}
    {A B : Set X} (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ) :
    (CategoryTheory.ShortComplex.mk
      (HomologicalComplex.homologyMap
          (mv_short_complex (R := R) (TopCat.toSSet.obj X)
            (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).g (n + 1)
        ≫ HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
            (n + 1))
      (mv_delta hA hB hAB n)
      (by
        have hqi := mv_incl_quasi_iso (R := R) hA hB hAB
        haveI _hiso : IsIso (HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
              (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
            (n + 1)) :=
          (quasiIsoAt_iff_isIso_homologyMap _ (n + 1)).mp inferInstance
        have e2 : HomologicalComplex.homologyMap
              (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
                (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
              (n + 1)
            ≫ mv_delta hA hB hAB n
            = (mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
                (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).δ (n + 1) n
                rfl :=
          IsIso.hom_inv_id_assoc _ _
        have e3 : HomologicalComplex.homologyMap
              (mv_short_complex (R := R) (TopCat.toSSet.obj X)
                (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).g (n + 1)
            ≫ (mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
                (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).δ (n + 1) n rfl
            = 0 :=
          (mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
            (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).comp_δ (n + 1) n rfl
        exact (Category.assoc _ _ _).trans
          ((congrArg (CategoryStruct.comp (HomologicalComplex.homologyMap
            (mv_short_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A)
              (singular_subcomplex_of_set X B)).g (n + 1))) e2).trans
            e3))).Exact := by
  haveI hq : QuasiIsoAt (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) (n + 1) :=
    (mv_incl_quasi_iso (R := R) (X := X) hA hB hAB).quasiIsoAt (n + 1)
  haveI hiso : IsIso (HomologicalComplex.homologyMap
      (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
      (n + 1)) :=
    (quasiIsoAt_iff_isIso_homologyMap _ (n + 1)).mp hq
  have e2 : HomologicalComplex.homologyMap
        (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
          (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
        (n + 1)
      ≫ mv_delta hA hB hAB n
      = (mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).δ (n + 1) n rfl :=
    IsIso.hom_inv_id_assoc _ _
  refine ShortComplex.exact_of_iso ?_
    ((mv_short_complex_short_exact (R := R) (TopCat.toSSet.obj X)
        (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).homology_exact₃
        (n + 1) n rfl)
  refine ShortComplex.isoMk (Iso.refl _)
    (isoOfQuasiIsoAt (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
        (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤))
      (n + 1))
    (Iso.refl _) ?_ ?_
  · exact Category.id_comp _
  · simp only [Iso.refl_hom, Category.comp_id]
    exact e2

end Library.AlgebraicTopology.MayerVietoris.LongExactSequence
