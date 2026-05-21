import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_ae_continuous_at_seg_q
import Problems.residue_thm.proofs.L_eventually_aemeas_seg_q
import Problems.residue_thm.proofs.L_eventually_bounded_seg_q

namespace Problems.residue_thm

-- Apply parametric-DCT (`intervalIntegral.continuousAt_of_dominated_interval`).
-- Three Builder sub-goals supply the DCT premises: eventually-AE-measurability
-- of the integrand, eventually-bounded by a constant M, and pointwise continuity
-- at h=0 (since z+t·0=z and Q is continuous at z via hQ + 0 < R).
theorem s10649
    (Q : ℂ → ℂ) (z : ℂ) (R : ℝ) (hR : 0 < R)
    (hQ : ContinuousOn Q (Metric.closedBall z R)) :
    ContinuousAt (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h)) 0  := by
  have h_aemeas := eventually_aemeas_seg_q Q z R hR hQ
  have h_bound := eventually_bounded_seg_q Q z R hR hQ
  have h_cont := ae_continuous_at_seg_q Q z R hR hQ
  obtain ⟨M, hM⟩ := h_bound
  exact intervalIntegral.continuousAt_of_dominated_interval h_aemeas hM
    intervalIntegrable_const h_cont

end Problems.residue_thm
