import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s12_s3_main_sub_2_sub_1
import Problems.compactness.proofs.L_s12_s3_main_sub_2_sub_2
import Problems.compactness.proofs.L_s12_s3_main_sub_2_sub_3

namespace Problems.compactness

theorem s12_s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M hfinsat hmax p
  constructor
  · -- Forward: neg p ∈ M → p ∉ M
    intro hneg
    exact s12_s3_main_sub_2_sub_1 M hfinsat p hneg
  · -- Backward: p ∉ M → neg p ∈ M
    intro hp
    by_contra hneg
    -- Maximality of p: get a finite T_p ⊆ M with ¬Sat (insert p T_p)
    obtain ⟨T_p, hTp_sub, hTp_fin, hTp_unsat⟩ :=
      s12_s3_main_sub_2_sub_2 M p hfinsat (hmax p hp)
    -- Maximality of neg p: get a finite T_np ⊆ M with ¬Sat (insert (neg p) T_np)
    obtain ⟨T_np, hTnp_sub, hTnp_fin, hTnp_unsat⟩ :=
      s12_s3_main_sub_2_sub_2 M (PropForm.neg p) hfinsat (hmax (PropForm.neg p) hneg)
    -- T_p ∪ T_np ⊆ M is finite; finsat yields a model v
    obtain ⟨v, hv⟩ := hfinsat (T_p ∪ T_np)
      (Set.union_subset hTp_sub hTnp_sub) (hTp_fin.union hTnp_fin)
    -- v satisfies T_p (restricted from T_p ∪ T_np)
    have hv_T_p : ∀ q ∈ T_p, PropForm.eval v q = true :=
      fun q hq => hv q (Or.inl hq)
    -- v satisfies T_np (restricted from T_p ∪ T_np)
    have hv_T_np : ∀ q ∈ T_np, PropForm.eval v q = true :=
      fun q hq => hv q (Or.inr hq)
    -- Since ¬Sat (insert p T_p) and v satisfies T_p, v must satisfy neg p
    have hv_negp : PropForm.eval v (PropForm.neg p) = true :=
      s12_s3_main_sub_2_sub_3 T_p p hTp_unsat v hv_T_p
    -- v satisfies insert (neg p) T_np, contradicting hTnp_unsat
    exact hTnp_unsat ⟨v, fun q hq => by
      rcases Set.mem_insert_iff.mp hq with rfl | hmem
      · exact hv_negp
      · exact hv_T_np q hmem⟩

end Problems.compactness
