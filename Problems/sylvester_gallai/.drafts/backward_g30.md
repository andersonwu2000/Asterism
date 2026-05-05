### _progress.md

```
# Progress note (timed-out turn)

## Decomposition shape
4-way split: one disjunctive algebraic lemma (the hard core) + two non-collinearity lemmas + one inequality lemma; patch case-splits on the disjunction to select witnesses (u=b,v=p,w=c) vs (u=a,v=p,w=c).

## Sub-pieces with clear formulations

- **s38_sub_1** (Backward) — disjunction: `∀ (p a b c : ℝ × ℝ), ¬ Collinear p a b → Collinear a b c → c ≠ a → c ≠ b → ((b.1-c.1)*(p.2-c.2)-(b.2-c.2)*(p.1-c.1))^2*((a.1-b.1)^2+(a.2-b.2)^2) < ((p.1-b.1)*(a.2-b.2)-(p.2-b.2)*(a.1-b.1))^2*((p.1-c.1)^2+(p.2-c.2)^2) ∨ ((a.1-c.1)*(p.2-c.2)-(a.2-c.2)*(p.1-c.1))^2*((a.1-b.1)^2+(a.2-b.2)^2) < ((p.1-b.1)*(a.2-b.2)-(p.2-b.2)*(a.1-b.1))^2*((p.1-c.1)^2+(p.2-c.2)^2)`
- **s38_sub_2** (Builder) — `∀ p a b c, ¬Collinear p a b → Collinear a b c → c ≠ b → ¬Collinear b p c`
- **s38_sub_3** (Builder) — `∀ p a b c, ¬Collinear p a b → Collinear a b c → c ≠ a → ¬Collinear a p c`
- **s38_sub_4** (Builder) — `∀ p a b c, ¬Collinear p a b → Collinear a b c → p ≠ c`

## Stuck point
The disjunction in s38_sub_1 is NOT the same as what dead strategies s29/s33 tried. Dead strategies used `|pb|²` or `|pa|²` on the RHS denominator; this one uses `|pc|²` for both candidates. Algebraically this reduces to: either `(1-t)²·|ab|²·|ab|² < D²·|pc|²·|ab|²/|ab|²` ... wait, working through: cross(b,p,c)=（1-t)·D and cross(a,p,c)=-t·D (by parametrizing c=a+t(b-a)), so the disjunction becomes `(1-t)²·L⁴ < D²·|pc|²` OR `t²·L⁴ < D²·|pc|²`. This CAN fail for both when |pc| is small (c near p's foot). Specifically the s29 counterexample (b=(0,0),a=(2,0),c=(0.5,0),p=(0.5,0.1)) gives |pc|²=0.01, D²=0.04, L²=4: (0.5)²·16=4 vs 0.04·0.01·... wait — the full expression is `t²·L²·L² < D²·|pc|²`... no: the inequality is `cross²·L² < D²·|pc|²` = `(t·D)²·L² < D²·|pc|²` = `t²·L² < |pc|²`. With t=0.25 (c=(0.5,0), a=(0,0)... wait a=(2,0)), t=(0.5-2)/(0-2)=0.75. t²·L²=0.5625·4=2.25 vs |pc|²=0.01. FALSE. And (1-t)²·L²=0.0625·4=0.25 vs 0.01. FALSE. So s38_sub_1 AS STATED IS ALSO FALSE.

#

... (truncated; full file was 2652 chars)
```
