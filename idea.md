# Weight enumerators of a natural class of quantum codes are Lorentzian

**Status:** ⏳ QUEUED

## Claim

For a natural subclass of stabilizer / CSS / self-dual quantum codes, the
homogenized complete or split weight enumerator is a Lorentzian polynomial,
imposing Hodge-type log-concavity a_k² ≥ a_{k−1}a_{k+1} (and prospectively
multivariate negative-dependence inequalities) on error distributions — new
constraints beyond the linear-programming bounds. Background: stabilizer codes
correspond to representable symplectic matroids (Sarvepalli, arXiv:1104.1171);
delta-matroid invariants have begun exhibiting Lorentzianity/log-concavity
(Larson, arXiv:2305.01008); enumerators of self-dual quantum codes are
classified in small cases (Chen–Ren, arXiv:2409.03576). Expectation stated up
front: arbitrary codes will likely give counterexamples — the lead's real
claim is that Lorentzianity characterizes a combinatorially meaningful
subclass.

## Decisive test

Exhaustive small-code sweep (the fastest falsifiable project in this batch;
numpy in a container; hours):

1. Enumerate stabilizer codes for small n (n ≤ 8, all inequivalent codes from
   known classifications/databases; at minimum all self-dual ones).
2. Cheap necessary condition first: univariate log-concavity (with no internal
   zeros) of the weight-enumerator coefficients.
3. For survivors, test Lorentzianity of the homogenized bivariate/split
   enumerator: hyperbolicity/Hessian-signature checks at sampled points of the
   positive orthant.
4. Cross-tabulate pass/fail against structure: self-dual, CSS, distance-optimal,
   graph-state, GF(4)-linear.

## Kill criteria

- Log-concavity fails for a substantial fraction of codes in *every* candidate
  subclass at small n — pass/fail correlates with no natural property. (The
  interesting outcome "fails generically but holds exactly on subclass X" is
  survival, not death; death is pass/fail being structureless noise.)
- Literature collision: quantum weight-enumerator log-concavity already
  established or refuted (search "Lorentzian weight enumerator", "log-concave
  quantum code", "matroid quantum enumerator").

## Log

See ADDENDUMS.md (no compute spent yet).
