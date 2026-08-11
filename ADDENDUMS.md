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
- **Flagged for adversarial review (entry 3):** (i) independent verification
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
