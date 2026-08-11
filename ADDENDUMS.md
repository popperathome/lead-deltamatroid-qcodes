# Addendums — lead-deltamatroid-qcodes

## 2026-08-11 · Entry 1 — Literature-collision check (kill criterion 2) + conventions freeze

- **Who:** Claude (Fable 5) orchestrator, Claude Code session; web search.
- **What:** searched the three queries frozen in idea.md ("Lorentzian weight
  enumerator", "log-concave quantum code", "matroid quantum enumerator") plus
  "log-concavity weight distribution self-dual code", "Lorentzian polynomial
  coding theory", and combined `"log-concave" + "stabilizer code" + weight
  enumerator` (arXiv + web, 2026-08-11). Fetched and read abstracts/content of
  the two closest hits.
- **Result:** no collision.
  - Closest work is **arXiv:2410.04412 "Log-Concave Sequences in Coding
    Theory"** — classical linear codes only (Hamming, Reed–Muller, MDS); no
    quantum/stabilizer codes, no additive GF(4) codes, no Lorentzian
    polynomials. Useful side-effect: it defines a "log-concave code" via its
    **nonzero** weight distribution, which independently validates the V2
    convention frozen below as the standard object in the classical
    literature.
  - **Chen–Ren arXiv:2409.03576** (cited in idea.md) is purely
    invariant-theoretic (Gleason-type generator sets for B, double, and
    complete enumerators of formally self-dual quantum codes); it contains no
    log-concavity/unimodality/Lorentzian content and no systematic tables of
    small-code enumerators, so it does not pre-empt any part of this test.
  - No hits for Lorentzianity/ULC of quantum weight enumerators; papers on
    log-concavity and on quantum enumerators exist only independently.
    arXiv:2607.15548 ("Quantum states supported by matroids") checked: no
    enumerator/log-concavity content.
- **Bears on:** kill criterion 2 — **NOT FIRED**.

### Conventions frozen before any compute (this entry predates all runs)

Motivation: essentially no stabilizer code has weight-1 stabilizers, so the
raw A-sequence is (1, 0, A₂, …) and fails log-concavity at j=1 for *every*
code; even-weight self-dual codes have internal zeros at every odd j; the
complete enumerator's support always contains the isolated identity vertex
(n,0,0,0), so raw M-convexity fails universally. Untreated, kill criterion 1
would "fire" as a pure artifact. Therefore, per enumerator we compute all of:

- **V1 (strict):** the raw coefficient sequence / polynomial as defined.
  Reported honestly (expected universal failure for the spike reason above).
- **V2 (support-restricted, PRIMARY):** coefficients from the first nonzero
  index j ≥ 1 through max support (the "nonzero weight distribution" of
  arXiv:2410.04412). Multivariate analog: P − x_I^n (enumerator of S \ {I}).
- **V3 (even-reindexed):** when supp(A)\{0} ⊆ 2ℤ, the halved-degree reindexed
  sequence (A₀, A₂, A₄, …); also V2∘V3.

Enumerators tested: **A** always (for k=0 it is the full weight distribution
of the additive GF(4) code); **B** and **B−A** additionally for k > 0 (B−A is
spike-free with support starting at d). For k=0, B=A and B−A≡0 (skipped,
recorded as degenerate).

Checks, all in exact integer arithmetic: C1 no internal zeros; C2
log-concavity a_j² ≥ a_{j−1}a_{j+1}; C3 ultra-log-concavity — by Brändén–Huh
this is *exactly* bivariate Lorentzianity of the homogenization, so C3
replaces idea.md's "sampled Hessian-signature checks" with a strictly
stronger exact test (deviation recorded here, not a weakening); C4 Lorentzianity
of the 4-variable complete enumerator via the Brändén–Huh criterion (M-convex
support + every (n−2)-fold coordinate partial's 4×4 integer Hessian has at
most one positive eigenvalue, counted exactly via integer characteristic
polynomial + Descartes' rule — valid because symmetric matrices have real
spectra). Nesting C4 ⇒ C3 ⇒ C2 asserted per code.

**Kill criterion 1 pre-registration:** primary combination = (A, V2, C2) for
k=0 codes and (B−A, V2, C2) for k>0 codes. The criterion FIRES iff every
candidate subclass (deduplicated by (n,k,A,B,complete-enumerator)
fingerprint, ≥ 20 non-trivial codes; codes with n ≤ 2 or coefficient
sequences of length ≤ 2 excluded as trivial) has fail fraction ≥ θ = 0.10
and no subclass has fail fraction 0. Survival ("characterizes subclass X") =
at least one pre-registered subclass with ≥ 20 deduped codes at exactly 0
failures while the random-stabilizer control population fails at ≥ θ.
Candidate subclasses: self-dual (graph states), even self-dual, GF(4)-linear,
CSS-as-given, constructed CSS, distance-optimal, named codes, and pairwise
intersections meeting the size floor. C3/C4 and other variants are reported
as sharpening/scope, not as kill-criterion inputs. The random ensemble is a
seeded generic control, not a uniform census; recorded as such.

## 2026-08-11 · Entry 2 — Run 1 (full n ≤ 8 sweep)

- **Who:** codex (gpt-5.6-sol) subagent implementing `test/sweep.py` per the
  Entry-1 freeze, directed by Claude (Fable 5) orchestrator; smoke test
  (--max-n 5) independently rerun by the wrapper agent; full run executed by
  the orchestrator. `test/sweep.py` was committed to this repo *before* the
  full run (commit d85867e).
- **Command:**
  `podman run --rm -v "$PWD":/work:z docker.io/library/python:3.12-slim python /work/test/sweep.py --seed 20260811`
  (Python 3.12.13; stdlib only — no pip at all, a strictly-more-reproducible
  deviation from the CLAUDE.md podman template). Seed 20260811. Wall-clock
  73.7 s.
- **Validation gate (all hard-asserted, PASS):** graph iso-class counts equal
  OEIS A000088 through n=8 (…, 1044, 12346; 13,598 total); graph-state
  closed-form enumerator vs symplectic spanning on all 52 graphs n ≤ 5;
  named-code (n,k,d) self-checks ([[4,2,2]], [[5,1,3]], Steane [[7,1,3]],
  [[8,3,2]]); MacWilliams transform vs direct centralizer enumeration on 816
  codes; Brändén–Huh checker self-tests incl. Bell-pair sanity (V1 fails at
  j=1 as predicted by the freeze).
- **Catalog:** 23,465 raw codes → 16,492 deduplicated fingerprints
  (13,598 graph states = all self-dual codes up to LC; exhaustive CSS
  subspace pairs n ≤ 5 (6,363) + 500 seeded pairs each n = 6,7,8; 4 named;
  1,900 seeded random controls n=4..8, k=1..n−2).
- **Results, primary registered combination (A,V2,C2 for k=0; B−A,V2,C2 for
  k>0), deduplicated, non-trivial:**
  | subclass | n | fail | frac |
  |---|---:|---:|---:|
  | selfdual_graph | 13268 | 8456 | 0.637 |
  | even_selfdual | 254 | 254 | 1.000 |
  | css_constructed | 1264 | 497 | 0.393 |
  | distance_optimal | 796 | 60 | 0.075 |
  | css_constructed∩distance_optimal | 150 | 9 | 0.060 |
  | selfdual_graph∩distance_optimal | 297 | 31 | 0.104 |
  | random_control | 1955 | 548 | 0.280 |
  - The 63.7% self-dual failure rate is genuine log-concavity violation, not
    a zero artifact: A/V2/C1 (internal zeros) fails at only 4.6% for
    selfdual_graph. The even_selfdual 100% failure IS the predicted parity
    artifact (odd-weight interior zeros), which the frozen V3 handles:
    under A/V2∘V3, even_selfdual fails C1 at 0.000 and C2 at 0.020, and
    selfdual∩distance_optimal passes C1, C2, **and C3 (exact bivariate
    Lorentzianity) at 0/31**.
  - Sharpening tables (deduplicated fail fractions): A/V2/C3 (ULC) fails
    ~1.000 selfdual, 0.765 distance_optimal — ultra-log-concavity is
    generically false even where log-concavity holds; A/V2∘V3/C3:
    distance_optimal 0.033, selfdual∩distance_optimal 0.000. B−A/V2/C2
    (k>0): distance_optimal 0.053 vs random_control 0.280. Complete
    4-variable enumerator C4: fails ≥ 0.89 everywhere (V1 and V2) — only 6
    of 13,268 self-dual codes pass; the multivariate/M-convex form of the
    claim is essentially dead generically at small n (which codes the 6 are
    is left to the review).
- **Criterion mapping:** kill criterion 1 **NOT FIRED** — pass/fail is
  strongly structured, not noise: distance_optimal (0.075) and
  css∩distance_optimal (0.060) sit far below the control (0.280) and below
  θ=0.10. The pre-registered *survival trigger* (a ≥20-member subclass at
  exactly zero failures under the primary combination) also did **not**
  trigger — zero-failure subclasses appear only under the V2∘V3 sharpening.
  Kill criterion 2: not fired (Entry 1).
- **Audit trail:** `test/results-seed20260811.json` (45.19 MiB, includes
  per-code generators/graph edges/derived seeds so no RNG replay is needed),
  SHA-256
  `fa05cb3110625a58eec80c33b160a59bbc329f2fc15d98e87eb3bfb888bbd3b1`.
- **Flagged for review (see entry 3):** (i) independent verification
  of the 63.7% self-dual V2/C2 failure rate and of the distance-optimal
  cleanliness (these carry the verdict); (ii) gf4_linear subclass came out
  as n=1 deduped member — suspiciously low, possible flag bug; (iii)
  css_decomposable ≡ css_constructed exactly in the dedup tables — verify
  the flag isn't degenerate; (iv) hard-coded best-known-distance table
  (from memory, incl. existence of [[8,3,3]] ⇒ [[8,3,2]] not optimal) vs
  codetables.de; (v) 3/4 named codes failing B−A/V2/C2 (incl. [[5,1,3]]?) —
  recompute by hand; (vi) Descartes/char-poly eigenvalue routine on
  near-boundary Hessians; (vii) criterion-mapping code vs the frozen
  Entry-1 text.

## 2026-08-11 · Entry 3 — Adversarial review of run 1

- **Who:** Claude Opus subagent, independent reimplementation from the
  definitions (own symplectic/enumerator/centralizer code written before
  reading `sweep.py`; scripts in session scratchpad, recorded here by their
  findings). Same container image (Python 3.12.13); float cross-paradigm
  checks used pip `numpy==2.5.2` (pinned, recorded). Artifact SHA-256
  verified against entry 2.
- **What survived (full, not sampled):** A and B recomputed for **all 23,465
  codes** (B via direct centralizer nullspace, no MacWilliams): 0 mismatches;
  B additionally brute-forced over all 4^n Paulis on 154 codes: identical.
  Dedup fingerprints rebuilt from scratch: 16,492 groups, identical sets.
  Every requested crosstab cell reproduced exactly from independent code
  (selfdual 8456/13268, distance_optimal 60/796, control 548/1955,
  even_selfdual 254/254, V2∘V3 cells incl. selfdual∩distance_optimal 0/31).
  All 6 C4 passers and 5 spot-checked failures confirmed with numpy
  eigvalsh, exact recorded violations reproduced. Named codes verified by
  hand: [[5,1,3]] A=(1,0,0,0,15,0), B−A support starts at d=3, and its
  recorded B−A/V2/C2 failure is mathematically correct (V2 slice (30,0,18),
  0² < 30·18); Steane and [[8,3,2]] failures likewise real; 3/4 named
  failing is correct. Descartes/char-poly eigenvalue counting vs numpy on
  48,184 Hessians (incl. 30,945 with exact zero eigenvalues): 0
  disagreements, zeros never counted positive. Variant slicing checked on 14
  adversarial sequences: 0 disagreements. Criterion code diffed word-by-word
  against the Entry-1 freeze: faithful, control intersections correctly
  excluded from candidates.
- **Findings:**
  - **F1 (MAJOR, changes numbers):** hard-coded distance table has
    `[[7,2]] best d = 3`; correct value is **2** (codetables.de
    lower=upper=2; CRSS quant-ph/9608006 Table III). Corrected cells:
    distance_optimal 60/796=0.0754 → **68/855=0.0795**;
    css∩distance_optimal 9/150=0.0600 → **12/155=0.0774**;
    distance_optimal∩control 19/349 → 24/403=0.0596. All other entries of
    the table confirmed correct, including existence of [[8,3,3]]
    (Gottesman) ⇒ [[8,3,2]] rightly non-optimal, and the k=0 row matching
    Danielsen–Parker Table 4 (1,2,2,2,3,4,3,4). **Verdict impact: none**
    (binding candidates stay below θ=0.10; nothing reaches 0). Margin
    caveat: binding candidate is ~0.02 below θ — the table is load-bearing
    and must be cited data, not memory.
  - **F2 (MAJOR, scope):** the pre-registered gf4_linear subclass was never
    actually tested: ω-closure is **not** LC-invariant, and 0/13,598 graph
    representatives are ω-closed (both hexacode graph representatives test
    negative). An undocumented `k==0` clause additionally excluded 68
    genuinely ω-closed codes (incl. [[5,1,3]], Steane). Without the clause:
    16 non-trivial deduped members, fail 6/16 — still under the floor of
    20; verdict unaffected, but this candidate produced no evidence.
  - **F3 (MAJOR, interpretation):** "13,598 graph states = all self-dual
    codes up to LC" is wrong as a census: there are only **290**
    LC-inequivalent self-dual additive GF(4) codes for n ≤ 8
    (Danielsen–Parker). The 63.7% is graph-isomorphism-weighted; per
    distinct A-enumerator the failure fraction rises with n
    (n=4: 0.20 → n=8: **0.87**). Direction robust under any weighting;
    the specific number is a property of the frozen fingerprint scheme.
  - **F4 (MINOR):** six degenerate [[n,n,1]] codes (S={I}) pass A/V2
    vacuously (V2=[]), inflating denominators by 6; primary combination
    unaffected (k>0 uses B−A).
  - **F5 (MINOR, explained):** css_decomposable ≡ css_as_given in dedup
    tables because the flag genuinely almost never fires outside CSS
    constructions (16 raw exceptions, all merged by OR-semantics into
    css_as_given groups); star-graph representatives are NOT
    CSS-decomposable (e.g. Y0Y1Z2 ∈ S); like gf4_linear the flag is
    representative-dependent, not LC-invariant.
  - **F6 (MINOR, scientifically sharpest):** the only 6 self-dual codes
    passing complete-enumerator Lorentzianity (C4) are the **edgeless
    graphs** — unentangled product states |+⟩^⊗n with enumerator
    (x_I+x_X)^n. At n ≤ 8 the multivariate/M-convex form of the claim
    holds **only on trivial product states**.
  - **F7/F8/F9 (MINOR):** css_decomposable not OR'd during dedup
    aggregation (empirically zero impact); d written as null on
    non-representative records; distance_optimal unpopulated at
    [[6,1]],[[6,4]],[[7,2]],[[8,3]],[[8,6]] because seeded sampling at
    n=6..8 never found the optimum — the subclass is biased toward easy
    (n,k) and is 44% random controls.
- **Bears on:** kill criterion 1 — **NOT FIRED stands** under both as-run
  and corrected tables (FIRED=False, SURVIVAL=False replayed
  independently); kill criterion 2 — not fired. A corrected run 2 (F1, F2
  clause, F4) is warranted for the record, not the verdict.

## 2026-08-11 · Entry 4 — Run 2 (corrected; authoritative)

- **Who:** codex subagent applying the Entry-3 fixes (F1 [[7,2]] best d
  3→2 with cited provenance; F2 gf4_linear k==0 clause removed; F4
  [[n,n,1]] degenerate codes marked trivial; F7 css_decomposable OR'd in
  dedup; F8 d written on all member records) plus a supplementary
  per-distinct-A-enumerator table addressing F3; smoke-tested independently
  by the wrapper agent; full run by the orchestrator. Script committed
  before the run (commit 4e90cef). Frozen criterion logic unchanged.
- **Command:** identical to entry 2 (same image, same seed 20260811; the
  script now writes `test/results-run2-seed20260811.json`). Wall-clock
  71.8 s. Validation gate: PASS (all five checks, unchanged).
- **Results (primary registered combination, deduplicated, non-trivial):**
  | subclass | n | fail | frac |
  |---|---:|---:|---:|
  | selfdual_graph | 13268 | 8456 | 0.637 |
  | even_selfdual | 254 | 254 | 1.000 |
  | css_constructed | 1258 | 497 | 0.395 |
  | distance_optimal | 849 | 68 | 0.080 |
  | css_constructed∩distance_optimal | 149 | 12 | 0.081 |
  | selfdual_graph∩distance_optimal | 297 | 31 | 0.104 |
  | gf4_linear | 10 | 6 | 0.600 |
  | random_control | 1955 | 548 | 0.280 |
  Matches the Entry-3 corrected predictions exactly (denominators shifted
  −6 by the F4 trivial exclusion). gf4_linear is now honestly populated
  (10 deduped members incl. [[5,1,3]] and Steane) but remains below the
  floor of 20 — registered as untestable at n ≤ 8 rather than tested.
- **Per-distinct-A sharpening (F3):** distinct self-dual A-enumerators
  failing A/V2/C2, by n: 3: 0/3, 4: 1/5, 5: 6/10, 6: 15/23, 7: 39/46,
  8: 101/116 (overall 162/203 = 0.80) — the failure rate *rises* with n
  under per-enumerator counting. Under A/V2∘V3/C2: 2/203.
- **Verdict:** kill criterion 1 **NOT FIRED** (distance_optimal 0.080 and
  css∩distance_optimal 0.081 vs control 0.280; structure, not noise); the
  pre-registered survival trigger (an exact-zero subclass under the
  primary) again did not trigger. Kill criterion 2 not fired (entry 1).
  → **status SURVIVING**, in a sharpened form:
  - The naive claim ("self-dual ⇒ log-concave enumerator") is **false**:
    a majority of self-dual codes at n ≤ 8 violate V2 log-concavity
    (0.80 of distinct enumerators; worsening with n), and
    ultra-log-concavity (= bivariate Lorentzianity) fails almost
    everywhere in V2.
  - The surviving form: pass/fail is strongly structured by
    **distance-optimality** (0.080 vs 0.280 control; B−A/V2/C2 0.053 for
    k>0), and under the even-reindexed variant the structure is nearly
    exact — selfdual∩distance_optimal passes C1+C2+C3 at **0/31**, and
    only 2/203 distinct self-dual enumerators fail V2∘V3/C2.
  - The multivariate arm is dead at n ≤ 8 except on trivial product
    states: the only C4-Lorentzian complete enumerators among 13,268
    self-dual codes are the six edgeless graphs, (x_I+x_X)^n.
- **Audit trail:** `test/results-run2-seed20260811.json` (45.18 MiB),
  SHA-256
  `f866dd60bc40a04f6c2497dec8021850eb7c85e93cd857c8860983ee2531bafd`.
  Run-1 artifact remains frozen (entry 2 hash).
- **Open problems for the next contributor (priority order):**
  1. **Pre-register and test the sharpened hypothesis:** "the V2∘V3
     enumerator of every distance-optimal self-dual additive GF(4) code is
     Lorentzian (ULC, no internal zeros)." It went 0/31 here but was not a
     registered criterion input; push to n = 9–12 via the Danielsen–Parker
     LC-orbit classification (290 codes at n ≤ 8, 40 at n = 12 self-dual).
     Identify the 2/203 V2∘V3 log-concavity violators and check whether
     they are distance-suboptimal (they are candidates for the boundary of
     the conjecture).
  2. **Weight by LC orbits, not graph iso-classes:** rerun the self-dual
     tables over one representative per LC-equivalence class
     (Danielsen–Parker orbits) — the bivariate results are LC-invariant, so
     this is the canonical census; the complete-enumerator results are not,
     which needs a per-orbit min/max treatment.
  3. **gf4_linear remains untested** (10 < 20 members at n ≤ 8; ω-closure
     is not LC-invariant so graph representatives cannot certify a class).
     Test GF(4)-linearity up to equivalence, or extend n.
  4. **distance_optimal composition bias:** several (n,k) blocks at
     n = 6..8 contributed zero members because seeded sampling never found
     the optimum; seed known-optimal codes explicitly (codetables.de
     generator matrices) before trusting subclass fractions near θ.
  5. **Reformulate the multivariate arm** (C4 dead on all entangled codes
     here): candidate replacements — Lorentzianity of the double/split
     enumerator of Chen–Ren, or of B−A's complete form, or on the
     M-convex-support closure rather than the raw support.

## 2026-08-11 · Entry 5 — Pre-registration of the sharpened hypothesis (extension to n ≤ 12; predates all extension compute)

- **Who:** Claude (Fable 5) orchestrator; web search for data availability
  and literature.
- **Data source located:** the Danielsen–Parker classification database
  (orig. ii.uib.no/~larsed/vncorbits, now 404) survives mirrored at
  **codetables.de/larsed/vncorbits/**: `thebigselfdualfile.txt.gz` (per-code
  records: length, distance, decomposability, Type I/II, weight
  distribution, |Aut|, LC-orbit size, graph6 representative) and
  `vncorbitsN.g6(.gz)` graph files for n = 1..12 plus `vncorbits14.g6`
  (indecomposable extremal Type II only). Exact URLs and SHA-256 of every
  downloaded file to be recorded in the run entry.
- **Literature check for the sharpened statement (kill-criterion-2
  analogue): NOT FIRED.** Searched "Type II / even self-dual additive
  GF(4) weight distribution unimodal | log-concave | extremal shadow"
  (2026-08-11): the classical literature classifies Type II enumerators
  and proves extremal ones unique per length (which makes the decisive
  check below cheap), but contains no
  unimodality/log-concavity/Lorentzianity results.

### Frozen hypothesis H1 and kill criteria (before any extension compute)

**H1:** for every even length n in the completed range, every Type II
(all-even-weight) self-dual additive GF(4) code attaining d = dmaxII(n)
(the maximum distance among Type II codes of that length, computed within
the complete classification) has a halved (V2∘V3) A-enumerator that passes
C1 + C2 + C3 of the Entry-1 conventions — i.e. is ultra-log-concave with
no internal zeros, equivalently its homogenization is bivariate
Lorentzian. (This is the exact-zero cell observed at n ≤ 8: 0/31.)

- **K1 (kills H1):** any dmaxII-attaining Type II code at any completed
  length fails C1, C2, or C3 on its halved enumerator. "Completed length"
  = both data gates below pass for that n. Applies retroactively: the two
  V2∘V3/C2-violating distinct enumerators found at n ≤ 8 (entry 4) must be
  identified; if either belongs to a dmaxII-attaining Type II code, K1
  fires already at n ≤ 8.
- **Data gates (per length, hard):** (i) per-length code counts must match
  the published Danielsen–Parker 2006 tables; (ii) A-enumerators
  recomputed from the graph6 representatives must equal the database's
  stored weight distributions (full recomputation where runtime allows,
  at minimum all Type II codes and all codes at n ≤ 10; any mismatch
  stops the run for investigation).
- **Descriptive outputs (NOT kill inputs), frozen now:** fail fractions
  for non-optimal Type II codes per length (discrimination check — if
  they also pass at ~100%, H1 is a Type II regularity rather than an
  optimality signature; either outcome is recorded, neither kills);
  Type I / odd-n codes under V2; the per-LC-orbit census at n ≤ 8
  resolving entry-3 F3 (our graph data partitioned into LC orbits by
  local-complementation closure, counts validated against
  Danielsen–Parker: 1, 2, 3, 6, 11, 26, 59, 182); exact distance-optimal
  populations at n ≤ 12 from the census (removing the entry-3 F9
  sampling bias).
- **Registered expectation, stated for honesty:** at n = 12 the extremal
  Type II code is the unique dodecacode (d = 6); H1 at n = 12 therefore
  reduces to a single sequence, and its halved enumerator is either ULC
  or the hypothesis dies at the first genuinely large length.

## 2026-08-11 · Entry 6 — Phase A of the Entry-5 extension: violator identification + LC-orbit census (n ≤ 8)

- **Who:** Claude Opus subagent (independent reimplementation of the
  Entry-1 conventions; no imports from sweep.py), directed by the
  orchestrator. Same container image, stdlib only.
- **Command:**
  `podman run --rm -v "$PWD":/work:z docker.io/library/python:3.12-slim python /work/test/orbits_n8.py`
  (Python 3.12.13, deterministic, no seed). Wall-clock 21.3 s; output
  byte-identical across two runs. Task-1 analysis read only the frozen
  run-2 artifact.
- **Task 1 — the two V2∘V3/C2 violators (K1 retro-check):** both are the
  **GHZ orbits** (star ≅ complete graph under LC):
  - n=6: A=[1,0,15,0,15,0,33], halved [15,15,33], violation 15² < 15·33;
    Type II, d=2 vs dmaxII(6)=4. Carried by graph-6-00071 (K_{1,5}) and
    graph-6-00155 (K₆).
  - n=8: A=[1,0,28,0,70,0,28,0,129], halved [28,70,28,129], violation
    28² < 70·129; Type II, d=2 vs dmaxII(8)=4. Carried by graph-8-05454
    (K_{1,7}) and graph-8-12345 (K₈).
  Both sit at the minimum possible distance — maximally suboptimal.
  **K1 does NOT fire at n ≤ 8**; GHZ is the anticipated boundary
  counterexample (entry 4, open problem 1). Independent recheck of all
  stored check flags on all 13,598 graph records: 0 mismatches.
- **Task 2 — LC-orbit census (resolves entry-3 F3):** the 13,598 iso
  classes partition into LC orbits with counts **1, 2, 3, 6, 11, 26, 59,
  182 (total 290) = Danielsen–Parker exactly** (hard gate). A-enumerator
  constant on every orbit (proves consistency of both codebases;
  bivariate data is genuinely LC-invariant). Orbit-weighted A/V2/C2 fail
  fractions: n=4: 2/6, 5: 7/11, 6: 16/26, 7: 48/59, 8: 152/182 (total
  225/290 = 0.776, rising with n) — confirms the run-2 direction under
  canonical census weighting. A/V2∘V3/C2 over Type II orbits: 2/30 =
  0.067, the two failures being exactly the GHZ orbits.
- **H1 population at n ≤ 8:** dmaxII = 2, 2, 4, 4 at n = 2, 4, 6, 8;
  attainers = **7 orbits (39 iso classes), 0 failures** on halved
  C1+C2+C3. All three distinct n=8 optimal orbits share
  A=[1,0,0,0,42,0,168,0,45] (halved [42,168,45]); n=6 optimum is the
  hexacode orbit A=[1,0,0,0,45,0,18].
- **Audit trail:** `test/orbits_n8.py` committed;
  `test/results-orbits-n8.json` (227,503 bytes) SHA-256
  `796203cb606e75f9f26cf478883230776e17ed725c5b92d6cc58d39d4aebed58`.
- **Bears on:** Entry-5 K1 — not fired at n ≤ 8. H1 remains alive going
  into the n ≤ 12 database run (entry 7).
