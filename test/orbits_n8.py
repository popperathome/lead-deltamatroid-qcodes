#!/usr/bin/env python3
"""LC-orbit census of self-dual additive GF(4) codes (graph states) at n <= 8.

Resolves entry-3 finding F3 ("13,598 graph states = all self-dual codes up to
LC" is wrong as a census: the LC-inequivalent count is 290) and produces the
canonical, orbit-weighted version of the run-2 self-dual tables, plus the exact
H1 population (dmaxII-attaining Type II orbits) at n <= 8.

Fully deterministic; stdlib only; no seed.  Everything (graph canonicalization,
local complementation, weight enumerators, the V1/V2/V3 slicings and the
C1/C2/C3 checks) is reimplemented here from the Entry-1 definitions --
`sweep.py` is deliberately NOT imported, independence is the point.

Input :  /work/test/results-run2-seed20260811.json   (graph_edges of the 13,598
         graph-code records; used only as the graph catalogue)
Output:  /work/test/results-orbits-n8.json

Hard gates (AssertionError stops the run):
  * per-n graph iso-class counts == OEIS A000088  (1,2,4,11,34,156,1044,12346)
  * per-n LC-orbit counts == Danielsen-Parker     (1,2,3,6,11,26,59,182 = 290)
  * the A-enumerator is constant on every LC orbit
  * recomputed A == the A stored in the run-2 artifact, for every iso class
"""

import hashlib
import json
import os
import sys
import time
from math import comb

ART_IN = "/work/test/results-run2-seed20260811.json"
ART_OUT = "/work/test/results-orbits-n8.json"

A000088 = {1: 1, 2: 2, 3: 4, 4: 11, 5: 34, 6: 156, 7: 1044, 8: 12346}
DANIELSEN_PARKER = {1: 1, 2: 2, 3: 3, 4: 6, 5: 11, 6: 26, 7: 59, 8: 182}


# ---------------------------------------------------------------------------
# Entry-1 conventions: variants V1/V2/V3 and checks C1/C2/C3
# ---------------------------------------------------------------------------
def V1(a):
    """raw coefficient sequence."""
    return list(a)


def V2(a):
    """support-restricted: first nonzero index j >= 1 through max support."""
    lo = None
    for j in range(1, len(a)):
        if a[j] != 0:
            lo = j
            break
    if lo is None:
        return []
    hi = max(j for j in range(len(a)) if a[j] != 0)
    return list(a[lo:hi + 1])


def v3_applicable(a):
    """V3 applies iff supp(a) \\ {0} is contained in 2Z."""
    return all(a[j] == 0 for j in range(1, len(a), 2))


def V3(a):
    """even-reindexed (halved-degree) sequence (a_0, a_2, a_4, ...)."""
    return [a[j] for j in range(0, len(a), 2)]


def C1(s):
    """no internal zeros: the support is one contiguous block."""
    nz = [i for i, x in enumerate(s) if x != 0]
    if not nz:
        return True, None
    for i in range(nz[0], nz[-1] + 1):
        if s[i] == 0:
            return False, i
    return True, None


def C2(s):
    """log-concavity  a_j^2 >= a_{j-1} a_{j+1}  (exact integers)."""
    for j in range(1, len(s) - 1):
        if s[j] * s[j] < s[j - 1] * s[j + 1]:
            return False, j
    return True, None


def C3(s):
    """ultra-log-concavity, i.e. (Branden-Huh) bivariate Lorentzianity of the
    homogenization.  Requires C1.  Integer cross-multiplication of
    (a_j/C(m,j))^2 >= (a_{j-1}/C(m,j-1)) (a_{j+1}/C(m,j+1)), m = deg."""
    ok1, _ = C1(s)
    m = len(s) - 1
    for j in range(1, len(s) - 1):
        lhs = s[j] * s[j] * comb(m, j - 1) * comb(m, j + 1)
        rhs = s[j - 1] * s[j + 1] * comb(m, j) * comb(m, j)
        if lhs < rhs:
            return False, j
    return ok1, None


def run_checks(a):
    """all six pass-flags for the A-enumerator `a` (V3 fields None if N/A)."""
    s2 = V2(a)
    out = {
        "V2_C1": C1(s2)[0], "V2_C2": C2(s2)[0], "V2_C3": C3(s2)[0],
        "V2oV3_C1": None, "V2oV3_C2": None, "V2oV3_C3": None,
    }
    if v3_applicable(a):
        s23 = V2(V3(a))
        out["V2oV3_C1"] = C1(s23)[0]
        out["V2oV3_C2"] = C2(s23)[0]
        out["V2oV3_C3"] = C3(s23)[0]
    return out


# ---------------------------------------------------------------------------
# graphs: adjacency as a tuple of n row-bitmasks
# ---------------------------------------------------------------------------
def adj_from_edges(n, edges):
    a = [0] * n
    for u, v in edges:
        assert u != v and 0 <= u < n and 0 <= v < n
        a[u] |= 1 << v
        a[v] |= 1 << u
    return tuple(a)


def edges_from_adj(adj):
    n = len(adj)
    return [[u, v] for u in range(n) for v in range(u + 1, n)
            if (adj[u] >> v) & 1]


def local_complement(adj, v):
    """complement the induced subgraph on N(v)."""
    a = list(adj)
    nv = a[v]
    u = nv
    while u:
        b = u & (-u)
        i = b.bit_length() - 1
        u ^= b
        a[i] ^= (nv ^ b)          # toggle edges from i to N(v) \\ {i}
    return tuple(a)


def _refine(nbrs, colors, n):
    """1-WL colour refinement to a stable ordered partition (colours are ranks
    of the isomorphism-invariant signatures, so the result is invariant)."""
    cur = list(colors)
    ncls = len(set(cur))
    while True:
        sigs = [(cur[v], tuple(sorted(cur[w] for w in nbrs[v])))
                for v in range(n)]
        rank = {s: i for i, s in enumerate(sorted(set(sigs)))}
        new = [rank[s] for s in sigs]
        k = len(rank)
        if k == ncls:
            return new
        cur, ncls = new, k


_canon_memo = {}


def canon(adj):
    """Canonical form of a graph: the lexicographically minimal packed
    upper-triangle bitstring over all vertex orderings compatible with the
    invariant refinement/individualization tree.  Returns (code, canon_adj)."""
    memo = _canon_memo.get(adj)
    if memo is not None:
        return memo
    n = len(adj)
    total_bits = n * (n - 1) // 2
    nbrs = [[w for w in range(n) if (adj[v] >> w) & 1] for v in range(n)]
    best = [None, None]          # [code, order]

    def rec(colors, placed, placed_mask, cur, bits):
        if len(placed) == n:
            if best[0] is None or cur < best[0]:
                best[0] = cur
                best[1] = tuple(placed)
            return
        unplaced = [v for v in range(n) if not (placed_mask >> v) & 1]
        mincol = min(colors[v] for v in unplaced)
        cands = [v for v in unplaced if colors[v] == mincol]
        k = len(placed)
        for v in cands:
            row = 0
            for u in placed:
                row = (row << 1) | ((adj[v] >> u) & 1)
            ncur = (cur << k) | row
            nbits = bits + k
            if best[0] is not None and (best[0] >> (total_bits - nbits)) < ncur:
                continue                      # strictly worse prefix: prune
            if len(cands) > 1:
                nc = list(colors)
                nc[v] = -1                    # individualize
                nc = _refine(nbrs, nc, n)
            else:
                nc = colors
            placed.append(v)
            rec(nc, placed, placed_mask | (1 << v), ncur, nbits)
            placed.pop()

    rec(_refine(nbrs, [0] * n, n), [], 0, 0, 0)
    order = best[1]
    pos = {v: i for i, v in enumerate(order)}
    cadj = [0] * n
    for u in range(n):
        for w in range(n):
            if (adj[u] >> w) & 1:
                cadj[pos[u]] |= 1 << pos[w]
    res = (best[0], tuple(cadj))
    _canon_memo[adj] = res
    return res


def enumerator(adj):
    """A-enumerator of the graph state |G>: the stabilizer group is spanned by
    g_v = X_v prod_{w~v} Z_w, so the element indexed by S subset V acts on
    qubit j as X^[j in S] Z^[|N(j) cap S| odd]; count Hamming weights."""
    n = len(adj)
    A = [0] * (n + 1)
    for S in range(1 << n):
        z = 0
        for j in range(n):
            if (adj[j] & S).bit_count() & 1:
                z |= 1 << j
        A[(S | z).bit_count()] += 1
    assert sum(A) == 1 << n
    return A


def distance(a):
    for j in range(1, len(a)):
        if a[j] != 0:
            return j
    return None                       # S = {I}: only n = 0; not reachable here


# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    with open(ART_IN) as f:
        art = json.load(f)
    records = [c for c in art["codes"] if c["class"] == "selfdual_graph"]
    print(f"[in]  graph-code records in run-2 artifact: {len(records)}")
    assert len(records) == 13598, len(records)

    # ---- 1. graphs up to isomorphism, per n --------------------------------
    graphs = {}          # n -> {code: canon_adj}
    stored_A = {}        # (n, code) -> A from the artifact
    for c in records:
        n = c["n"]
        adj = adj_from_edges(n, c["graph_edges"])
        code, cadj = canon(adj)
        graphs.setdefault(n, {})[code] = cadj
        prev = stored_A.get((n, code))
        assert prev is None or prev == c["A"], (n, code, prev, c["A"])
        stored_A[(n, code)] = c["A"]
    counts = {n: len(g) for n, g in sorted(graphs.items())}
    print(f"[gate] iso-class counts per n: {counts}")
    assert counts == A000088, (counts, A000088)
    assert sum(counts.values()) == 13598
    print("[gate] OEIS A000088 through n=8: PASS "
          "(artifact records are pairwise non-isomorphic and exhaustive)")

    # ---- 2. LC orbits ------------------------------------------------------
    orbits = {}          # n -> list of sorted member-code lists
    for n in sorted(graphs):
        pool = graphs[n]
        seen = set()
        for code in sorted(pool):
            if code in seen:
                continue
            members = []
            frontier = [code]
            seen.add(code)
            while frontier:
                cur = frontier.pop()
                members.append(cur)
                cadj = pool[cur]
                for v in range(n):
                    img = local_complement(cadj, v)
                    icode, iadj = canon(img)
                    assert icode in pool, (n, icode)   # closure inside the pool
                    if icode not in seen:
                        seen.add(icode)
                        frontier.append(icode)
            orbits.setdefault(n, []).append(sorted(members))
        assert len(seen) == len(pool)
    orbit_counts = {n: len(o) for n, o in sorted(orbits.items())}
    print(f"[gate] LC-orbit counts per n: {orbit_counts} "
          f"(total {sum(orbit_counts.values())})")
    assert orbit_counts == DANIELSEN_PARKER, (orbit_counts, DANIELSEN_PARKER)
    print("[gate] Danielsen-Parker 1,2,3,6,11,26,59,182 (total 290): PASS")

    # ---- 3. enumerators; constancy on orbits; agreement with the artifact ---
    orbit_records = []
    for n in sorted(orbits):
        for idx, members in enumerate(sorted(orbits[n])):
            As = []
            for code in members:
                A = enumerator(graphs[n][code])
                assert A == stored_A[(n, code)], \
                    f"A mismatch vs artifact at n={n} code={code}: " \
                    f"{A} vs {stored_A[(n, code)]}"
                As.append(A)
            first = As[0]
            for A in As[1:]:
                assert A == first, \
                    f"FATAL: A-enumerator not constant on LC orbit n={n} #{idx}"
            rep = members[0]
            a = first
            orbit_records.append({
                "n": n,
                "orbit_index": idx,
                "size": len(members),
                "representative_graph_edges": edges_from_adj(graphs[n][rep]),
                "representative_canon_code": rep,
                "member_canon_codes": members,
                "A": a,
                "d": distance(a),
                "type_II": v3_applicable(a),
                "V2": V2(a),
                "V2oV3": V2(V3(a)) if v3_applicable(a) else None,
                "passes": run_checks(a),
            })
    print(f"[gate] A-enumerator constant on all {len(orbit_records)} orbits: PASS")
    print(f"[gate] recomputed A == artifact A on all 13,598 iso classes: PASS")

    # ---- 4. summary tables -------------------------------------------------
    def frac(f, t):
        return (f / t) if t else None

    per_n_counts = {}
    v2c2 = {}
    v2v3c2 = {}
    v2c2_II = {}
    for r in orbit_records:
        n = r["n"]
        per_n_counts[n] = per_n_counts.get(n, 0) + 1
        nontrivial = len(r["V2"]) >= 3       # shorter slices pass vacuously
        d2 = v2c2.setdefault(n, {"orbits": 0, "fail": 0,
                                 "nontrivial": 0, "nontrivial_fail": 0})
        d2["orbits"] += 1
        d2["fail"] += 0 if r["passes"]["V2_C2"] else 1
        if nontrivial:
            d2["nontrivial"] += 1
            d2["nontrivial_fail"] += 0 if r["passes"]["V2_C2"] else 1
        if r["type_II"]:
            d3 = v2v3c2.setdefault(n, {"applicable_orbits": 0, "fail": 0})
            d3["applicable_orbits"] += 1
            d3["fail"] += 0 if r["passes"]["V2oV3_C2"] else 1
            d2b = v2c2_II.setdefault(n, {"typeII_orbits": 0, "fail": 0})
            d2b["typeII_orbits"] += 1
            d2b["fail"] += 0 if r["passes"]["V2_C2"] else 1
    for n, d in v2c2.items():
        d["frac"] = frac(d["fail"], d["orbits"])
        d["nontrivial_frac"] = frac(d["nontrivial_fail"], d["nontrivial"])
    for n, d in v2v3c2.items():
        d["frac"] = frac(d["fail"], d["applicable_orbits"])
    for n, d in v2c2_II.items():
        d["frac"] = frac(d["fail"], d["typeII_orbits"])

    # dmaxII and the H1 population
    dmaxII = {}
    for r in orbit_records:
        if r["type_II"]:
            n = r["n"]
            if r["d"] > dmaxII.get(n, -1):
                dmaxII[n] = r["d"]
    h1 = []
    for r in orbit_records:
        if r["type_II"] and r["d"] == dmaxII.get(r["n"]):
            p = r["passes"]
            h1.append({
                "n": r["n"], "orbit_index": r["orbit_index"],
                "size": r["size"], "d": r["d"], "dmaxII": dmaxII[r["n"]],
                "A": r["A"], "V2oV3": r["V2oV3"],
                "V2oV3_C1": p["V2oV3_C1"], "V2oV3_C2": p["V2oV3_C2"],
                "V2oV3_C3": p["V2oV3_C3"],
                "H1_pass": bool(p["V2oV3_C1"] and p["V2oV3_C2"]
                                and p["V2oV3_C3"]),
                "representative_graph_edges": r["representative_graph_edges"],
            })
    h1_fail = [h for h in h1 if not h["H1_pass"]]

    v2v3_violators = [
        {"n": r["n"], "orbit_index": r["orbit_index"], "size": r["size"],
         "A": r["A"], "V2oV3": r["V2oV3"], "d": r["d"],
         "dmaxII": dmaxII.get(r["n"]),
         "attains_dmaxII": r["d"] == dmaxII.get(r["n"]),
         "representative_graph_edges": r["representative_graph_edges"]}
        for r in orbit_records
        if r["type_II"] and r["passes"]["V2oV3_C2"] is False
    ]

    summary = {
        "orbit_counts_per_n": per_n_counts,
        "danielsen_parker_reference": DANIELSEN_PARKER,
        "iso_class_counts_per_n": counts,
        "orbit_weighted_A_V2_C2": v2c2,
        "orbit_weighted_A_V2oV3_C2": v2v3c2,
        "orbit_weighted_A_V2_C2_typeII_only": v2c2_II,
        "dmaxII_per_n": dmaxII,
        "H1_population_dmaxII_typeII_orbits": h1,
        "H1_failures": h1_fail,
        "A_V2oV3_C2_violating_orbits": v2v3_violators,
        "totals": {
            "orbits": len(orbit_records),
            "iso_classes": sum(counts.values()),
            "A_V2_C2_fail_orbits": sum(d["fail"] for d in v2c2.values()),
            "A_V2oV3_C2_applicable_orbits":
                sum(d["applicable_orbits"] for d in v2v3c2.values()),
            "A_V2oV3_C2_fail_orbits": sum(d["fail"] for d in v2v3c2.values()),
            "type_II_orbits": sum(1 for r in orbit_records if r["type_II"]),
        },
    }

    out = {
        "meta": {
            "script": os.path.basename(__file__),
            "python": sys.version.split()[0],
            "input_artifact": ART_IN,
            "deterministic": True,
            "seed": None,
            "note": ("no timing field is written; with the pinned image the "
                     "artifact is byte-reproducible across runs"),
        },
        "orbits": orbit_records,
        "summary": summary,
    }

    # ---- 5. print the tables ----------------------------------------------
    print("\n=== LC-orbit counts (gate: Danielsen-Parker) ===")
    print(f"{'n':>2} {'iso-classes':>12} {'LC orbits':>10} {'D-P':>5}")
    for n in sorted(per_n_counts):
        print(f"{n:>2} {counts[n]:>12} {per_n_counts[n]:>10} "
              f"{DANIELSEN_PARKER[n]:>5}")
    print(f"{'tot':>2} {sum(counts.values()):>12} "
          f"{sum(per_n_counts.values()):>10} "
          f"{sum(DANIELSEN_PARKER.values()):>5}")

    print("\n=== orbit-weighted fail fractions, A / V2 / C2 ===")
    print(f"{'n':>2} {'orbits':>7} {'fail':>5} {'frac':>7} | "
          f"{'nontriv':>7} {'fail':>5} {'frac':>7}")
    for n in sorted(v2c2):
        d = v2c2[n]
        f1 = "-" if d["frac"] is None else f"{d['frac']:.3f}"
        f2 = "-" if d["nontrivial_frac"] is None else f"{d['nontrivial_frac']:.3f}"
        print(f"{n:>2} {d['orbits']:>7} {d['fail']:>5} {f1:>7} | "
              f"{d['nontrivial']:>7} {d['nontrivial_fail']:>5} {f2:>7}")
    tot_o = sum(d["orbits"] for d in v2c2.values())
    tot_f = sum(d["fail"] for d in v2c2.values())
    tot_nt = sum(d["nontrivial"] for d in v2c2.values())
    tot_ntf = sum(d["nontrivial_fail"] for d in v2c2.values())
    print(f"{'tot':>2} {tot_o:>7} {tot_f:>5} {tot_f/tot_o:>7.3f} | "
          f"{tot_nt:>7} {tot_ntf:>5} {tot_ntf/tot_nt:>7.3f}")

    print("\n=== orbit-weighted fail fractions, A / V2oV3 / C2 "
          "(Type II orbits = V3-applicable) ===")
    print(f"{'n':>2} {'typeII':>7} {'fail':>5} {'frac':>7}")
    for n in sorted(v2v3c2):
        d = v2v3c2[n]
        print(f"{n:>2} {d['applicable_orbits']:>7} {d['fail']:>5} "
              f"{d['frac']:>7.3f}")
    to = sum(d["applicable_orbits"] for d in v2v3c2.values())
    tf = sum(d["fail"] for d in v2v3c2.values())
    print(f"{'tot':>2} {to:>7} {tf:>5} {tf/to:>7.3f}")

    print("\n=== A / V2 / C2 restricted to Type II orbits ===")
    print(f"{'n':>2} {'typeII':>7} {'fail':>5} {'frac':>7}")
    for n in sorted(v2c2_II):
        d = v2c2_II[n]
        print(f"{n:>2} {d['typeII_orbits']:>7} {d['fail']:>5} {d['frac']:>7.3f}")

    print("\n=== A/V2oV3/C2 violating orbits ===")
    for v in v2v3_violators:
        print(f"  n={v['n']} orbit#{v['orbit_index']} size={v['size']} "
              f"d={v['d']} dmaxII={v['dmaxII']} attains={v['attains_dmaxII']}")
        print(f"      A={v['A']} V2oV3={v['V2oV3']} rep_edges="
              f"{v['representative_graph_edges']}")

    print("\n=== H1 population at n <= 8: dmaxII-attaining Type II orbits ===")
    print(f"{'n':>2} {'orbit':>6} {'size':>5} {'d':>2} "
          f"{'C1':>5} {'C2':>5} {'C3':>5}  A")
    for h in h1:
        print(f"{h['n']:>2} {h['orbit_index']:>6} {h['size']:>5} {h['d']:>2} "
              f"{str(h['V2oV3_C1']):>5} {str(h['V2oV3_C2']):>5} "
              f"{str(h['V2oV3_C3']):>5}  {h['A']}")
    print(f"H1 population: {len(h1)} orbits "
          f"({sum(h['size'] for h in h1)} iso-classes); "
          f"failures: {len(h1_fail)}")

    dt = time.time() - t0
    with open(ART_OUT, "w") as f:
        json.dump(out, f, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(open(ART_OUT, "rb").read()).hexdigest()
    print(f"\n[out] {ART_OUT}  bytes={os.path.getsize(ART_OUT)}  sha256={h}")
    print(f"[done] wall {dt:.1f} s")


if __name__ == "__main__":
    main()
