- **Argmin over filtered triple-product Finset**: Use `Finset.exists_min_image` on `(P×ˢP×ˢP).filter pred` with `open Classical`; delegate pack/unpack of `mem_filter`/`mem_product` to Builder sub-lemmas.

- **Sylvester–Gallai existence goal**: `by_contra` + Skolemise the negated `∃ p q, p≠q ∧ ∀ r, …` via a pure-logic sub-lemma, then feed the universal witness into a Kelly-style geometric refutation sub-lemma.

- **Existence of perpendicular-distance² minimiser over point triples**: Split into Builder witness (`p,q,r` from non-collinear triple, `p≠q` via `Collinear`'s `mul_comm` symmetry) + Backward `Finset.exists_min_image` on filtered `P ×ˢ P ×ˢ P`, then unpack.

- **Kelly polynomial closer (μ-substituted)**: Backward-split into `D² > 0` (unfold `Collinear` determinant + `ring`), `2μA ≤ 0` (sign case-split on H1/H2), then `nlinarith` closes via identity `RHS−LHS = D²·(|q−r|² − 2μA)`.

- **|s-p|² < |r-p|² via Lagrange + strict Cauchy–Schwarz**: Combine four sub-lemmas (|u|²>0, Lagrange equality on s, sign-bound (s-p)·u, strict CS at r) then `nlinarith` to cancel the positive |u|² factor.

- **Cross-square inequality with collinearity-induced identity rewrite**: Split `A²·D < C²·E` as identity `A²·D = C²·F` (`s100_sub_1`) plus `F < E` (`sub_2`) and `C² > 0` (`sub_3`); finish with `rw [h1]; exact mul_lt_mul_of_pos_left h2 h3`.

- **Strict ratio inequality `X²/D1 < Y²/D2`**: Prove both denominators positive, then `rw [div_lt_div_iff₀ hD2 hD1]` to reduce to the cross-multiplied polynomial inequality.

- **Kelly geometric step (smaller perp-distance triple)**: Pigeonhole `{p,q,s}` along line `pq` via signed scalar projections to a same-side pair, then dispatch each of the 3 cases to a sub-lemma with `rcases … | … | …`.

- **Minimiser of perp-distance² ⇒ False**: Split off the Kelly construction as a Backward sub-lemma producing a strictly-smaller witness, then close with `absurd (h_min …) (not_le.mpr h_lt)`.

- **Kelly cross-multiplied distance bound (Case B)**: Introduce A,B,D,E,α,β; combine ring identities `A·D = B·(β−α)` and `α²+B² = D·E` with `D>0`, `B≠0` and feed to nlinarith.
