import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_isometry_fixing_origin_smul_comm

namespace Problems.Geometry.banach_tarski

-- S realizes the cone map: each cone point y = r•x (r∈(0,1], x∈e.source⊆sphere) has ‖y‖=r,
-- ‖y‖⁻¹•y = x, so f y = r • e x = r • (g•x) for the g∈S realizing e at x; since g fixes 0 it is
-- ℝ-linear (s11475), so g•(r•x) = r•(g•x), matching. Leaf: cite s11475 + norm algebra inline.
theorem s11512 (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    Equidecomp.IsDecompOn (fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z))
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} S  := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  obtain ⟨g, hgS, hgx⟩ := hdec x hx
  refine ⟨g, hgS, ?_⟩
  have hx1 : ‖x‖ = 1 := by
    have h := hsrc hx
    rwa [mem_sphere_zero_iff_norm] at h
  have hrpos : 0 < r := hr.1
  have hnr : ‖r • x‖ = r := by
    rw [norm_smul, hx1, mul_one, Real.norm_eq_abs, abs_of_pos hrpos]
  have hxback : (‖r • x‖)⁻¹ • (r • x) = x := by
    rw [hnr, smul_smul, inv_mul_cancel₀ (ne_of_gt hrpos), one_smul]
  change ‖r • x‖ • e.toFun (‖r • x‖⁻¹ • (r • x)) = g • (r • x)
  rw [hxback, hnr, hgx]
  change r • (g x) = g (r • x)
  rw [s11475 g (h0 g hgS) r x]

end Problems.Geometry.banach_tarski
