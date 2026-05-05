- **Indexed intersection subset via membership unfolding**: Split `⋂ m, f m ⊆ f n` into membership unfolding (`Set.mem_iInter.mp`) + specialization (`h n`). Avoids elaboration failures with `Set.iInter_subset`.

- **Lebesgue measure of linear-image via smul**: Rewrite `(fun x => c*x) '' s` as `c • s` (pure set equality), then apply `addHaar_smul_of_nonneg volume hr s` explicitly — pass `volume` as the first argument, not the nonnegativity proof.

- **ENNReal ofReal power sequence tendsto zero**: `simp_rw [ENNReal.ofReal_pow]` rewrites `ofReal (r^n)` to `ofReal r ^ n`, then `ENNReal.tendsto_pow_atTop_nhds_zero_of_lt_one` closes the goal directly.

- **Cantor set measure zero via iterate squeeze**: Induction gives `volume(cantorXi n) = (1-ξ)^n`; containment + `measure_mono` bounds `volume(cantorSet)`; `tendsto_pow_atTop_nhds_zero_of_lt_one` squeezes to 0.

- **Cantor iterate measure by induction**: Decompose into 4 lemmas (compactness, containment, disjointness, step formula); induction closes with `simp` at zero and delegates `succ` to the step lemma via `s171_sub_4`.

- **Disjointness of affine images via interval containment**: Bound each image into disjoint `Icc` intervals separately, then combine with `Disjoint.mono`. Use `s_sub_1`/`s_sub_2` for containment and `s_sub_3` for interval disjointness.

- **ENNReal measure zero from geometric upper bound**: Squeeze via `le_of_tendsto_of_tendsto'` (const + geometric tendsto) to get `≤ 0`, then `le_antisymm` with `zero_le` closes the equality.

- **Cantor set iterate measure induction step**: Unfold the union definition, derive `MeasurableSet` via `IsCompact.measurableSet`, apply `measure_union` with disjointness, then rewrite with affine-scaling lemmas (`addHaar_image_homothety`) and close with ENNReal arithmetic.

- **Inductive subset containment of iterated affine union**: Induct on `n`; base by `simp [cantorXi]`; step by `Set.union_subset` delegating each affine image to a standalone `image_subset_iff`+`nlinarith` lemma.

- **Inductive compactness of iterated IFS sets**: Decompose into base (`isCompact_Icc`) + image lemmas (`IsCompact.image` with continuous affine maps) + union (`IsCompact.union`); combine via `induction n`.
