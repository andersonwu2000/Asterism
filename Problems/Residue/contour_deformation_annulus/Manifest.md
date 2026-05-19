---
problem: Residue.contour_deformation_annulus
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Residue.contour_deformation_annulus — punctured ball 同心圓圍道積分相等

## Statement
∀ {f : ℂ → ℂ} {c : ℂ} {r₁ r₂ R : ℝ},
  0 < r₁ → r₁ < r₂ → r₂ < R →
  AnalyticOn ℂ f (Metric.ball c R \ {c}) →
  (∮ z in C(c, r₁), f z) = (∮ z in C(c, r₂), f z)

## Setting
在 c 處有孤立奇點（或 removable）的 f、同心於 c 的兩個圓圍道積分相等 — 這是 single-pole residue 定義不依賴 r 選擇的核心 fact。

## Lemma hints
- `Residue.primitive_simply_connected` (proved) — annulus 雖然不是 simply-connected、但可拆成兩塊上下半 annulus 各自 simply-connected
- `Residue.closed_loop_integral_zero` (proved)
- 標準作法：兩個同心圓 + 兩條半徑連線 = 兩個圍道、各自包圍 simply-connected region、各自圍道積分 = 0；組合起來消掉半徑連線部分、得到兩圓圍道積分相等

## Strategic notes
這是 chain 中比較複雜的構造性證明。預計拆出：
- annulus = 上半 ∪ 下半 (simply-connected each)
- 每塊上 closed loop = inner_arc + radius_in + outer_arc_reverse + radius_out
- 半徑線段在兩塊上方向相反、積分抵消
- 兩 inner_arc 拼出 inner_circle、兩 outer_arc 拼出 outer_circle

可能需要 2-3 個 Forward 補半 annulus 的 simply-connected 性、path concatenation。預計 3-5 小時。
