import Mathlib
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation

noncomputable def circle_mv_augmentation_map {R : Type} [Ring R] :
    ModuleCat.of R (R × R) ⟶ ModuleCat.of R (R × R) :=
  ModuleCat.ofHom
    (LinearMap.prod
      (LinearMap.fst R R R + LinearMap.snd R R R)
      (-(LinearMap.fst R R R + LinearMap.snd R R R)))

-- ker of the augmentation-doubling map (a,b)↦(a+b,-(a+b)) is the antidiagonal {(a,-a)} ≅ R.
-- Build the LinearEquiv via `LinearEquiv.ofLinear`: forward = first projection off the kernel
-- subtype, inverse = `a ↦ (a,-a)` corestricted into the kernel (membership `hmem`). Round-trip
-- identities: `f∘g = id` is `simp`; `g∘f = id` uses the kernel relation `a+b=0` (⇒ `-a=b`).
noncomputable def circle_mv_augmentation_kernel_linequiv {R : Type} [Ring R] :
    ↥(LinearMap.ker (circle_mv_augmentation_map (R := R)).hom) ≃ₗ[R] R := by
  have hmem : ∀ a : R, ((a, -a) : R × R) ∈
      LinearMap.ker (circle_mv_augmentation_map (R := R)).hom := by
    intro a; rw [LinearMap.mem_ker]; simp [circle_mv_augmentation_map]
  refine LinearEquiv.ofLinear
    ((LinearMap.fst R R R).comp (LinearMap.ker (circle_mv_augmentation_map (R := R)).hom).subtype)
    (LinearMap.codRestrict (LinearMap.ker (circle_mv_augmentation_map (R := R)).hom)
      (LinearMap.prod LinearMap.id (-LinearMap.id)) hmem) ?_ ?_
  · ext
    simp
  · ext x
    · simp
    · have hx : (circle_mv_augmentation_map (R := R)).hom x.1 = 0 := x.2
      simp only [circle_mv_augmentation_map, ModuleCat.hom_ofHom, LinearMap.prod_apply,
        Pi.prod, LinearMap.add_apply, LinearMap.fst_apply, LinearMap.snd_apply,
        Prod.mk_eq_zero] at hx
      simp only [LinearMap.codRestrict_apply, LinearMap.comp_apply, Submodule.subtype_apply,
        LinearMap.fst_apply, LinearMap.prod_apply, Pi.prod, LinearMap.id_coe, id_eq,
        LinearMap.neg_apply]
      linear_combination (norm := abel) -hx.1

-- kernel(circle_mv_augmentation_map) ≅ R for the augmentation-doubling map (a,b)↦(a+b,-(a+b)).
-- Identify the categorical kernel with the module-theoretic ker via ModuleCat.kernelIsoKer,
-- then the concrete linear-algebra iso ↥ker ≃ₗ R (antidiagonal {(a,-a)}) closes it.
noncomputable def circle_mv_augmentation_kernel {R : Type} [Ring R] :
    CategoryTheory.Limits.kernel (circle_mv_augmentation_map (R := R)) ≅
      ModuleCat.of R R :=
  (ModuleCat.kernelIsoKer (circle_mv_augmentation_map (R := R))) ≪≫
    (circle_mv_augmentation_kernel_linequiv (R := R)).toModuleIso

end Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
