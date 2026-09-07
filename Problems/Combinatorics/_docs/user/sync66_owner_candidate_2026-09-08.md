# SYNC66: a coordinatewise zero-action bound excludes the two 66-member profiles (owner-supplied, UNVERIFIED, 2026-09-08)

*Supplied by the owner from an outside session. **Not reviewed by this framework's theory reviewer, not Lean-certified, not accepted.** It answers the open statement SYNC66 that Programme revision 57 handed to the theory layer: under the eight-cell hypotheses of Section 2 it claims neither 66-member profile is realizable, moving the exactly-three-tight-class lower bound of the accepted report `agent/g691_20260907-1344_alt_remains_open.md` from 66 to 68. Treat every statement below as a CLAIM to be re-derived: the load-bearing places are the restatement of that report's Theorem 22 as inequalities (9)–(10), the rank bound (11) with its two equality-classification facts, and the rank-five weight bounds in Cases C–D. The finite enumerations it cites (`verify.py`, `zero_frequency_check.py`, `verification.json`) live in `scratch/union_closed_20260908/` in the repository root and are diagnostics, not certificates.*

---

# A coordinatewise zero-action bound excludes the two SYNC66 profiles

Date: 2026-09-08. Status: **proposed proof for independent review; not Lean-certified, not yet accepted by the Asterism framework**.

## 1. Result and scope

Under the precise eight-cell hypotheses below, neither of the two profiles

| outside points | \(|Z|\) | singleton sizes | opposite double sizes | \(|H|\) |
|---|---:|---|---|---:|
| 7 | 4 | 11,11,11 | 7,7,7 | 8 |
| 7 | 5 | 10,10,11 | 7,7,8 | 8 |

can have every outside frequency at most 32. This is the boundary called **SYNC66** in programme revision 57.

The new step retains the coordinate incidence of each zero-forced avoiding top. The previous scalar estimate retains only its cardinality. A further correction counts the incidences required to separate the points *inside* one zero block. Together these bounds remove every five-member zero cell and reduce the four-member zero cell to four shapes. Short arguments exclude those four shapes.

The reduction uses a small, completely specified finite table of zero families, reproduced by two independent enumerations in the accompanying code. The final four exclusions are mathematical arguments, not solver outputs. Conditional on the accepted report's reduction to these two profiles, this advances its exactly-three-tight-class branch from \(|K|\ge66\) to \(|K|\ge68\). It does **not** settle ALT, the branches with more tight classes, or Frankl's conjecture.

**Prior work used.** The setting, product-partition lemma, scalar zero-action bound, and small partition costs come from [the accepted 2026-09-07 report](../../Problems/Combinatorics/_docs/agent/g691_20260907-1344_alt_remains_open.md), especially Theorem 1, Lemma 11, Theorem 22, Lemma 23, Theorem 37, Theorem 42, and Proposition 43. The elementary avoiding-top construction is prior work, not claimed here as new. The coordinatewise inequality, its internal-block correction, and their application to the complete two-profile boundary are the proposed contribution. The proof below does not depend on missing `.attempts/` review scripts or on a claimed proof of the original conjecture.

## 2. Explicit hypotheses and notation

Let \(X\) be a set of seven points. Let \(Z,A_1,A_2,A_3\) be finite union-closed families of subsets of \(X\). For nonempty \(I\subseteq\{1,2,3\}\), put

\[
F_I=\mathop{\bigvee}_{i\in I}A_i,
\qquad F\vee G=\{f\cup g:f\in F,g\in G\},
\qquad H=F_{123}.
\]

Assume:

1. \(\varnothing\in Z\), and every nonempty member of \(Z\) has size at least three.
2. Each of the seven \(F_I\) has empty intersection, and every member has size at least two.
3. \(Z\vee A_i\subseteq A_i\) for each \(i\). Consequently \(Z\) stabilizes every \(F_I\).
4. \(H\) has support \(X\) and separates its seven points (its active incidence columns are distinct).
5. The cell cardinalities are one of the two displayed profiles.
6. For each \(x\in X\),
   \[
   f_Z(x)+\sum_{I\ne\varnothing}f_{F_I}(x)\le32.
   \tag{1}
   \]

These are necessary hypotheses already supplied by the accepted report in the branch being studied. We prove that they are inconsistent. The quantities count occurrences in different cells separately, as they should for the original family with three tagged tight coordinates.

Write \(U=\bigcup Z\), \(v=|U|\), and let \(B_1,\ldots,B_r\) be the nonzero incidence classes of \(Z\), of sizes \(w_i\). These are the **zero blocks**. Put

\[
m_i=\bigcup\{z\in Z:z\cap B_i=\varnothing\},
\quad q_i=|m_i|,
\quad p_i=(q_i-2)_+,
\quad z_j=f_Z(x)\quad(x\in B_j).
\]

Every nonzero cell has all of \(U\) in its support, and its active classes refine the zero blocks, with additional active classes in \(X\setminus U\). For a cell \(F\), write \(c_i(F)\) for its number of classes in \(B_i\), and \(d(F)\) for its number in \(X\setminus U\). Define

\[
C_i=\sum_{I\ne\varnothing}c_i(F_I),
\qquad D=\sum_{I\ne\varnothing}d(F_I).
\]

Here the partition of a product is the common refinement of the partitions of its factors, retaining inactivity until the final inactive class is omitted. To verify this fact: equal columns in both factors remain equal in every union; conversely each factor stabilizes the product, so a product class cannot be split by a factor. Empty intersection supplies a member avoiding any active product class, proving the latter assertion directly.

We use the following valid lower bounds from the accepted report:

\[
C_i\ge\ell(w_i),\quad
\ell(1)=7,\ \ell(2)=11,\ \ell(3)=15,\ \ell(4)=17,
\quad\ell(w)=6+w\ (w\ge5),
\tag{2}
\]

\[
D\ge\mu(7-v),\quad
\mu(0)=0,\ \mu(1)=4,\ \mu(2)=8,\ \mu(3)=10,
\quad\mu(t)=t+3\ (t\ge4).
\tag{3}
\]

The last formulas are lower bounds, not claims of sharpness for all larger arguments.

## 3. The coordinatewise inequality

**Lemma 1.** For \(x\in B_j\),

\[
f_Z(x)+\sum_{I\ne\varnothing}f_{F_I}(x)
\ \ge\ z_j+7+D+\sum_{i:\,B_j\subseteq m_i}C_i.
\tag{4}
\]

**Proof.** Fix a nonzero cell \(F\). For any active class \(Q\) of \(F\), its avoiding top

\[
n_Q=\bigcup\{f\in F:f\cap Q=\varnothing\}
\]

belongs to \(F\). It is proper in the support top. Avoiding tops belonging to distinct classes are distinct: membership avoids \(Q\) exactly when the member is contained in \(n_Q\), so equal avoiding tops would mean equal columns.

If \(Q\subseteq B_i\), unioning an \(F\)-member avoiding \(Q\) with any zero member avoiding \(B_i\) shows \(m_i\subseteq n_Q\). Thus every such \(n_Q\) contains \(x\) when \(B_j\subseteq m_i\). If \(Q\subseteq X\setminus U\), the same argument with the zero top gives \(U\subseteq n_Q\). The support top of \(F\) contains \(x\) as well. These are all distinct members. Therefore

\[
f_F(x)\ge1+d(F)+\sum_{i:\,B_j\subseteq m_i}c_i(F).
\]

Sum over the seven nonzero cells and add \(z_j\). ∎

In particular, set

\[
L_j=z_j+7+\mu(7-v)+
\sum_{i:\,B_j\subseteq m_i}\ell(w_i).
\tag{5}
\]

Every point of \(B_j\) has frequency at least \(L_j\).

**Lemma 2 (incidences inside a zero block).** In addition to the witnesses counted in (4), count the incidences of \(B_j\) in the avoiding tops belonging to classes *inside \(B_j\)*. If their total over the seven cells is \(E_j\), then

\[
\sum_{x\in B_j} f_K(x)
\ge w_j\left(z_j+7+D+\sum_{i:\,B_j\subseteq m_i}C_i\right)+E_j,
\tag{6}
\]

where \(f_K\) abbreviates the left side of (1). Moreover

\[
E_j\ge\binom{w_j}{2},
\qquad w_j=3\ \Longrightarrow\ E_j\ge10.
\tag{7}
\]

**Proof.** The avoiding tops associated with classes in \(B_j\) are absent from the list in Lemma 1, because \(m_j\) avoids \(B_j\). Hence their incidences are additional, with no double counting.

For two distinct active classes \(Q,R\) in one cell, either \(n_Q\) contains \(R\), or \(n_R\) contains \(Q\), or both. Otherwise the two incidence columns would be identical. Their contribution to the sum of the internal avoiding-top sizes is consequently at least \(\min(|Q|,|R|)\). Summing over pairs of classes counts different incidences. In \(H\), the classes within \(B_j\) are single points, giving the first bound in (7).

For a three-point block, a binary partition contributes at least one internal incidence and the discrete partition at least three. If a singleton partition is discrete, it and its two incident double partitions and \(H\) contribute at least twelve. Otherwise at least two singleton partitions are different binary partitions. If the third is trivial, the singleton contribution is at least two, the double contribution at least \(3+1+1=5\), and \(H\) contributes three: total ten. If the third is binary, the singleton contribution is at least three, and the doubles still contribute at least five; the total is at least eleven. This proves the stated uniform ten. ∎

Thus the necessary block test

\[
\boxed{w_jL_j+\binom{w_j}{2}\le32w_j}
\tag{8}
\]

is strictly stronger than just \(L_j\le32\). In particular a block of size at least two cannot have \(L_j=32\).

For example, \(Z=\{\varnothing,Pq,Pr,Pqr\}\), with \(|P|=2\), has three inactive points. For \(x\in P\), (5) gives

\[
f_K(x)\ge3+7+7+7+10=34>32.
\]

This excludes the entire four-point zero-support branch without assumptions about the three singleton support sizes.

## 4. The small finite zero-family reduction

We combine (8) with the prior scalar bound, restating its exact formula to make the enumeration independently reproducible. Form the sorted list \(\beta_1\le\cdots\le\beta_7\) containing \(w_i\) copies of \(\max(2,q_i)\), together with \(7-v\) copies of \(v\). Put

\[
\Delta=\sum_{j=1}^7\left(\max(\beta_j,2,j-1)-\beta_j\right).
\]

Theorem 22's avoiding-top weight argument, summed over the cells, gives

\[
W(K)\ge132-2a+7(v-2)+W(Z)+\sum_i p_i C_i+(v-1)D+\Delta,
\tag{9}
\]

where \(a=|Z|\). In particular

\[
W_0(Z):=132-2a+7(v-2)+W(Z)
 +\sum_i p_i\ell(w_i)+(v-1)\mu(7-v)+\Delta\le224.
\tag{10}
\]

For clarity, the scalar argument does not assume any unattained combination of minima is realizable. In each cell its distinct avoiding tops have the prescribed zero-forced sizes; its support has size at least \(v+d(F)\); all remaining members have size at least two. The usual frequency ordering gives the separating lower list \(\max(2,j-1)\) on those same avoiding tops. In \(H\) one may add precisely \(\Delta\); taking coordinatewise maxima of the sorted lower lists is valid. This is the proof of the cited bound, and also explains why later improvements in singleton cells may be added without duplicating \(\Delta\).

Here is the complete table of zero-family orbits satisfying (10). Each decimal mask denotes a union of the blocks in the stated order, with block bits \(1,2,4,8\). The last column is

\[
\max_j\left(w_jL_j+\binom{w_j}{2}-32w_j\right).
\]

A positive entry excludes the row by (8).

| a | block sizes | zero masks | \(W_0\) | \((L_j)\) | block excess |
|---:|---|---|---:|---|---:|
|4|3,3|0,1,2,3|217|28,28|−9|
|4|3,4|0,1,2,3|223|26,24|−15|
|4|1,1,2|0,5,6,7|195|26,26,34|5|
|4|1,1,3|0,4,5,7|211|24,16,32|3|
|4|1,1,3|0,5,6,7|219|24,24,32|3|
|4|1,2,2|0,3,5,7|212|40,28,28|8|
|4|1,2,2|0,3,6,7|215|28,36,24|9|
|4|1,1,4|0,4,5,7|223|20,12,28|−10|
|4|1,2,3|0,3,5,7|223|40,28,24|8|
|4|1,2,3|0,3,6,7|223|28,36,20|9|
|4|1,2,3|0,4,5,7|215|24,12,32|3|
|4|1,2,3|0,4,6,7|219|12,20,32|3|
|4|1,2,4|0,3,6,7|223|26,34,16|5|
|4|1,2,4|0,4,5,7|224|20,8,28|−10|
|4|1,3,3|0,2,3,7|213|24,32,8|3|
|4|1,3,3|0,2,6,7|221|8,32,16|3|
|4|2,2,3|0,4,5,7|220|20,8,32|3|
|5|1,1,3|0,4,5,6,7|220|24,24,33|6|
|5|1,1,1,1|0,7,11,13,15|203|42,34,34,34|10|
|5|1,1,1,2|0,7,9,11,15|223|44,36,28,32|12|
|5|1,1,1,2|0,9,10,11,15|219|32,32,16,40|17|
|5|1,1,2,2|0,5,6,7,15|223|32,32,40,12|17|
|5|1,1,2,3|0,5,6,7,15|221|32,32,40,8|17|

**Completeness of the finite test.** Since \(\varnothing\in Z\), its distinct active avoiding tops are proper members, giving \(r\le a-1\). Enumerate \(1\le r\le a-1\), \(3\le v\le7\), and sorted positive \(r\)-tuples of sum \(v\). Among the proper nonempty masks of physical size at least three, choose exactly \(a-2\). Adjoin empty and top. Retain only union-closed choices having \(r\) different nonzero incidence columns. Compute (10), and identify masks only under permutations of equal-size blocks. These operations exhaust all possible zero families, including those whose nonempty members have a common point, and those with smaller support. Each arithmetic calculation is an integer calculation on at most sixteen block masks.

The script `zero_frequency_check.py` performs precisely this enumeration. `verify.py` independently enumerates physical subsets, without starting from block partitions, and checks that it produces the same 23 orbits. No factor-rank filter, FC theorem, unverified realization assumption, or external classification is used to discard a zero shape here.

All six \(a=5\) rows have positive block excess. **The second SYNC66 profile is excluded.** Four \(a=4\) rows remain.

## 5. Four remaining shapes

For this section all singleton sizes are eleven and all double sizes seven. Each singleton has rank at least four, since there are at most \(2^r-1\) nonempty masks on \(r\) active classes. Each has rank at most five: rank six would force both incident seven-member double cells to have exactly its six classes and support; both other singleton partitions would then be coarser, contradicting the seven classes of \(H\). Thus

\[
4\le\rho(A_i)\le5.
\tag{11}
\]

Two equality facts about the costs (2) will be useful:

- A three-point block with total class count 15 has singleton rank pattern \((3,1,1)\) or \((2,2,1)\), up to permutation. In either case the singleton ranks sum to five. In the second pattern the binary cuts must differ.
- A four-point block with total class count at most 18 in fact has count 17 and singleton ranks \((2,2,1)\), with the two binary cuts having discrete common refinement.

To prove these facts, enumerate the ranks of three partitions on three or four points. On three points, a discrete singleton already contributes three in itself, both incident products, and the full product; equality 15 forces the other two to be trivial. Without a discrete singleton, global separation requires two different binary cuts; a third binary cut raises the total to at least 17. On four points, a rank-four singleton costs at least 19. A rank-three singleton must have a second nontrivial partition to obtain discrete common refinement, again costing at least 19. If all ranks are at most two, three nontrivial partitions cost at least 19; exactly two can reach four global classes only via a four-class common refinement, giving \(5+8+4=17\).

### Case A: two disjoint triples and one inactive point

Let \(Z=\{\varnothing,P,Q,P\cup Q\}\), \(|P|=|Q|=3\), with one inactive point \(e\). Apply the stronger form (6)–(7) to \(P\):

\[
96\ge\sum_{x\in P}f_K(x)\ge3(2+7+C_Q+D)+10.
\]

Hence \(C_Q+D\le19\). Since \(C_Q\ge15\) and \(D\ge4\), both are equalities. Applying the same argument to \(Q\) gives \(C_P=15\).

For a single inactive point, \(D=4\) means it occurs in exactly one singleton cell: if it occurred in two, it would be active in those two singletons, all three double cells, and \(H\), giving \(D\ge6\). Each triple block has singleton rank sum five by the equality fact above. Therefore

\[
\sum_i\rho(A_i)=5+5+1=11,
\]

contrary to (11), which requires at least twelve. This excludes Case A without using the prior review's separate exclusion of this shape.

### Case B: disjoint blocks of sizes three and four

Let \(Z=\{\varnothing,P,Q,P\cup Q\}\), \(|P|=3\), \(|Q|=4\), with full support. Here \(W_0=223\), \(p_P=2\), and \(p_Q=1\). The actual bound (9) is

\[
W(K)\ge223+2(C_P-15)+(C_Q-17).
\]

The budget 224 forces \(C_P=15\) and \(C_Q\le18\). Thus \(C_Q=17\), with singleton ranks \((2,2,1)\). In the singleton where \(Q\) is unsplit, (11) requires three classes on \(P\). Equality \(C_P=15\) then makes the other two restrictions on \(P\) trivial. Those two singletons have rank \(1+2=3\), contradicting (11).

### Case C: a chain on six support points

Let

\[
Z=\{\varnothing,P,Pq,Pqr\},\qquad |P|=4,
\]

where \(q,r\) are single points and one point \(e\) is inactive. Here \(W_0=223\), and the coefficient of \(D-4\) in (9) is five. Thus the budget forces \(D=4\), so precisely one singleton contains \(e\).

The other two singleton cells have physical support six and rank four or five. Each has eleven members and weight at least 32. For rank four, the possible block weights on six points allowing eleven members of size at least two give a raw distinct-mask lower bound of at least 36. For rank five there is one double block and four unit points, and the lower bound 32 is the eleven-member case of the prior Theorem 42.

Here is also a direct proof of that rank-five bound. Let \(B\) be the double block, and let \(p\) count proper members of weight two. Let \(E\) be the sum of weight excesses above three among the other proper members. The weight equals \(36-p+E\). If \(B\) is present, its union with each unit pair supplies a different weight-four member, giving \(E\ge p-1\). Otherwise all weight-two members are among six unit pairs. Weight at most 31 would require \(p-E\ge5\). Four unit pairs force the unit top, so \(p\ge5\) forces \(E\ge1\), hence \(p=6\). The six pairs force four unit triples and the unit top, requiring eleven proper members although only ten slots exist. Contradiction.

The scalar calculation charged each of these two singletons only

\[
2\cdot11+(6-2)+(4-2)+(5-2)=31.
\]

They therefore add at least two to \(W_0=223\), giving \(W(K)\ge225>224\).

### Case D: a chain on seven support points

Let

\[
Z=\{\varnothing,P,Pq,PqR\},\qquad |P|=4,\quad |R|=2,
\]

where \(q\) is a single point. Here \(W_0=224\), and the coefficient of \(C_R-11\) is three. Hence \(C_R=11\). Exactly one singleton splits \(R\); if two did, the two-point block would have total class count at least 13.

Consider either singleton where \(R\) remains unsplit. Its support is seven and its rank is four or five. In rank four, its block weights are \((1,2,2,2)\) or \((1,1,2,3)\); selecting the ten lightest proper masks of weight at least two gives weight at least 39 or 42, including the top. In rank five its weights must be \((1,1,1,2,2)\).

For these rank-five weights, the raw eleven-member weight minimum is 32. Equality requires all five weight-two masks: the two double blocks and the three pairs of unit points. Its remaining five proper members would all have weight three. But unioning the two double blocks forces a proper weight-four member, impossible in that equality list. Therefore its weight is at least 33.

The scalar bound charged this singleton only

\[
2\cdot11+(7-2)+(4-2)+(5-2)=32.
\]

Even one such singleton raises the total above 224. This excludes Case D and finishes the proof of SYNC66 under the hypotheses in Section 2. ∎

## 6. Verification and suggested formalization

Run from the repository root:

```text
python scratch/union_closed_20260908/verify.py
python scratch/union_closed_20260908/zero_frequency_check.py
```

The completed checks enumerate all **4,960** union-closed families on four points (including the empty family), test the local coordinatewise inequality and its internal-incidence correction on **2,343,314** actual absorbing pairs, enumerate the relevant common partition refinements, and compare the weighted zero-family enumeration with an independent physical-subset enumeration. Both zero enumerations give **23** orbits, of which **four** survive the block test. The active class minima are 7,11,15,17, the inactive minima are 4,8,10, and the three-point internal-incidence minimum is ten. Exact results are recorded in `verification.json`. These are reproducible finite checks, not Lean certificates or a formal proof of all possible eight-cell diagrams.

Suggested dependency order for framework intake:

1. Prove the single-cell coordinatewise avoiding-top lemma, retaining the *sets* \(m_i\), not only \(|m_i|\).
2. Prove the internal-block correction, including the three-point lower bound ten.
3. Formalize the explicit finite zero-mask check (23 orbits before the block test, four after it). An executable finite check can replace the displayed arithmetic table.
4. Prove the two small partition equality classifications and the four residual exclusions.
5. Conclude the exact SYNC66 statement with all Section 2 premises explicit; combine with the existing 66-member reduction only afterward.

The next unresolved boundary is at least 68 members in the exactly-three-tight-class branch, provided this submission is accepted. No completeness claim is made about other branches of ALT or about the next cardinality boundary.
