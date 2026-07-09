/-
  Defs.lean — Stokes' theorem on a smooth manifold-with-boundary (abstract version).

  USER-OWNED vocabulary (the framework treats this file as ground truth). The
  deferred theorems are STANDALONE NAMED lemmas (§A.1–A.4, §A.6) that lift out
  verbatim as the `root` of a separate framework problem. ONE exception:
  `mextDeriv`'s smoothness witness (§A.5) is still an inline structure-field
  `sorry` — see its note for the `T%`-elaborator reason and the lift recipe.
  The operator owns the SHAPE of each definition.

  Soundness boundary: the gates check sorry-freeness + axiom whitelist, so a clean
  proof of `stokes` is only possible once every deferred lemma is discharged. What
  the gates CANNOT catch is a wrong definition *shape* — so the audit you own is
  the shapes flagged `AUDIT`, not the proofs.

  ORIENTATION (resolved at definition level via a reference form): summing
  `topCoeff` (standard-basis coefficient) over charts with no sign would be wrong
  even for an oriented `M` — each term needs a per-chart sign `±1`, and it is NOT
  a global constant (e.g. `[0,1]`: the two endpoint charts overlap with transition
  `x ↦ 1−x`, det = −1, so no positive-det oriented atlas exists; they must carry
  opposite signs). So `integralForm`/`integralBoundary` take a reference top form
  `μ` and weight each chart term by `sign (localCoeff μ)` (boundary: the induced
  `−sign`). `μ` nowhere-zero is the orientation hypothesis, bundled in the
  `[OrientedManifold]` instance as `refForm_ne`; the
  result's independence of the covering is the deferred §B obligation. The `[0,1]`
  check now gives `integralBoundary = f(1)−f(0) = integralForm (df)`.

  ── what mathlib already gives ──────────────────────────────────────────────
  mathlib HAS the exterior derivative on a normed space
  (`Analysis/Calculus/DifferentialForm/Basic.lean`: `extDeriv`/`extDerivWithin`,
  with `d∘d=0` and linearity) but lists differential forms ON MANIFOLDS as TODO.
  The naive `M → (E [⋀^Fin k]→L[ℝ] ℝ)` map is the TRIVIALISED view; it ignores
  `tangentCoordChange`, hence is only a genuine form when `TM` is trivial. This
  file supplies the missing manifold layer (forms as bundle sections + d + ∫).

  ── build status (all compile-verified) ─────────────────────────────────────
  §1 `formBundleCore`/`DiffForm`, §2 `mextDeriv`, §3 `integralForm`/
  `integralBoundary`, §4 `stokes` statement — every DEFINITION is genuine,
  sorry-free DATA. Remaining `sorry`s: §A (differential-side obligations) + the
  `stokes` root itself. The integration defs carry NO sorry; their analytic
  well-definedness (§B notes) is work the `stokes` proof needs, not a separate
  file-level sorry.
-/
import Mathlib

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_theorem

/-! ## §1 — the `⋀ᵏ T*M` bundle (general `k`)

    `coordChange` = the tangent core's transitions pushed through the
    contravariant alternating-precomposition functor. DATA genuine; the three
    coherence facts are deferred named lemmas (§A.1–A.3).
    AUDIT: contravariance ⇒ `formCoordChange i j` precomposes by the tangent
    transition `j i` (the swap is the only "shape" choice here). -/

section FormBundle

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- Transition map of `⋀ᵏ T*M`: precompose alternating maps by the (swapped)
    tangent transition. -/
noncomputable def formCoordChange (k : ℕ) (i j : atlas H M) (x : M) :
    (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] (E [⋀^Fin k]→L[ℝ] ℝ) :=
  ContinuousAlternatingMap.compContinuousLinearMapCLM
    ((tangentBundleCore I M).coordChange j i x)

/-- §A.1 DEFERRED (→ root): transitions fix the fibre on a self-overlap.
    Proof: tangent `coordChange_self` ⇒ inner map is `id`, and precomposition by
    `id` is `id`. -/
lemma formCoordChange_self (k : ℕ) :
    ∀ i, ∀ x ∈ (tangentBundleCore I M).baseSet i, ∀ v,
      formCoordChange (M := M) I k i i x v = v :=
  sorry

/-- §A.2 DEFERRED (→ root): transitions are continuous on the overlap.
    Proof: tangent `continuousOn_coordChange` composed with continuity of the
    precomposition functor `compContinuousLinearMapCLM`. -/
lemma formCoordChange_continuousOn (k : ℕ) :
    ∀ i j, ContinuousOn (formCoordChange (M := M) I k i j)
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j) :=
  sorry

/-- §A.3 DEFERRED (→ root): the cocycle condition.
    Proof: tangent cocycle at `(k,j,i)` (i.e. `τ_kj ∘ τ_ji = τ_ki`) + the
    contravariant functoriality `pre(g) ∘ pre(h) = pre(h ∘ g)`. -/
lemma formCoordChange_comp (k : ℕ) :
    ∀ i j l, ∀ x ∈ (tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j
        ∩ (tangentBundleCore I M).baseSet l, ∀ v,
      formCoordChange (M := M) I k j l x (formCoordChange (M := M) I k i j x v)
        = formCoordChange (M := M) I k i l x v :=
  sorry

/-- The vector-bundle core of `⋀ᵏ T*M`. -/
noncomputable def formBundleCore (k : ℕ) :
    VectorBundleCore ℝ M (E [⋀^Fin k]→L[ℝ] ℝ) (atlas H M) where
  baseSet i := (tangentBundleCore I M).baseSet i
  isOpen_baseSet i := (tangentBundleCore I M).isOpen_baseSet i
  indexAt := (tangentBundleCore I M).indexAt
  mem_baseSet_at := (tangentBundleCore I M).mem_baseSet_at
  coordChange := formCoordChange I k
  coordChange_self := formCoordChange_self I k
  continuousOn_coordChange := formCoordChange_continuousOn I k
  coordChange_comp := formCoordChange_comp I k

/-- Fibre- and vector-bundle instances for `⋀ᵏ T*M`, declared on the exact
    `.Fiber` expression via the core's accessors (search won't unfold the def to
    fire the global `VectorBundleCore` instances; the `T%` section elaborator and
    `Trivialization.IsLinear` need them present — mirrors `TangentSpace.fiberBundle`). -/
noncomputable instance instFormFiberBundle (k : ℕ) :
    FiberBundle (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber :=
  (formBundleCore (M := M) I k).fiberBundle

noncomputable instance instFormVectorBundle (k : ℕ) :
    VectorBundle ℝ (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber :=
  (formBundleCore (M := M) I k).vectorBundle

/-- §A.4 DEFERRED (→ root): the `⋀ᵏ T*M` core has `C^∞` transition functions. -/
lemma formBundleCore_isContMDiff (k : ℕ) :
    (formBundleCore (M := M) I k).IsContMDiff I ∞ :=
  sorry

/-- Smooth-vector-bundle instance for `⋀ᵏ T*M` (from the core + §A.4). -/
noncomputable instance instFormBundleContMDiff (k : ℕ) :
    ContMDiffVectorBundle ∞ (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber I := by
  haveI := formBundleCore_isContMDiff (M := M) I k
  exact (formBundleCore (M := M) I k).instContMDiffVectorBundle

/-- A smooth differential `k`-form on `M`: a `C^∞` section of `⋀ᵏ T*M`.
    Correct for a general manifold (genuine bundle section, not trivialised).
    `I` and `M` are EXPLICIT (mathlib idiom for bundle/section type-formers, cf.
    `TangentBundle I M`): `M` is not inferable from `DiffForm I k`, so explicit
    args replace the `(M := …)` noise at every use site. -/
abbrev DiffForm (I : ModelWithCorners ℝ E H) (M : Type*) [TopologicalSpace M]
    [ChartedSpace H M] [IsManifold I ∞ M] (k : ℕ) : Type _ :=
  Cₛ^∞⟮I; (E [⋀^Fin k]→L[ℝ] ℝ), (formBundleCore (M := M) I k).Fiber⟯

end FormBundle

/-! ## §2 — exterior derivative `mextDeriv : DiffForm k → DiffForm (k+1)`

    Chart-transport of mathlib's normed-space `extDerivWithin`: read φ's coordinate
    rep near `x` via the bundle trivialisation, apply the model `extDerivWithin` on
    `range I` at `extChartAt I x x`, transport the result back into the fibre.
    DATA genuine (trivialisation-aware). Smoothness is §A.5; the correctness that
    this construction is chart-independent (hence the genuine `d`) is exercised by
    the deferred `mextDeriv_dd` (`d∘d = 0`), §A.6.
    AUDIT: extChartAt + trivialisation + `extDerivWithin (range I)` is the
    "manifold d" shape; `range I` gives the correct one-sided derivative at ∂.
    Named `mextDeriv` (not `extDeriv`) to avoid clashing with mathlib's
    normed-space `extDeriv` when a sub-problem opens both namespaces. -/

section ExtDeriv

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- Coordinate representative of a `k`-form near `x`: `E → (E[⋀^k]→L ℝ)`. -/
noncomputable def formInCoord {k : ℕ} (φ : DiffForm I M k) (x : M) :
    E → (E [⋀^Fin k]→L[ℝ] ℝ) :=
  fun y =>
    let p := (extChartAt I x).symm y
    Trivialization.continuousLinearMapAt ℝ
      (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x) p (φ p)

/-- Underlying (raw) section function of the exterior derivative. -/
noncomputable def mextDerivFun {k : ℕ} (φ : DiffForm I M k) (x : M) :
    (formBundleCore (M := M) I (k + 1)).Fiber x :=
  Trivialization.symmL ℝ
    (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ) (formBundleCore (M := M) I (k + 1)).Fiber x) x
    (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))

/-- The exterior derivative of a smooth `k`-form.

    §A.5 DEFERRED (smoothness, INLINE): `contMDiff_toFun` is an inline `sorry` —
    the one obligation not yet a standalone liftable lemma. Stating
    `CMDiff ∞ (T% (mextDerivFun I φ))` *outside* the structure trips the `T%`
    elaborator's FiberBundle search (inside the field it resolves via the
    structure's expected type). To lift it, restate that `CMDiff` goal as the root
    with `instFormFiberBundle`/`instFormVectorBundle` in scope. -/
noncomputable def mextDeriv {k : ℕ} (φ : DiffForm I M k) :
    DiffForm I M (k + 1) where
  toFun := mextDerivFun I φ
  contMDiff_toFun := sorry

/-- §A.6 DEFERRED (→ root): `d ∘ d = 0`. A NECESSARY (not sufficient) correctness
    check on the chart-transport construction — the genuine exterior derivative
    satisfies it, so a construction failing it is definitely wrong. Provability
    here relies on the construction being chart-independent. -/
lemma mextDeriv_dd {k : ℕ} (φ : DiffForm I M k) :
    mextDeriv (M := M) I (mextDeriv (M := M) I φ) = 0 :=
  sorry

end ExtDeriv

/-! ## §3 — integration of a top form over an oriented manifold (GENERAL `∫_N`)

    The canonical operator: `DiffForm.integral` of a top `d`-form over an oriented
    compact `d`-manifold `N` modelled on `EuclideanSpace ℝ (Fin d)` — for ANY model
    `I` (with or without boundary). A top alternating form on the model is
    determined by its value on the standard basis (`topCoeff`); `∫_N` is the
    partition-of-unity sum of that coefficient, weighted by the per-chart
    orientation sign read from the orientation's reference form `μ`. Both `∫_M`
    (M with boundary) and `∫_∂M` (boundaryless ∂M) are THIS one operator,
    instantiated at different `(I, N)`. -/

open MeasureTheory

/-- An **orientation** of a manifold `N` modelled on `EuclideanSpace ℝ (Fin d)`: a
    chosen nowhere-zero reference top `d`-form. A manifold is orientable iff such a
    form exists; choosing one orients it. General over the model `I`, so the SAME
    class serves both `M` (`𝓡∂ (n+1)`) and its boundary
    (`𝓘(ℝ, EuclideanSpace (Fin n))`). The linear-algebra foundation is mathlib's
    `Module.Oriented`/`Orientation`; we use the equivalent nowhere-zero-top-form
    presentation, which is what `∫_N` integrates against. -/
class OrientedManifold {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    (I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH)
    (N : Type*) [TopologicalSpace N] [ChartedSpace EH N] [IsManifold I ∞ N] where
  /-- The chosen nowhere-zero reference top form orienting `N`. -/
  refForm : DiffForm I N d
  /-- The reference form vanishes nowhere — i.e. it is a genuine orientation. -/
  refForm_ne : ∀ x : N, refForm x ≠ 0

section Integration

variable {d : ℕ} {EH : Type*} [TopologicalSpace EH]
  {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
  {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
  [IsManifold I ∞ N] [CompactSpace N]

/-- Coefficient of a top alternating form in standard coordinates: its value on the
    standard orthonormal basis of `EuclideanSpace ℝ (Fin d)`. -/
noncomputable def topCoeff
    (α : EuclideanSpace ℝ (Fin d) [⋀^Fin d]→L[ℝ] ℝ) : ℝ :=
  α (EuclideanSpace.basisFun (Fin d) ℝ)

/-- Local scalar density of a top form `φ` in the chart at `x`: the coefficient of
    its coordinate representative — the function `∫_N` integrates against Lebesgue
    measure (localised by a partition of unity). -/
noncomputable def localCoeff (φ : DiffForm I N d) (x : N) :
    EuclideanSpace ℝ (Fin d) → ℝ :=
  fun y => topCoeff (formInCoord I φ x y)

/-- `∫_N φ` — the integral of a top `d`-form `φ` over the oriented compact manifold
    `N`. Partition-of-unity sum of the chart-localised coefficient, **weighted by
    the per-chart orientation sign `sign (localCoeff μ)`** read from the
    `[OrientedManifold]` reference form `μ` (consistent across charts; `[0,1]`
    yields `f(1)−f(0)`). THE canonical integration operator — both sides of Stokes
    use it. DATA genuine; chart-independence of the result (given `μ` nowhere-zero)
    is the deferred obligation §B.1.

    Named `DiffForm.integral` (usable as `φ.integral`), per mathlib's convention of
    namespacing operations under the type. -/
noncomputable def DiffForm.integral [OrientedManifold I N] (φ : DiffForm I N d) : ℝ :=
  let μ := OrientedManifold.refForm (I := I) (N := N)
  -- `Classical.choose` (not `obtain`/`cases`, which cannot eliminate `∃ : Prop`
  -- into data) extracts the index type + bump covering subordinate to the charts.
  let h := SmoothBumpCovering.exists_isSubordinate
    (I := I) (M := N) (s := Set.univ) isClosed_univ
    (U := fun x => (chartAt EH x).source)
    (fun x _ => (chartAt EH x).open_source.mem_nhds (mem_chart_source _ x))
  let B := h.choose_spec.choose
  -- Integrate over the chart TARGET only: off-target `(extChartAt _).symm` is junk
  -- (can land back in the source, giving a spurious `ρ_i > 0` term). On the target
  -- it is the genuine inverse and `ρ_i`'s support (⊆ source) is captured exactly.
  ∑ᶠ i, ∫ y in (extChartAt I (B.c i)).target,
    B.toSmoothPartitionOfUnity i ((extChartAt I (B.c i)).symm y)
      * localCoeff φ (B.c i) y
      * Real.sign (localCoeff μ (B.c i) y) ∂volume

end Integration

/-! ## §3' — the boundary face embedding `faceEmbed`

    Used by `∂M`'s charts (§5) and by `ι*`'s differential `dι` (`faceEmbedL`, §5).
    Places the face `EuclideanSpace ℝ (Fin n)` into coordinates `1..n` of the model
    `{x₀ = 0}` (coordinate 0 is the normal). -/

section Boundary

variable {n : ℕ}

/-- Embed the boundary face `EuclideanSpace ℝ (Fin n)` into the model half-space as
    `{x₀ = 0}` (coordinate 0 is the inward normal): place `z` in coordinates `1..n`. -/
noncomputable def faceEmbed (z : EuclideanSpace ℝ (Fin n)) : EuclideanSpace ℝ (Fin (n + 1)) :=
  ∑ i : Fin n, z i • EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ

end Boundary

/-! ## §5 — the boundary `∂M` as an oriented `n`-manifold (step 3)

    `∂M` packaged as a boundaryless `C^∞` `n`-manifold modelled on
    `EuclideanSpace ℝ (Fin n)`. Charts = `M`'s boundary charts restricted to the
    face `{x₀=0}` and projected via `faceProj` (the left inverse of `faceEmbed`).
    DATA genuine; the `OpenPartialHomeomorph`/`ChartedSpace`/`IsManifold` coherence
    is deferred (structure-field `sorry`s — unavoidable for a from-scratch charted
    space; this is the mathlib-wishlist boundary-manifold construction). -/

section BoundaryManifold

variable {n : ℕ}
  {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
  [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The boundary `∂M` as a subtype of `M`. -/
def Bdry (n : ℕ) (M : Type*) [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M] : Type _ :=
  {x : M // x ∈ (𝓡∂ (n + 1)).boundary M}

instance : TopologicalSpace (Bdry n M) :=
  inferInstanceAs (TopologicalSpace {x : M // x ∈ (𝓡∂ (n + 1)).boundary M})

/-- The inclusion `∂M ↪ M` (used by `ι*`). -/
def bdryIncl (p : Bdry n M) : M := p.val

/-- Drop coordinate `0` (the normal direction): the left inverse of `faceEmbed`,
    projecting the model onto the boundary face `EuclideanSpace ℝ (Fin n)`. -/
noncomputable def faceProj (w : EuclideanSpace ℝ (Fin (n + 1))) : EuclideanSpace ℝ (Fin n) :=
  (EuclideanSpace.equiv (Fin n) ℝ).symm (fun i => w i.succ)

/-- Chart of `∂M` at `p`: `M`'s extended chart at `p`, restricted to `∂M` and
    projected to the face. DATA genuine; partial-homeomorphism coherence (and the
    boundary-membership of `invFun`) deferred. -/
noncomputable def bdryChart (p : Bdry n M) :
    OpenPartialHomeomorph (Bdry n M) (EuclideanSpace ℝ (Fin n)) where
  toFun q := faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val)
  -- GUARDED: `invFun` is total, so its `Bdry`-membership proof must hold for EVERY
  -- `z`. Off-target, `(extChartAt _).symm` is "extra useless data" (mathlib's
  -- `PartialEquiv` doc) — junk not in the boundary, so an unguarded `⟨…, _⟩` makes
  -- the membership a FALSE ∀z obligation. The dependent guard sends off-target `z`
  -- to the boundary point `p`; on-target the hypothesis `h` makes the membership
  -- genuinely provable. (Mirrors the §A target ∩ face fix.)
  invFun z :=
    haveI : Decidable (faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target) :=
      Classical.propDecidable _
    if h : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target then
      ⟨(extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z), sorry⟩
    else p
  source := Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).source
  -- Intersect with the face `{w₀ = 0}` BEFORE projecting: `faceProj` of an interior
  -- point `w` (`w₀ > 0`) would land a `z` whose `faceEmbed z = (0, w₁..wₙ) ∉ target`,
  -- so `invFun z` is junk and `left/right_inv'` would be FALSE. Restricting to the
  -- face makes `faceEmbed ∘ faceProj = id` there, and `open_target` provable (the
  -- face slice is open in the face subspace, `faceProj` a homeo on it).
  target := faceProj '' ((extChartAt (𝓡∂ (n + 1)) p.val).target ∩
    {w : EuclideanSpace ℝ (Fin (n + 1)) | w 0 = 0})
  map_source' := sorry
  map_target' := sorry
  left_inv' := sorry
  right_inv' := sorry
  open_source := sorry
  open_target := sorry
  continuousOn_toFun := sorry
  continuousOn_invFun := sorry

/-- `∂M` is a charted space over `EuclideanSpace ℝ (Fin n)` (induced from `M`). -/
noncomputable instance : ChartedSpace (EuclideanSpace ℝ (Fin n)) (Bdry n M) where
  atlas := Set.range bdryChart
  chartAt p := bdryChart p
  mem_chart_source p := sorry
  chart_mem_atlas p := ⟨p, rfl⟩

/-- DEFERRED (→ root): `∂M` is a `C^∞` manifold (without boundary), modelled on
    `EuclideanSpace ℝ (Fin n)` — the induced smooth structure (transition maps are
    `M`'s boundary-chart transitions restricted to the face). -/
instance instBdryManifold : IsManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) ∞ (Bdry n M) :=
  sorry

/-! ### `ι*` — pullback of forms along the inclusion `ι : ∂M ↪ M` (step 4)

    The differential `dι` in boundary-adapted coordinates is the CONSTANT linear
    face embedding `faceEmbedL` (because `ι` becomes `faceEmbed` in the charts, and
    `faceEmbed` is linear) — so `ι*` needs no `mfderiv`, just precomposition by
    `faceEmbedL`. This is the clean closed form of `ι*` for the boundary inclusion. -/

/-- `dι` in coordinates: the linear face embedding placing `EuclideanSpace ℝ (Fin n)`
    in coordinates `1..n` of `EuclideanSpace ℝ (Fin (n+1))`. -/
noncomputable def faceEmbedL :
    EuclideanSpace ℝ (Fin n) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)) :=
  ∑ i : Fin n, (EuclideanSpace.proj i).smulRight (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ)

/-- Raw section of `∂M`'s form bundle for the pullback `ι* φ` at `p`: precompose
    `φ`'s coordinate rep at `ι p` by `faceEmbedL` (= `dι`), transport into the
    fibre. -/
noncomputable def pullbackBdryFun (φ : DiffForm (𝓡∂ (n + 1)) M n) (p : Bdry n M) :
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p :=
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p) p
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      (formInCoord (𝓡∂ (n + 1)) φ (bdryIncl p)
        (extChartAt (𝓡∂ (n + 1)) (bdryIncl p) (bdryIncl p))))

/-- The pullback `ι* φ` of a boundary `n`-form along `ι : ∂M ↪ M`, as a genuine
    `n`-form on `∂M`. §A.7 DEFERRED (smoothness, inline structure-field `sorry`,
    same `T%`-elaborator reason as `mextDeriv`). -/
noncomputable def pullbackBdry (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := pullbackBdryFun φ
  contMDiff_toFun := sorry

end BoundaryManifold

/-! ## §6 — STOKES (the framework's root goal)

    `∫_M dφ = ∫_∂M (ι* φ)` — Wikipedia's generalized Stokes theorem, with BOTH
    sides the single canonical operator `DiffForm.integral` (`∫_N`): LHS at
    `(𝓡∂ (n+1), M)` applied to `mextDeriv φ`, RHS at `(∂M's model, ∂M)` applied to
    `pullbackBdry φ` (`ι* φ`). Every object — `DiffForm`, `mextDeriv`,
    `DiffForm.integral`, `Bdry`/`∂M`, `pullbackBdry`/`ι*` — is general, reusable
    infrastructure, not a shortcut for this problem. The root the framework proves;
    a clean (sorryAx-free) proof discharges every §A obligation, `∂M`'s coherence,
    the induced orientation, and the integration well-definedness. -/

section StokesThm

variable {n : ℕ}
  {M : Type*} [TopologicalSpace M] [T2Space M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
  [IsManifold (𝓡∂ (n + 1)) ∞ M] [CompactSpace M] [OrientedManifold (𝓡∂ (n + 1)) M]

/-- `∂M` inherits `T2` from `M`. (Stated explicitly because `Bdry` is a `def`, so
    instance search won't unfold it to fire `Subtype.t2Space`.) -/
instance : T2Space (Bdry n M) :=
  inferInstanceAs (T2Space {x : M // x ∈ (𝓡∂ (n + 1)).boundary M})

/-- DEFERRED (→ root): `∂M` is compact — it is the boundary, a closed subset of the
    compact manifold `M`. -/
instance instBdryCompact : CompactSpace (Bdry n M) := sorry

/-- Raw section of the induced orientation `ι_ν μ` at `p`: contract `M`'s reference
    form `μ` (at `ι p`) with the outward normal `ν = −e₀` in slot 0 (`curryLeft`),
    pass the remaining `n` slots through `faceEmbedL` (= `dι`), transport into `∂M`'s
    fibre. GENUINE DATA (no `sorry`) — this fixes `∂M`'s orientation, hence the RHS
    of Stokes. AUDIT: `ν = −e₀` is transverse to the face `{x₀=0}`, so `ι_ν μ` is a
    nowhere-zero top form on `∂M` (the induced orientation). -/
noncomputable def inducedOrientFun (p : Bdry n M) :
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p :=
  let μ := OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p) p
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      ((formInCoord (𝓡∂ (n + 1)) μ (bdryIncl p)
        (extChartAt (𝓡∂ (n + 1)) (bdryIncl p) (bdryIncl p))).curryLeft
          (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))

/-- The induced orientation form `ι_ν μ` on `∂M`, as a genuine `n`-form. Its VALUE
    (`toFun`) is genuine data, so Stokes' statement is determinate; the smoothness
    witness is the inline deferred Prop (§A.8, same `T%` reason as `mextDeriv`). -/
noncomputable def inducedOrient :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := inducedOrientFun
  contMDiff_toFun := sorry

/-- `M`'s orientation INDUCES one on `∂M` via the outward-normal contraction
    `ι_ν μ` (`ν = −e₀`) — `inducedOrient`. The `[OrientedManifold]` instance the
    boundary integral `∫_∂M` reads. `refForm` is GENUINE data (so the Stokes
    statement is sorry-free in its DATA); `refForm_ne` (`ι_ν μ` nowhere-zero, since
    `ν` is transverse to the face) is the only remaining deferred Prop. -/
noncomputable instance instBdryOriented :
    OrientedManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) where
  refForm := inducedOrient
  refForm_ne := sorry

/-- DEFERRED (→ root): the **generalized Stokes theorem** `∫_M dφ = ∫_∂M (ι* φ)`,
    with BOTH sides the single `DiffForm.integral` operator (LHS at `M`, RHS at
    `∂M`). The textbook Wikipedia form, built entirely on reusable infrastructure. -/
theorem stokes (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1)) φ) = DiffForm.integral (pullbackBdry φ) :=
  sorry

end StokesThm

end Problems.Geometry.stokes_theorem
