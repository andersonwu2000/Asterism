<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `Tendsto (fun n => f (u n)) atTop (𝓝 (f L))` from `ContinuousAt f L` and `Tendsto u atTop (𝓝 L)`, use `simpa [Function.comp] using hcont.tendsto.comp h₁`; `Tendsto.comp` produces `Tendsto (f ∘ u) ...` which won't unify with `fun n => f (u n)` without the `simp`, and `NNReal.continuous_sqrt.comp (continuous_const.add continuous_id)` establishes continuity of `fun y => NNReal.sqrt (x + y)`.
- To show `Tendsto (fun n => u (n+1)) atTop (𝓝 L)` from `h : Tendsto u atTop (𝓝 L)`, use `h.comp (Filter.tendsto_atTop_atTop_of_monotone (fun a b h => Nat.add_le_add_right h 1) (fun b => ⟨b, Nat.le_add_right b 1⟩))`; there is no dedicated "shift" lemma — it is `Tendsto.comp` with a monotone cofinal map.
- The `𝓝` notation in this problem's goal needs `open scoped Topology` inside `patch.lean` itself; `Defs.lean`'s `open ... Topology` is per-file and does not carry over, so the seeded skeleton fails to elaborate until the open is added between `namespace` and the theorem.
