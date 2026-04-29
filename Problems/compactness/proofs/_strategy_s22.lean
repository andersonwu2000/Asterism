import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s22_s4_main_sub_2_sub_1
import Problems.compactness.proofs.L_s22_s4_main_sub_2_sub_2
import Problems.compactness.proofs.L_s22_s4_main_sub_2_sub_3
import Problems.compactness.proofs.L_s22_s4_main_sub_2_sub_4

namespace Problems.compactness

theorem s22_s4_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M h_finsat h_max p
  -- Convert Zorn-style maximality to element-wise maximality
  have h_max' : ∀ q : PropForm α, q ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert q M → T.Finite → Sat T) :=
    s22_s4_main_sub_2_sub_2 M h_max
  constructor
  · -- Forward: neg p ∈ M → p ∉ M
    exact s22_s4_main_sub_2_sub_1 M h_finsat p
  · -- Backward: p ∉ M → neg p ∈ M
    intro hp
    by_contra hneg
    -- Finite witness T_p ⊆ M with ¬Sat (insert p T_p)
    obtain ⟨T_p, hTp_sub, hTp_fin, hTp_unsat⟩ :=
      s22_s4_main_sub_2_sub_3 M p h_finsat (h_max' p hp)
    -- Finite witness T_np ⊆ M with ¬Sat (insert (neg p) T_np)
    obtain ⟨T_np, hTnp_sub, hTnp_fin, hTnp_unsat⟩ :=
      s22_s4_main_sub_2_sub_3 M (PropForm.neg p) h_finsat (h_max' (PropForm.neg p) hneg)
    -- T_p ∪ T_np ⊆ M is finite; finsat yields a model v
    obtain ⟨v, hv⟩ := h_finsat (T_p ∪ T_np)
      (Set.union_subset hTp_sub hTnp_sub) (hTp_fin.union hTnp_fin)
    -- v satisfies T_p, so v must satisfy neg p
    have hv_negp : PropForm.eval v (PropForm.neg p) = true :=
      s22_s4_main_sub_2_sub_4 T_p p hTp_unsat v (fun q hq => hv q (Set.mem_union_left _ hq))
    -- v satisfies T_np and neg p, contradicting ¬Sat (insert (neg p) T_np)
    exact hTnp_unsat ⟨v, fun q hq => by
      rcases Set.mem_insert_iff.mp hq with rfl | hmem
      · exact hv_negp
      · exact hv q (Set.mem_union_right _ hmem)⟩

end Problems.compactness
