- **Conjunction-closure biconditional for finitely-satisfiable set**: Split iff into 3 sub-lemmas (fwd-left, fwd-right, backward); each direction uses negation-completeness + finite-sat to derive contradiction via a 2-element witness set.

- **Canonical model from negation-complete conjunction-closed set**: Define `v a ↔ atom a ∈ M`, then prove the biconditional `p ∈ M ↔ eval v p = true` by structural induction (atom/neg/conj); project forward. Use `Classical.choice` for v construction.

- **Witness extraction via maximal-set negation**: Split into 3 sub-goals: push `¬∀` classically (`Classical.not_forall`/`not_imp`), prove `p ∈ T'` by contradiction via `hfinsat`, then strip with `T' \ {p}` using `Set.insert_diff_self_of_mem`.

- **Maximal finsat set neg-membership biconditional**: Split iff via `s79_sub_1` (forward: 2-element contradiction), `s79_sub_2` (witness extraction from `hmax`), `s79_sub_3` (backward: diagonal union argument). Intermediate witness form bridges maximality to both directions.

- **Set-builder membership from matching conjunction hypothesis**: Project the hypothesis into its components with `have` and close via `exact ⟨h1, h2⟩`, since `S ∈ {X | P X}` reduces definitionally to `P S`.

- **Reshape Zorn output to pointwise-maximal existential**: After `obtain ⟨M, hMP, hMmax⟩`, split the set-builder membership unpack and the `N = M` → `M = N` flip into two sub-lemmas, then `exact ⟨M, sub_1 …, sub_2 …⟩`.

- **Maximal finitely-satisfiable extension exists**: Apply `Set.zorn_subset_nonempty` to get the strong form (with `S ⊆ M`), then project away the extra conjunct via destructure-and-repack.

- **Zorn maximal element in finsat-extension poset**: Split into membership witness (S ∈ P), raw `zorn_subset_nonempty` call, and output reshape (`.symm` on equality); keeps satisfiability reasoning out of the Zorn step.

- **Finite subset of chain-union is satisfiable**: Split into pure chain-cover combinatorics (`∃ X ∈ C, T ⊆ X` via `Set.Finite.induction_on` + `IsChain` comparability) then one-line `hfinsat` lift; compose the two sublemmas positionally.

- **Lindenbaum extension to pointwise-maximal finitely-sat superset**: Decompose into 4 lemmas: chain⇒finite-subset-in-member, chain-union preserves finsat, Zorn for subset-max, then subset-max⇒pointwise-max.
