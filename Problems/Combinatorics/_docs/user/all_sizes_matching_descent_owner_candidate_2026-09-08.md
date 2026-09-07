# An all-size matching descent for a smallest counterexample (owner-supplied, UNVERIFIED, 2026-09-08)

*Supplied by the owner from an outside session. **Not reviewed by this framework's theory reviewer, not Lean-certified, not accepted, novelty not checked against the literature.** It is a direction, not a result: it does not assume SYNC66 and does not settle anything at any size. What it proves (Theorem 2, Lemma 3, Corollary 4) is a restriction that holds at EVERY maximal-frequency coordinate of a smallest counterexample — a near-perfect containment matching between the two sides of the split would halve the counterexample, so the split's Hall deficiency must be at least two, or one with a critical family of reducible members only. What it does NOT prove is the existence of such a matching, or a descent from the Hall obstruction — that is the whole difficulty and the report says so. Section 6 is a limitation of the SYNC66 candidate's witness-count inequalities (an infinite family they fail to detect); it does not refute SYNC66's finite claim, and judging its bite needs the SYNC66 definitions beside it. Treat every statement as a CLAIM to be re-derived; the checks it cites (`checks.py`, `near_matching_probe.py`, `verification.json`) live in `scratch/union_closed_all_sizes_20260908/` in the repository root and test the finite identities and examples, not the all-rare premise.*

---

# An all-size direction: near-perfect containment matching and a halving descent

Date: 2026-09-08. **Status: research submission for independent review; no Lean certification. Frankl's conjecture remains unresolved in this submission.**

## 1. What this investigation establishes

This investigation replaces the next finite-cardinality exclusion with three statements that hold at arbitrary size:

1. A near-perfect containment matching in a maximal-frequency split of a smallest Frankl counterexample would produce a counterexample of approximately half the size. The precise parity and removability conditions are proved below.
2. A smallest counterexample must therefore have a specified Hall obstruction at **every** maximal-frequency coordinate. When the matching deficiency is one, the only possible unmatched members lie in a canonical union-closed upper ideal. In the relevant parity, all of those members must be reducible.
3. The previous zero-action witness bounds have a concrete limitation: an infinite family of exact eight-cell diagrams passes those numerical bounds even though its actual outside frequencies exceed half. Thus simply substituting arbitrary parameters into the SYNC66 inequalities is insufficient. A separate uniform projection inequality is available, but it does not remove that limitation.

The missing result is **existence of a suitable matching, or a descent from its Hall obstruction**, under the full hypotheses of a smallest counterexample. It is not proved here. In particular this report does not present an equivalent reformulation as a solution, and does not claim that a conditional descent establishes its own hypothesis.

The main matching route targets Frankl directly. It does not require proving the stronger Boolean rigidity statement used by the present ALT programme. An optional matching lemma for that stronger route is given in Section 7.

The existing [SYNC66 report](sync66_owner_candidate_2026-09-08.md) remains a separate candidate submission. No part of the direct matching descent assumes that SYNC66 has been accepted.

## 2. A smallest counterexample has an unequal split of sizes m+1 and m

For a finite family \(F\), put \(f_F(x)=|\{A\in F:x\in A\}|\). A counterexample means that \(F\) is union-closed, contains a nonempty member, and

\[
2f_F(x)<|F|\qquad\text{for every }x.
\]

**Lemma 1 (standard minimal-counterexample normalization).** If \(F\) has the fewest members among all counterexamples, then

\[
|F|=2m+1,\qquad \max_x f_F(x)=m,\qquad m\ge2.
\tag{1}
\]

**Proof.** Removing an inclusion-minimal nonempty member preserves union closure: if the removed set were a union of surviving members, one of its nonempty proper subsets would have been a member. The remainder still has a nonempty member; otherwise \(F\) would consist only of the removed member and possibly empty, and could not be a counterexample.

If \(|F|=2m\), every frequency is at most \(m-1\), so the remainder of size \(2m-1\) is still a counterexample. If \(|F|=2m+1\) and every frequency is at most \(m-1\), the remainder of size \(2m\) is again a counterexample. Both contradict minimality. Families of size at most three cannot be counterexamples: in the three-member case any point of a proper nonempty member is also in the top, while the case with only one nonempty member has size at most two. This gives \(m\ge2\). ∎

This normalization is already present in the project record; the proof is included to make the present reduction self-contained.

Choose a coordinate \(t\) attaining \(m\), and put

\[
L=\{A\in F:t\notin A\},\qquad
H=\{A\setminus\{t\}:A\in F,\ t\in A\}.
\]

Then both families are union-closed,

\[
|L|=m+1,\quad |H|=m,\quad L\vee H\subseteq H,
\quad f_L(x)+f_H(x)\le m\quad(x\ne t).
\tag{2}
\]

All subsequent matchings use two separate copies of these families, even where a set belongs to both.

## 3. A direct halving descent

Join \(A\in L\) to \(B\in H\) exactly when \(A\subseteq B\).

**Theorem 2 (near-perfect matching descent).** Suppose (2) holds and there is a bijection

\[
\phi:L\setminus\{R\}\longrightarrow H,
\qquad A\subseteq\phi(A).
\tag{3}
\]

Then:

- If \(m\) is even, \(L\) is a counterexample with \(m+1\) members.
- If \(m\) is odd and \(R\) is removable from \(L\), then \(L\setminus\{R\}\) is a counterexample with \(m\) members.

Here removable means that deletion preserves union closure, equivalently that \(R\) is not the union of two other members of \(L\). Empty is allowed as a removable member.

**Proof.** Containment in the matching gives, for every coordinate \(x\),

\[
f_H(x)\ge f_L(x)-\mathbf 1_{x\in R}.
\]

Combining this with (2),

\[
2f_L(x)\le m+\mathbf 1_{x\in R}.
\tag{4}
\]

If \(m=2r\), integrality makes the right side imply \(f_L(x)\le r\), whether or not \(x\in R\). Since \(|L|=2r+1\), all coordinates are strictly rare in \(L\).

If \(m=2r+1\), let \(G=L\setminus\{R\}\). For \(x\notin R\), (4) gives \(f_G(x)=f_L(x)\le r\). For \(x\in R\), it gives \(f_G(x)=f_L(x)-1\le r\). Thus every coordinate of the \(2r+1\)-member family \(G\) is strictly rare. Removability supplies union closure.

In the minimal-counterexample setting these smaller families have at least three members, so cannot consist only of empty. ∎

The theorem is independent of ground-set size, zero-block size, and the number of maximal-frequency coordinate classes. It reduces the original counterexample size \(2m+1\) to \(m+1\) or \(m\), rather than excluding one numerical size at a time.

**Important limitation.** The theorem proves the consequence of (3), not its existence. Even a matching of size \(m\) need not be able to leave a removable member unmatched; Section 5 gives an actual example.

## 4. Exact Hall obstructions that must survive at every maximal coordinate

For \(S\subseteq L\), define

\[
N(S)=\{B\in H:\exists A\in S, A\subseteq B\},
\qquad d(S)=|S|-|N(S)|,
\qquad \delta=\max_{S\subseteq L}d(S).
\tag{5}
\]

Since \(|L|=|H|+1\), \(\delta\ge1\). The deficiency form of Hall's theorem says that the maximum matching has size \(|L|-\delta\). Thus a matching as in (3) exists for some \(R\) exactly when \(\delta=1\). The matching theorem is standard; see, for example, [Cameron's account of Hall's theorem](https://doi.org/10.1112/jlms.70378).

**Lemma 3 (canonical critical family).** Every \(S\) maximizing \(d\) is an upper ideal in \(L\) under inclusion. The intersection

\[
S_* = \bigcap\{S\subseteq L:d(S)=\delta\}
\tag{6}
\]

also has deficiency \(\delta\). In particular \(S_*\) is nonempty, union-closed, and absorbed by \(L\); its neighborhood \(N(S_*)\) is union-closed and absorbed by \(L\).

When \(\delta=1\), a member \(R\in L\) can be the unmatched member of a matching saturating \(H\) **if and only if** \(R\in S_*\).

**Proof.** If \(A\in S\) and \(A\subseteq A'\in L\), then \(N(\{A'\})\subseteq N(\{A\})\). If \(A'\notin S\), adjoining it increases deficiency by one, contradicting maximality. Hence a maximizer is an upper ideal.

The neighborhood cardinality is submodular, because neighborhoods commute with union and \(N(S\cap T)\subseteq N(S)\cap N(T)\). Therefore \(d\) is supermodular. The union and intersection of two maximizers must again be maximizers; finite iteration proves the assertion for \(S_*\). Positive deficiency makes it nonempty. An upper ideal of a union-closed family is union-closed and absorbed by that family. If \(B\in N(S_*)\) and \(A\in L\), then \(A\cup B\in H\) still contains the same witness in \(S_*\), proving the corresponding neighborhood assertions.

Suppose \(\delta=1\). By Hall's theorem, deleting \(R\) from the left side permits a perfect matching exactly when no subset of \(L\setminus\{R\}\) has positive deficiency. Since all deficiencies are at most one, this says precisely that every deficiency-one set contains \(R\), which is \(R\in S_*\). ∎

**Corollary 4 (an all-size restriction on smallest counterexamples).** For every maximal-frequency coordinate of a smallest counterexample:

\[
\begin{array}{c|l}
|F|\pmod4&\text{necessary obstruction}\\\hline
1&\delta\ge2,\\
3&\delta\ge2\ \text{or}\ \bigl(\delta=1\text{ and every member of }S_*\text{ is reducible in }L\bigr).
\end{array}
\tag{7}
\]

**Proof.** Apply Theorem 2 and Lemma 3. A permitted matching would produce a smaller counterexample. ∎

This is a uniform restriction, not a cardinality cutoff. It also gives a concrete set-level object for a continued attack, rather than just a list of frequency totals.

**Additional structure in the deficiency-one case.** When \(\delta=1\), there is a containment-preserving bijection

\[
L\setminus S_*\longrightarrow H\setminus N(S_*).
\tag{8}
\]

Indeed, for \(T\subseteq L\setminus S_*\), the inequality \(d(S_*\cup T)\le d(S_*)\) gives \(|N(T)\setminus N(S_*)|\ge|T|\); the two sides of (8) have equal cardinality. Hall's theorem applies.

If all members of \(S_*\) are reducible, an inclusion-minimal \(B\in S_*\) can be written \(B=C\cup D\) with proper \(C,D\in L\setminus S_*\). Under any matching (8),

\[
\phi(C),\phi(D)\notin N(S_*),\qquad
\phi(C)\cup\phi(D)\in N(S_*).
\tag{9}
\]

The second inclusion uses union closure of \(H\) and containment of \(B\). This precisely records where unions cross from the matched complement into the deficient part. It is a possible starting point for a further descent; no such descent is asserted here.

## 5. Two tempting shortcuts are false

All examples use decimal masks with bit weights \(1,2,4,8\).

**Equal-size absorption does not guarantee a perfect containment matching.**

\[
L=\{2,3\},\qquad H=\{1,3\}.
\]

Both families are union-closed, have the same size, and \(L\vee H\subseteq H\). Both lower members have only the upper member 3 as a possible neighbor. A matching has size at most one.

**A near-perfect matching does not guarantee a removable unmatched member, even in the relevant parity.**

\[
\begin{aligned}
L&=\{0,4,5,10,14,15\},\\
H&=\{1,5,7,11,15\}.
\end{aligned}
\tag{10}
\]

Both are union-closed and \(H\) absorbs \(L\). A matching saturating \(H\) is

\[
0\mapsto1,\quad4\mapsto5,\quad5\mapsto7,
\quad10\mapsto11,\quad15\mapsto15,
\]

leaving 14 unmatched. The set \(\{14,15\}\) has the single neighbor 15, so neither can both be matched. The displayed matching and the analogous matching using \(14\mapsto15\) show that exactly 14 and 15 can be unmatched. Both are reducible:

\[
14=4\cup10,\qquad15=5\cup10.
\]

The removable lower members are \(0,4,5,10\), none of which can be unmatched in a saturating matching. Thus \(S_*=\{14,15\}\) contains no removable member.

This is **not** a Frankl counterexample or a refutation of the proposed minimal-counterexample target: its combined coordinate frequencies are \((7,6,7,5)\), which violate the required ceiling \(m=5\). It shows that the full rarity hypothesis must do real work; closure, absorption, cardinality difference one, and even existence of a near-perfect matching are insufficient on their own.

## 6. Why the SYNC66 witness counts do not automatically extend to all sizes

Here is an infinite family of actual diagrams on which those specific numerical tests fail to detect abundance.

Fix \(k\ge6\), let \(X=[k]\), choose a three-set \(B\subset X\), and put

\[
A=\{S\subseteq X:|S|\ge3\},\qquad
Z=\{\varnothing\}\cup(A\setminus\{B\}),\qquad
F_I=A\quad(I\ne\varnothing).
\tag{11}
\]

The families are union-closed; removing the minimal three-set \(B\) preserves closure. The zero family stabilizes \(A\), and all exact products are \(A\), because \(A\vee A=A\). Every nonzero cell has empty intersection and separates \(X\). Every nonempty zero member has size at least three.

Write

\[
s=2^k-1-k-\binom{k}{2},\qquad |K|=8s=2M,\quad M=4s.
\]

All eight cells have size \(s\), so all three tagged coordinates have frequency exactly \(M\). On an outside point,

\[
f_A(x)=2^{k-1}-k,
\quad
f_K(x)=M+2(k-1)(k-2)-\mathbf1_{x\in B}>M.
\tag{12}
\]

The actual diagram thus has abundant outside coordinates and satisfies Frankl's conclusion. It is not an obstruction satisfying the rare-frequency premise.

However, every zero block is a single point and each avoiding top is \(X\setminus\{x\}\). The previous coordinatewise witness floor reduces to

\[
f_Z(x)+7k=2^{k-1}+6k-\mathbf1_{x\in B}\le M-1.
\tag{13}
\]

There is no internal-block correction, and the class counts are already exact. The previous scalar weight floor is

\[
W_0=14s+k(2^{k-1}-k)+7k^2-14k-17.
\]

It too is compatible with the hypothetical rare-coordinate budget:

\[
k(M-1)-W_0
=(7k-28)2^{k-1}-2k^3-k^2+16k+31>0
\quad(k\ge6).
\tag{14}
\]

For completeness, the gap in (13), even using the larger floor without the indicator, is \(G(k)=7\cdot2^{k-1}-2k^2-8k-5\). It is positive at six, and \(G(k+1)-2G(k)=2k^2+4k-5>0\). The gap \(Q(k)\) in (14) is 107 at six, and

\[
Q(k+1)-2Q(k)=7\cdot2^k+2k^3-5k^2-24k-18>0
\quad(k\ge6).
\]

Thus these failures of detection hold for the entire infinite family, not only the checked examples.

| k | \(|K|\) | half-size M | actual outside frequencies | witness floors |
|---:|---:|---:|---|---|
|6|336|168|207–208|67–68|
|7|792|396|455–456|105–106|
|8|1752|876|959–960|175–176|
|9|3728|1864|1975–1976|309–310|
|10|7744|3872|4015–4016|571–572|

**Scope of this limitation.** It concerns the particular zero-action and internal-block inequalities used in the previous submission. It is not an impossibility theorem for all counting methods, all scalar refinements, or the full programme. These examples need not be minimal and do not satisfy outside rarity. What they demonstrate is exactly the information lost by counting a fixed collection of witnesses instead of the many remaining members of the cells.

### A uniform partition bound remains available

For any three partitions of a block of \(w\) points with discrete common refinement, encode a point by its three class labels. Let \(r_I\) be the number of different projections of those codes onto the coordinates in \(I\). Then

\[
\sum_{I\ne\varnothing}r_I
\ge w+3w^{2/3}+3w^{1/3}=(1+w^{1/3})^3-1.
\tag{15}
\]

This is an application of the classical discrete projection inequalities, not a new projection theorem; see [Bollobás–Thomason, *Projections of Bodies and Hereditary Properties of Hypergraphs*](https://doi.org/10.1112/blms/27.5.417).

Indeed \(r_1r_2r_3\ge w\), while the discrete Loomis–Whitney inequality gives \(r_{12}r_{13}r_{23}\ge w^2\). AM–GM applied to the two triples of numbers gives (15). The latter product inequality also follows directly by writing the three pair projections as zero-one matrices and applying Cauchy–Schwarz to count the compatible triples.

For an inactive region of \(t\) points, adjoin a dummy point with the inactive label in every partition. There are \(t+1\) distinct joint codes; removing the dummy's projection from each nonempty coordinate subset gives the uniform bound

\[
D\ge(1+(t+1)^{1/3})^3-8.
\tag{16}
\]

Integer ceilings may be taken in both formulas. Full cubic boxes of side \(q\) attain equality in (15) at \(w=q^3\), and, after designating one point as dummy, in (16) at \(t=q^3-1\). These formulas extend the small partition constants to arbitrary block sizes. They do not fix the example (11), whose zero blocks all have size one.

## 7. Optional: an exact half-size descent for the tight-family programme

Call a family sub-tight when \(2f_K(x)\le|K|\) for every coordinate. Let \(K\) be tight, \(|K|=2M\), and let \(t\) be tight. Its split \(L,H\) has \(|L|=|H|=M\), with \(H\) absorbing \(L\).

**Proposition 5.** If there is a containment-preserving bijection \(\phi:L\to H\), then \(L\) is sub-tight. Moreover, if \(L\) is Boolean-with-clones, then so is \(K\).

**Proof.** The matching gives \(f_H(x)\ge f_L(x)\), and sub-tightness of \(K\) gives \(f_L(x)+f_H(x)\le M\). Hence \(2f_L(x)\le M\).

Suppose \(L\) is the full Boolean family on disjoint blocks, with support \(U\). Each \(x\in U\) has \(f_L(x)=M/2\). The inequalities force \(f_H(x)=f_L(x)\). Thus containment in each matching edge is equality on \(U\): any additional occurrence there would make the total larger. Consequently each Boolean trace \(C\in L\) has exactly one upper representative

\[
\phi(C)=C\cup Q_C,\qquad Q_C\cap U=\varnothing.
\]

For \(B\in L\), absorption and uniqueness of that representative show \(Q_{C\cup B}=Q_C\). Taking \(B=U\) makes all \(Q_C\) one common set \(Q\). Hence \(H=\{C\cup Q:C\in L\}\), and restoring \(t\) appends the disjoint Boolean block \(Q\cup\{t\}\). The case \(L=\{\varnothing\}\) is immediate. ∎

Let \(\mathcal C\) consist of the non-Boolean sub-tight union-closed families with a nonempty member. A smallest member of \(\mathcal C\) must be tight. To see this, delete a minimal nonempty member from a strict counterexample. The smaller family is sub-tight and hence, by minimality, Boolean. Its nonempty support \(U\) has frequencies exactly half its even cardinality. Strict rarity in the original family forces the deleted member to avoid \(U\). Its union with the Boolean top then belongs to neither the smaller family nor the deleted member, a contradiction.

Proposition 5 therefore supplies a uniform descent within \(\mathcal C\): a successful matching either exhibits a smaller member of \(\mathcal C\), with exactly half as many members, or shows that the original family was Boolean. Thus every smallest obstruction to that stronger programme fails the perfect-matching test at every tight coordinate.

Proving that some tight coordinate always admits this matching would settle the stronger Boolean-rigidity programme. That existence statement is still open here; the direct near-perfect route in Sections 2–4 avoids requiring this stronger conclusion.

## 8. Verification and the next mathematical task

Run:

```text
python scratch/union_closed_all_sizes_20260908/checks.py
```

The completed checks:

- Enumerate all 4,959 nonempty union-closed families on four points, including all 51 tight families, and verify the perfect-matching descent identities at their 148 tight-coordinate splits.
- Verify the canonical Hall critical-family description on all 411 near-perfect absorbing pairs on three points with cardinality difference one.
- Verify both explicit failed shortcuts, including the even-lower-cardinality example (10).
- Verify the infinite-family formulas directly for \(6\le k\le10\), and equality in the projection formulas on cubic boxes of side 1 through 6.

Results are recorded in `verification.json`. **These checks do not provide nonvacuous tests of the all-rare premise of Theorem 2:** no actual counterexample to Frankl is supplied. The descent theorem is justified by its general algebraic proof. The finite tests validate the independent matching identities, combinatorial examples, and formulas.

The precise next target is now:

> For a smallest Frankl counterexample, find a maximal-frequency coordinate whose containment graph has deficiency one and, when \(|F|\equiv3\pmod4\), whose critical family contains a removable lower member; alternatively, construct a smaller counterexample from the simultaneous Hall obstructions (7)–(9).

The two unresolved issues are therefore global: why at least one split should have deficiency one, and why the deficiency-one critical family should contain a removable member in the required parity. A proof must exploit strict rarity and the fact that **every** maximal-coordinate split is constrained. The explicit counterexamples rule out proofs that use only absorption and closure. No new finite cardinality target has been substituted for these missing all-size statements.
