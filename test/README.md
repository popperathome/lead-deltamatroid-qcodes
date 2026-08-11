# Stabilizer enumerator decisive test

`sweep.py` builds the frozen small-code catalog, validates its exact Pauli,
MacWilliams, graph-state, distance, and Brändén–Huh machinery, then tests the
A, B, B−A, and complete A enumerators for internal zeros, log-concavity,
ultra-log-concavity, and Lorentzianity. Results are reported both raw and after
the registered enumerator fingerprint deduplication.

Run the smoke test in the pinned Python 3.12 container. The script is standard
library only, so no package installation is needed:

```sh
podman run --rm -v "$PWD":/work:z docker.io/library/python:3.12-slim python /work/test/sweep.py --seed 20260811 --max-n 5
```

For the full `n <= 8` sweep, omit `--max-n`:

```sh
podman run --rm -v "$PWD":/work:z docker.io/library/python:3.12-slim python /work/test/sweep.py --seed 20260811
```

Use `--out PATH` to override the default artifact path.

Artifacts:

- `results-seed<seed>.json`: reproducible metadata and conventions, validation
  results, raw code records, complete-enumerator data for deduplicated
  representatives, raw/deduplicated cross-tabs, and the frozen kill-criterion
  mapping.
- Standard output: phase timings, progress, validation results, the primary
  summary table, and the verdict.
