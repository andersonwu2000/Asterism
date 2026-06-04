import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- exists_self_homeo_sending_to_unit_ball: compact convex body with 0 in interior
-- is sent onto the closed unit ball by a self-homeomorphism of Euclidean space,
-- constructed via gaugeRescaleHomeomorph; the image equality follows from
-- gauge_gaugeRescale + gaugeRescale_gaugeRescale + gaugeRescale_self.
private lemma mem_of_gauge_le_one_closedConvex {n : ℕ}
    {T : Set (EuclideanSpace ℝ (Fin n))}
    (hT_conv : Convex ℝ T) (hT_closed : IsClosed T)
    (hT_nhds : T ∈ nhds (0 : EuclideanSpace ℝ (Fin n)))
    {y : EuclideanSpace ℝ (Fin n)} (hy : gauge T y ≤ 1) : y ∈ T := by
  rw [← hT_closed.closure_eq]
  apply mem_closure_iff_nhds.mpr
  intro U hU
  have hcont : ContinuousAt (fun t : ℝ => t • y) 1 :=
    (continuous_id.smul continuous_const).continuousAt
  have hUy : U ∈ nhds ((fun t : ℝ => t • y) 1) := by simp only [one_smul]; exact hU
  have hpre : {t : ℝ | t • y ∈ U} ∈ nhds (1 : ℝ) := hcont hUy
  rw [Metric.mem_nhds_iff] at hpre
  obtain ⟨ε, hε, hball⟩ := hpre
  have hδ : 0 < min (ε / 2) (1 / 2) := by positivity
  set t := 1 - min (ε / 2) (1 / 2) with ht_def
  have ht0 : 0 < t := by simp only [ht_def]; linarith [min_le_right (ε / 2) (1 / 2)]
  have htlt : t < 1 := by simp only [ht_def]; linarith
  have htU : t • y ∈ U := hball (by
    simp only [Metric.mem_ball, Real.dist_eq, ht_def]
    rw [show 1 - min (ε / 2) (1 / 2) - 1 = -(min (ε / 2) (1 / 2)) by ring]
    rw [abs_neg, abs_of_pos hδ]
    linarith [min_le_left (ε / 2) (1 / 2)])
  exact ⟨t • y, htU, interior_subset (by
    rw [← gauge_lt_one_eq_interior hT_conv hT_nhds]
    simp only [Set.mem_setOf_eq]
    rw [gauge_smul_of_nonneg ht0.le, smul_eq_mul]
    linarith [mul_le_mul_of_nonneg_left hy ht0.le])⟩

theorem exists_self_homeo_sending_to_unit_ball
    {n : ℕ} {T : Set (EuclideanSpace ℝ (Fin n))}
    (hcomp : IsCompact T) (hconv : Convex ℝ T)
    (h0 : (0 : EuclideanSpace ℝ (Fin n)) ∈ interior T) :
    ∃ e : EuclideanSpace ℝ (Fin n) ≃ₜ EuclideanSpace ℝ (Fin n),
      e '' T = Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 := by
  set B := Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 with hB_def
  have hB_comp : IsCompact B := isCompact_closedBall 0 1
  have hB_conv : Convex ℝ B := convex_closedBall 0 1
  have hT_nhds : T ∈ nhds (0 : EuclideanSpace ℝ (Fin n)) :=
    mem_nhds_iff.mpr ⟨interior T, interior_subset, isOpen_interior, h0⟩
  have hB_nhds : B ∈ nhds (0 : EuclideanSpace ℝ (Fin n)) := by
    rw [hB_def]; exact Metric.closedBall_mem_nhds 0 (by norm_num)
  have hT_bdd : Bornology.IsVonNBounded ℝ T := hcomp.isVonNBounded ℝ
  have hB_bdd : Bornology.IsVonNBounded ℝ B := hB_comp.isVonNBounded ℝ
  have hT_abs : Absorbent ℝ T := absorbent_nhds_zero hT_nhds
  have hB_abs : Absorbent ℝ B := absorbent_nhds_zero hB_nhds
  have hT_closed : IsClosed T := hcomp.isClosed
  refine ⟨gaugeRescaleHomeomorph T B hconv hT_nhds hT_bdd hB_conv hB_nhds hB_bdd, ?_⟩
  -- Characterize the image: e '' T = B
  -- First, note that applying the homeomorphism equals gaugeRescale T B
  set e := gaugeRescaleHomeomorph T B hconv hT_nhds hT_bdd hB_conv hB_nhds hB_bdd with he_def
  have he_apply : ∀ y, e y = gaugeRescale T B y := fun y => by
    simp [he_def, gaugeRescaleHomeomorph, gaugeRescaleEquiv]
  ext x
  rw [Set.mem_image]
  simp_rw [he_apply]
  constructor
  · -- Forward: y ∈ T → gaugeRescale T B y ∈ B
    rintro ⟨y, hyT, rfl⟩
    rw [hB_def, mem_closedBall_zero_iff]
    -- gauge B (gaugeRescale T B y) = gauge T y
    have key := gauge_gaugeRescale T hB_abs hB_bdd y
    -- key : gauge B (gaugeRescale T B y) = gauge T y
    rw [hB_def, gauge_closedBall (by norm_num : (0:ℝ) ≤ 1), div_one] at key
    -- key : ‖gaugeRescale T B y‖ = gauge T y
    rw [key]
    exact gauge_le_one_of_mem hyT
  · -- Backward: x ∈ B → ∃ y ∈ T, gaugeRescale T B y = x
    intro hxB
    refine ⟨gaugeRescale B T x, ?_, ?_⟩
    · -- gaugeRescale B T x ∈ T
      apply mem_of_gauge_le_one_closedConvex hconv hT_closed hT_nhds
      have key := gauge_gaugeRescale B hT_abs hT_bdd x
      -- key : gauge T (gaugeRescale B T x) = gauge B x
      rw [key, hB_def, gauge_closedBall (by norm_num : (0:ℝ) ≤ 1), div_one]
      rw [hB_def] at hxB
      rwa [mem_closedBall_zero_iff] at hxB
    · -- gaugeRescale T B (gaugeRescale B T x) = x
      have hcomp : gaugeRescale T B (gaugeRescale B T x) = gaugeRescale B B x :=
        gaugeRescale_gaugeRescale hT_abs hT_bdd x
      rw [hcomp, congr_fun (gaugeRescale_self hB_abs hB_bdd) x]
      simp

end Problems.Topology.brouwer_fixed_point
