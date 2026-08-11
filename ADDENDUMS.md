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
