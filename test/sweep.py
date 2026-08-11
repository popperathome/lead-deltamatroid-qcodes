#!/usr/bin/env python3
"""Exact small-stabilizer-code falsification sweep (Python stdlib only).

Pauli phases are discarded: every statistic used here depends only on the
symplectic vector (x, z), not on a representative's phase.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import platform
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Iterable, Iterator


GRAPH_COUNTS = {1: 1, 2: 2, 3: 4, 4: 11, 5: 34, 6: 156, 7: 1044, 8: 12346}
SELFDUAL_MAX_DISTANCE = {1: 1, 2: 2, 3: 2, 4: 2, 5: 3, 6: 4, 7: 3, 8: 4}

# From memory -- independently verified in adversarial review.  Entries are
# best-known binary stabilizer distances d for [[n,k]], n <= 8.  The k=0
# column is replaced by the Danielsen--Parker maxima above.
BEST_KNOWN_DISTANCE = {
    1: {1: 1},
    2: {1: 1, 2: 1},
    3: {1: 1, 2: 1, 3: 1},
    4: {1: 2, 2: 2, 3: 1, 4: 1},
    5: {1: 3, 2: 2, 3: 1, 4: 1, 5: 1},
    6: {1: 3, 2: 2, 3: 2, 4: 2, 5: 1, 6: 1},
    7: {1: 3, 2: 3, 3: 2, 4: 2, 5: 1, 6: 1, 7: 1},
    8: {1: 3, 2: 3, 3: 3, 4: 2, 5: 2, 6: 2, 7: 1, 8: 1},
}

SINGLE_SUBCLASSES = (
    "selfdual_graph", "even_selfdual", "gf4_linear", "css_decomposable",
    "css_constructed", "distance_optimal", "named", "random_control",
)
CANDIDATE_SUBCLASSES = SINGLE_SUBCLASSES[:-1]


@dataclass
class CodeSpec:
    id: str
    code_class: str
    n: int
    generators: tuple[tuple[int, int], ...]
    graph_edges: list[list[int]] | None = None
    derived_seed: int | None = None
    graph_state: bool = False
    css_as_given: bool = False
    named: bool = False
    random_control: bool = False


def parity(value: int) -> int:
    return value.bit_count() & 1


def commute(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return parity((a[0] & b[1]) ^ (b[0] & a[1])) == 0


def packed(pauli: tuple[int, int], n: int) -> int:
    return pauli[0] | (pauli[1] << n)


def unpack(value: int, n: int) -> tuple[int, int]:
    mask = (1 << n) - 1
    return value & mask, value >> n


def rref(rows: Iterable[int], width: int) -> tuple[int, ...]:
    work = [row for row in rows if row]
    pivot_row = 0
    for column in range(width):
        found = next((i for i in range(pivot_row, len(work)) if (work[i] >> column) & 1), None)
        if found is None:
            continue
        work[pivot_row], work[found] = work[found], work[pivot_row]
        for i in range(len(work)):
            if i != pivot_row and ((work[i] >> column) & 1):
                work[i] ^= work[pivot_row]
        pivot_row += 1
        if pivot_row == len(work):
            break
    return tuple(work[:pivot_row])


def rank(rows: Iterable[int], width: int) -> int:
    return len(rref(rows, width))


def in_span(value: int, basis: Iterable[int], width: int) -> bool:
    base = tuple(basis)
    return rank((*base, value), width) == rank(base, width)


def span(basis: Iterable[int]) -> list[int]:
    values = [0]
    for vector in basis:
        values += [item ^ vector for item in values]
    return values


def nullspace(equations: Iterable[int], width: int) -> tuple[int, ...]:
    rows = rref(equations, width)
    pivot_for_row = [((row & -row).bit_length() - 1) for row in rows]
    pivots = set(pivot_for_row)
    result = []
    for free in range(width):
        if free in pivots:
            continue
        vector = 1 << free
        for pivot, row in zip(pivot_for_row, rows, strict=True):
            if parity(row & vector):
                vector |= 1 << pivot
        result.append(vector)
    return tuple(result)


def validate_generators(n: int, generators: tuple[tuple[int, int], ...]) -> int:
    assert all(0 <= x < 1 << n and 0 <= z < 1 << n for x, z in generators)
    assert all(commute(a, b) for a, b in itertools.combinations(generators, 2))
    assert rank((packed(g, n) for g in generators), 2 * n) == len(generators)
    k = n - len(generators)
    assert 0 <= k <= n
    return k


def centralizer_basis(n: int, generators: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    equations = tuple(z | (x << n) for x, z in generators)
    basis = nullspace(equations, 2 * n)
    k = n - len(generators)
    assert len(basis) == n + k
    return basis


def pauli_weight(value: int, n: int) -> int:
    x, z = unpack(value, n)
    return (x | z).bit_count()


def enumerate_stabilizer(
    n: int, generators: tuple[tuple[int, int], ...]
) -> tuple[list[int], list[int], dict[tuple[int, int, int, int], int]]:
    elements = span(packed(g, n) for g in generators)
    counts = [0] * (n + 1)
    complete: Counter[tuple[int, int, int, int]] = Counter()
    mask = (1 << n) - 1
    for value in elements:
        x, z = value & mask, value >> n
        counts[(x | z).bit_count()] += 1
        n_x = (x & ~z & mask).bit_count()
        n_z = (z & ~x & mask).bit_count()
        n_y = (x & z).bit_count()
        n_i = n - n_x - n_y - n_z
        complete[(n_i, n_x, n_y, n_z)] += 1
    assert sum(counts) == 1 << len(generators)
    return elements, counts, dict(complete)


def macwilliams(a: list[int], stabilizer_dim: int) -> list[int]:
    n = len(a) - 1
    denominator = 1 << stabilizer_dim
    numerators = [0] * (n + 1)
    for j, coefficient in enumerate(a):
        if not coefficient:
            continue
        for p in range(n - j + 1):
            left = math.comb(n - j, p) * (3 ** p)
            for q in range(j + 1):
                numerators[p + q] += coefficient * left * math.comb(j, q) * ((-1) ** q)
    assert all(value % denominator == 0 for value in numerators)
    b = [value // denominator for value in numerators]
    k = n - stabilizer_dim
    assert all(value >= 0 for value in b)
    assert sum(b) == 1 << (n + k)
    return b


def direct_centralizer_counts(n: int, generators: tuple[tuple[int, int], ...]) -> list[int]:
    counts = [0] * (n + 1)
    for value in span(centralizer_basis(n, generators)):
        counts[pauli_weight(value, n)] += 1
    return counts


def code_distance(n: int, k: int, generators: tuple[tuple[int, int], ...]) -> int:
    stabilizer = set(span(packed(g, n) for g in generators))
    if k == 0:
        weights = [pauli_weight(value, n) for value in stabilizer if value]
    else:
        weights = [pauli_weight(value, n) for value in span(centralizer_basis(n, generators))
                   if value not in stabilizer]
    assert weights
    return min(weights)


def sequence_check(sequence: list[int]) -> dict[str, dict[str, object]]:
    support = [i for i, value in enumerate(sequence) if value]
    gap = None
    if support:
        gap = next((i for i in range(support[0], support[-1] + 1) if sequence[i] == 0), None)
    c1 = {"pass": gap is None, "first_gap": gap}
    c2_violation = next((j for j in range(1, len(sequence) - 1)
                         if sequence[j] ** 2 < sequence[j - 1] * sequence[j + 1]), None)
    c2 = {"pass": c2_violation is None, "first_violating_index": c2_violation}
    m = len(sequence) - 1
    c3_violation = None
    if gap is None:
        for j in range(1, len(sequence) - 1):
            left = sequence[j] ** 2 * math.comb(m, j - 1) * math.comb(m, j + 1)
            right = sequence[j - 1] * sequence[j + 1] * math.comb(m, j) ** 2
            if left < right:
                c3_violation = j
                break
    c3 = {"pass": gap is None and c3_violation is None,
          "first_violating_index": c3_violation,
          "c1_required": True}
    return {"c1": c1, "c2": c2, "c3": c3}


def variants(sequence: list[int]) -> dict[str, list[int]]:
    nonzero_after_identity = [i for i in range(1, len(sequence)) if sequence[i]]
    v2 = (sequence[nonzero_after_identity[0]:nonzero_after_identity[-1] + 1]
          if nonzero_after_identity else [])
    output = {"V1": list(sequence), "V2": v2}
    if all(i % 2 == 0 for i in nonzero_after_identity):
        v3 = list(sequence[::2])
        nonzero_v3 = [i for i in range(1, len(v3)) if v3[i]]
        output["V3"] = v3
        output["V2oV3"] = (v3[nonzero_v3[0]:nonzero_v3[-1] + 1] if nonzero_v3 else [])
    return output


def all_sequence_checks(sequence: list[int]) -> dict[str, dict[str, object]]:
    return {name: sequence_check(value) for name, value in variants(sequence).items()}


def compositions(total: int, parts: int) -> Iterator[tuple[int, ...]]:
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first, *rest)


def m_convex_check(polynomial: dict[tuple[int, int, int, int], int]) -> dict[str, object]:
    support = set(polynomial)
    for alpha in sorted(support):
        for beta in sorted(support):
            for i in range(4):
                if alpha[i] <= beta[i]:
                    continue
                found = False
                for j in range(4):
                    if alpha[j] >= beta[j]:
                        continue
                    exchanged = list(alpha)
                    exchanged[i] -= 1
                    exchanged[j] += 1
                    if tuple(exchanged) in support:
                        found = True
                        break
                if not found:
                    return {"pass": False, "support_size": len(support),
                            "first_violation": {"alpha": list(alpha), "beta": list(beta), "i": i}}
    return {"pass": True, "support_size": len(support), "first_violation": None}


def poly_add(a: list[int], b: list[int]) -> list[int]:
    result = [0] * max(len(a), len(b))
    for i, value in enumerate(a):
        result[i] += value
    for i, value in enumerate(b):
        result[i] += value
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    return result


def poly_mul(a: list[int], b: list[int]) -> list[int]:
    result = [0] * (len(a) + len(b) - 1)
    for i, left in enumerate(a):
        for j, right in enumerate(b):
            result[i + j] += left * right
    return result


def permutation_sign(permutation: tuple[int, ...]) -> int:
    inversions = sum(permutation[i] > permutation[j]
                     for i in range(len(permutation)) for j in range(i + 1, len(permutation)))
    return -1 if inversions & 1 else 1


def characteristic_polynomial(matrix: list[list[int]]) -> list[int]:
    # Ascending coefficients of det(lambda I - H), by the direct 4x4 Leibniz expansion.
    result = [0]
    for permutation in itertools.permutations(range(4)):
        term = [permutation_sign(permutation)]
        for row, column in enumerate(permutation):
            term = poly_mul(term, [-matrix[row][column], 1] if row == column
                            else [-matrix[row][column]])
        result = poly_add(result, term)
    result += [0] * (5 - len(result))
    assert len(result) == 5 and result[-1] == 1
    return result


def coefficient_signs_descending(coefficients: list[int]) -> list[str]:
    return ["+" if value > 0 else "-" if value < 0 else "0"
            for value in reversed(coefficients)]


def positive_eigenvalue_count(matrix: list[list[int]]) -> tuple[int, list[int], list[str]]:
    coefficients = characteristic_polynomial(matrix)
    nonzero_signs = [1 if value > 0 else -1 for value in reversed(coefficients) if value]
    changes = sum(a != b for a, b in zip(nonzero_signs, nonzero_signs[1:]))
    return changes, coefficients, coefficient_signs_descending(coefficients)


def derivative_hessian(
    polynomial: dict[tuple[int, int, int, int], int], gamma: tuple[int, int, int, int]
) -> list[list[int]]:
    matrix = [[0] * 4 for _ in range(4)]
    for exponent, original_coefficient in polynomial.items():
        if any(exponent[i] < gamma[i] for i in range(4)):
            continue
        remaining = tuple(exponent[i] - gamma[i] for i in range(4))
        if sum(remaining) != 2:
            continue
        coefficient = original_coefficient
        for value, order in zip(exponent, gamma, strict=True):
            coefficient *= math.prod(range(value - order + 1, value + 1))
        occupied = [i for i, value in enumerate(remaining) if value]
        if len(occupied) == 1 and remaining[occupied[0]] == 2:
            matrix[occupied[0]][occupied[0]] += 2 * coefficient
        elif len(occupied) == 2 and all(remaining[i] == 1 for i in occupied):
            u, v = occupied
            matrix[u][v] += coefficient
            matrix[v][u] += coefficient
        else:
            raise AssertionError((exponent, gamma, remaining))
    return matrix


def hessian_check(
    polynomial: dict[tuple[int, int, int, int], int], degree: int
) -> dict[str, object]:
    if degree < 2:
        return {"pass": True, "partials_tested": 0, "first_violation": None}
    tested = 0
    for gamma in compositions(degree - 2, 4):
        matrix = derivative_hessian(polynomial, gamma)
        positives, coefficients, signs = positive_eigenvalue_count(matrix)
        tested += 1
        if positives > 1:
            return {"pass": False, "partials_tested": tested,
                    "first_violation": {"gamma": list(gamma), "positive_eigenvalues": positives,
                                        "char_poly_coefficients_ascending": coefficients,
                                        "char_poly_signs_descending": signs}}
    return {"pass": True, "partials_tested": tested, "first_violation": None}


def c4_check(polynomial: dict[tuple[int, int, int, int], int]) -> dict[str, object]:
    degrees = {sum(exponent) for exponent in polynomial}
    if not polynomial:
        return {"pass": True, "degree": None, "m_convex": {"pass": True, "support_size": 0,
                                                               "first_violation": None},
                "hessian": {"pass": True, "partials_tested": 0, "first_violation": None}}
    assert len(degrees) == 1
    degree = next(iter(degrees))
    m_convex = m_convex_check(polynomial)
    if not m_convex["pass"]:
        return {"pass": False, "degree": degree, "m_convex": m_convex, "hessian": None}
    hessian = hessian_check(polynomial, degree)
    return {"pass": hessian["pass"], "degree": degree, "m_convex": m_convex,
            "hessian": hessian}


def complete_checks(complete: dict[tuple[int, int, int, int], int], n: int) -> dict[str, object]:
    v1 = dict(complete)
    v2 = dict(complete)
    assert v2.pop((n, 0, 0, 0), None) == 1
    return {"V1": c4_check(v1), "V2": c4_check(v2)}


def polynomial_product(linear_forms: list[dict[tuple[int, int, int, int], int]]) -> dict[tuple[int, int, int, int], int]:
    result = {(0, 0, 0, 0): 1}
    for factor in linear_forms:
        product: Counter[tuple[int, int, int, int]] = Counter()
        for left, a in result.items():
            for right, b in factor.items():
                product[tuple(left[i] + right[i] for i in range(4))] += a * b
        result = dict(product)
    return result


def adj_from_mask(n: int, mask: int) -> tuple[int, ...]:
    adjacency = [0] * n
    bit = 0
    for i in range(n):
        for j in range(i + 1, n):
            if (mask >> bit) & 1:
                adjacency[i] |= 1 << j
                adjacency[j] |= 1 << i
            bit += 1
    return tuple(adjacency)


def mask_from_adj(adjacency: tuple[int, ...]) -> int:
    mask = 0
    bit = 0
    for i in range(len(adjacency)):
        for j in range(i + 1, len(adjacency)):
            mask |= ((adjacency[i] >> j) & 1) << bit
            bit += 1
    return mask


def refine_partition(adjacency: tuple[int, ...], partition: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    while True:
        refined: list[tuple[int, ...]] = []
        changed = False
        cell_masks = [sum(1 << v for v in cell) for cell in partition]
        for cell in partition:
            buckets: dict[tuple[int, ...], list[int]] = {}
            for vertex in cell:
                signature = tuple((adjacency[vertex] & cell_mask).bit_count() for cell_mask in cell_masks)
                buckets.setdefault(signature, []).append(vertex)
            if len(buckets) > 1:
                changed = True
            refined.extend(tuple(sorted(buckets[key])) for key in sorted(buckets))
        result = tuple(refined)
        if not changed:
            return result
        partition = result


def adjacency_word(adjacency: tuple[int, ...], order: tuple[int, ...]) -> tuple[int, ...]:
    return tuple((adjacency[order[i]] >> order[j]) & 1
                 for i in range(len(order)) for j in range(i + 1, len(order)))


@cache
def canonical_graph(n: int, mask: int) -> int:
    adjacency = adj_from_mask(n, mask)
    degree_buckets: dict[int, list[int]] = {}
    for vertex, neighbors in enumerate(adjacency):
        degree_buckets.setdefault(neighbors.bit_count(), []).append(vertex)
    initial = tuple(tuple(degree_buckets[degree]) for degree in sorted(degree_buckets))
    best: tuple[int, ...] | None = None

    def search(partition: tuple[tuple[int, ...], ...]) -> None:
        nonlocal best
        partition = refine_partition(adjacency, partition)
        split_index = next((i for i, cell in enumerate(partition) if len(cell) > 1), None)
        if split_index is None:
            word = adjacency_word(adjacency, tuple(cell[0] for cell in partition))
            if best is None or word < best:
                best = word
            return
        cell = partition[split_index]
        for vertex in cell:
            rest = tuple(item for item in cell if item != vertex)
            search(partition[:split_index] + ((vertex,), rest) + partition[split_index + 1:])

    search(initial)
    assert best is not None
    canonical_mask = sum(bit << i for i, bit in enumerate(best))
    return canonical_mask


def graph_classes(max_n: int) -> dict[int, list[int]]:
    classes = {1: [0]}
    print("  graphs n=1: 1 class")
    for n in range(2, max_n + 1):
        found: set[int] = set()
        last_progress = time.monotonic()
        for old_index, old_mask in enumerate(classes[n - 1], 1):
            old = adj_from_mask(n - 1, old_mask)
            for neighborhood in range(1 << (n - 1)):
                adjacency = [value for value in old] + [0]
                for vertex in range(n - 1):
                    if (neighborhood >> vertex) & 1:
                        adjacency[vertex] |= 1 << (n - 1)
                        adjacency[n - 1] |= 1 << vertex
                found.add(canonical_graph(n, mask_from_adj(tuple(adjacency))))
            if time.monotonic() - last_progress >= 30:
                print(f"  graphs n={n}: extended {old_index}/{len(classes[n - 1])} parent classes; "
                      f"{len(found)} canonical classes so far")
                last_progress = time.monotonic()
        classes[n] = sorted(found)
        assert len(found) == GRAPH_COUNTS[n], (n, len(found), GRAPH_COUNTS[n])
        print(f"  graphs n={n}: {len(found)} classes")
    return classes


def graph_spec(n: int, mask: int, index: int) -> CodeSpec:
    adjacency = adj_from_mask(n, mask)
    generators = tuple((1 << vertex, adjacency[vertex]) for vertex in range(n))
    edges = [[i, j] for i in range(n) for j in range(i + 1, n) if (adjacency[i] >> j) & 1]
    return CodeSpec(f"graph-{n}-{index:05d}", "selfdual_graph", n, generators,
                    graph_edges=edges, graph_state=True)


@cache
def subspaces(n: int) -> tuple[tuple[int, ...], ...]:
    spaces: set[frozenset[int]] = {frozenset((0,))}
    frontier = [frozenset((0,))]
    while frontier:
        current = frontier.pop()
        for vector in range(1, 1 << n):
            if vector in current:
                continue
            extended = frozenset((*current, *(item ^ vector for item in current)))
            if extended not in spaces:
                spaces.add(extended)
                frontier.append(extended)
    ordered = sorted(spaces, key=lambda space: (len(space), tuple(sorted(space))))
    return tuple(tuple(sorted(space)) for space in ordered)


def basis_of_space(space: Iterable[int], n: int) -> tuple[int, ...]:
    return rref(space, n)


def orthogonal_basis(space_basis: Iterable[int], n: int) -> tuple[int, ...]:
    return nullspace(space_basis, n)


def css_generators(n: int, c1: tuple[int, ...], c2: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    c2_basis = basis_of_space(c2, n)
    c1_basis = basis_of_space(c1, n)
    return tuple((value, 0) for value in c2_basis) + tuple((0, value) for value in orthogonal_basis(c1_basis, n))


def exhaustive_css_specs(max_n: int) -> list[CodeSpec]:
    output = []
    for n in range(1, min(max_n, 5) + 1):
        spaces = subspaces(n)
        sets = [set(space) for space in spaces]
        count = 0
        for i, c1 in enumerate(spaces):
            for j, c2 in enumerate(spaces):
                if not sets[j].issubset(sets[i]):
                    continue
                output.append(CodeSpec(f"css-{n}-{count:06d}", "css", n,
                                       css_generators(n, c1, c2), css_as_given=True))
                count += 1
        print(f"  exhaustive CSS n={n}: {count} pairs")
    return output


def stable_seed(master: int, *parts: object) -> int:
    digest = hashlib.sha256(":".join(map(str, parts)).encode("ascii")).digest()
    return master + int.from_bytes(digest[:8], "big")


def random_independent_vectors(rng: random.Random, n: int, dimension: int) -> tuple[int, ...]:
    basis: tuple[int, ...] = ()
    while len(basis) < dimension:
        candidate = rng.randrange(1, 1 << n)
        reduced = rref((*basis, candidate), n)
        if len(reduced) > len(basis):
            basis = reduced
    return basis


def random_css_specs(max_n: int, master_seed: int) -> list[CodeSpec]:
    output = []
    for n in range(6, min(max_n, 8) + 1):
        for index in range(500):
            derived = stable_seed(master_seed, "css", n, index)
            rng = random.Random(derived)
            dim_c1 = rng.randrange(n + 1)
            dim_c2 = rng.randrange(dim_c1 + 1)
            c1_basis = random_independent_vectors(rng, n, dim_c1)
            c1_elements = span(c1_basis)
            coefficient_basis = random_independent_vectors(rng, dim_c1, dim_c2) if dim_c1 else ()
            c2_basis = tuple(c1_elements[coefficient] for coefficient in coefficient_basis)
            c1 = tuple(sorted(c1_elements))
            c2 = tuple(sorted(span(c2_basis)))
            output.append(CodeSpec(f"css-random-{n}-{index:03d}", "css", n,
                                   css_generators(n, c1, c2), derived_seed=derived,
                                   css_as_given=True))
        print(f"  seeded CSS n={n}: 500 pairs")
    return output


def named_specs() -> list[CodeSpec]:
    # [[4,2,2]] error-detecting code; Gottesman, PhD thesis (1997), Sec. 3.2.
    code_422 = CodeSpec("named-4-2-2", "named", 4,
                        ((0b1111, 0), (0, 0b1111)), css_as_given=True, named=True)

    # [[5,1,3]] perfect code; Laflamme et al., Phys. Rev. Lett. 77 (1996).
    word = ((1 << 0) | (1 << 3), (1 << 1) | (1 << 2))  # XZZXI
    cyclic = []
    mask = (1 << 5) - 1
    x, z = word
    for _ in range(4):
        cyclic.append((x, z))
        x = ((x << 1) | (x >> 4)) & mask
        z = ((z << 1) | (z >> 4)) & mask
    code_513 = CodeSpec("named-5-1-3", "named", 5, tuple(cyclic), named=True)

    # Steane [[7,1,3]] CSS code from the [7,4,3] Hamming code;
    # Steane, Proc. Roy. Soc. A 452 (1996).
    simplex = (0b0001111, 0b0110011, 0b1010101)
    steane_generators = tuple((row, 0) for row in simplex) + tuple((0, row) for row in simplex)
    code_713 = CodeSpec("named-steane-7-1-3", "named", 7, steane_generators,
                        css_as_given=True, named=True)

    # [[8,3,2]] cube/3D color code; Bombin and Martin-Delgado,
    # Phys. Rev. Lett. 97, 180501 (2006).  One X cell and four independent
    # Z cell/face checks (the RM(1,3) words) give this standard presentation.
    rm_basis = (0b11111111, 0b00001111, 0b00110011, 0b01010101)
    color_generators = ((0b11111111, 0),) + tuple((0, row) for row in rm_basis)
    code_832 = CodeSpec("named-color-8-3-2", "named", 8, color_generators,
                        css_as_given=True, named=True)
    return [code_422, code_513, code_713, code_832]


def random_stabilizer_generators(n: int, k: int, rng: random.Random) -> tuple[tuple[int, int], ...]:
    target = n - k
    generators: list[tuple[int, int]] = []
    attempts = 0
    while len(generators) < target:
        attempts += 1
        if attempts > 100_000:
            raise RuntimeError(f"commuting completion stalled for n={n}, k={k}")
        candidate = (rng.getrandbits(n), rng.getrandbits(n))
        if candidate == (0, 0) or not all(commute(candidate, old) for old in generators):
            continue
        if rank((packed(g, n) for g in (*generators, candidate)), 2 * n) == len(generators) + 1:
            generators.append(candidate)
    return tuple(generators)


def random_control_specs(max_n: int, master_seed: int) -> list[CodeSpec]:
    output = []
    for n in range(4, min(max_n, 8) + 1):
        for k in range(1, n - 1):
            for index in range(100):
                derived = stable_seed(master_seed, n, k, index)
                generators = random_stabilizer_generators(n, k, random.Random(derived))
                output.append(CodeSpec(f"random-{n}-{k}-{index:03d}", "random_control", n,
                                       generators, derived_seed=derived, random_control=True))
            print(f"  random controls n={n}, k={k}: 100 codes")
    return output


def structural_flags(spec: CodeSpec, k: int, elements: list[int], a: list[int]) -> dict[str, bool]:
    n = spec.n
    element_set = set(elements)
    even = all(index % 2 == 0 for index, value in enumerate(a) if index and value)
    gf4 = False
    if k == 0:
        gf4 = all(packed((z, x ^ z), n) in element_set for x, z in spec.generators)
    pure_x = sum((value >> n) == 0 for value in elements)
    mask = (1 << n) - 1
    pure_z = sum((value & mask) == 0 for value in elements)
    return {
        "selfdual": k == 0,
        "even": even,
        "gf4_linear": gf4,
        "css_decomposable": pure_x * pure_z == len(elements),
        "css_as_given": spec.css_as_given,
        "graph_state": spec.graph_state,
        "named": spec.named,
        "random_control": spec.random_control,
        "distance_optimal": False,
        "trivial": False,
    }


def fingerprint(n: int, k: int, a: list[int], b: list[int],
                complete: dict[tuple[int, int, int, int], int]) -> tuple[object, ...]:
    return n, k, tuple(a), tuple(b), tuple(sorted(complete.items()))


def subclass_memberships(flags: dict[str, bool]) -> dict[str, bool]:
    return {
        "selfdual_graph": flags["selfdual"] and flags["graph_state"],
        "even_selfdual": flags["selfdual"] and flags["even"],
        "gf4_linear": flags["gf4_linear"],
        "css_decomposable": flags["css_decomposable"],
        "css_constructed": flags["css_as_given"],
        "distance_optimal": flags["distance_optimal"],
        "named": flags["named"],
        "random_control": flags["random_control"],
    }


def validation_gate(classes: dict[int, list[int]], graph_specs: list[CodeSpec],
                    named: list[CodeSpec], core_rows: list[dict[str, object]], max_n: int) -> dict[str, object]:
    print("validation gate:")
    counts = {str(n): len(classes[n]) for n in range(1, max_n + 1)}
    assert all(len(classes[n]) == GRAPH_COUNTS[n] for n in range(1, max_n + 1))
    print(f"  PASS A000088 graph counts through n={max_n}: {counts}")

    graph_crosschecks = 0
    for spec in graph_specs:
        if spec.n > 5:
            continue
        _, _, symplectic_complete = enumerate_stabilizer(spec.n, spec.generators)
        adjacency = [0] * spec.n
        for i, j in spec.graph_edges or []:
            adjacency[i] |= 1 << j
            adjacency[j] |= 1 << i
        closed: Counter[tuple[int, int, int, int]] = Counter()
        for subset in range(1 << spec.n):
            letter_counts = [0, 0, 0, 0]
            for vertex in range(spec.n):
                selected = (subset >> vertex) & 1
                odd_neighbors = parity(adjacency[vertex] & subset)
                letter = 2 if selected and odd_neighbors else 1 if selected else 3 if odd_neighbors else 0
                letter_counts[letter] += 1
            closed[tuple(letter_counts)] += 1
        assert dict(closed) == symplectic_complete
        graph_crosschecks += 1
    print(f"  PASS graph-state closed form: {graph_crosschecks} graphs (all n<=5)")

    named_parameters = {}
    advertised = {"named-4-2-2": (4, 2, 2), "named-5-1-3": (5, 1, 3),
                  "named-steane-7-1-3": (7, 1, 3), "named-color-8-3-2": (8, 3, 2)}
    for spec in named:
        k = validate_generators(spec.n, spec.generators)
        d = code_distance(spec.n, k, spec.generators)
        assert (spec.n, k, d) == advertised[spec.id], (spec.id, spec.n, k, d)
        named_parameters[spec.id] = [spec.n, k, d]
    print(f"  PASS named-code parameters: {named_parameters}")

    macwilliams_checked = 0
    validation_specs = {spec.id: spec for spec in named}
    for row in core_rows:
        spec = row["spec"]
        assert isinstance(spec, CodeSpec)
        if spec.n <= 4:
            validation_specs[spec.id] = spec
    for spec in validation_specs.values():
        _, a, _ = enumerate_stabilizer(spec.n, spec.generators)
        b = macwilliams(a, len(spec.generators))
        assert b == direct_centralizer_counts(spec.n, spec.generators), spec.id
        macwilliams_checked += 1
    print(f"  PASS MacWilliams/direct-centralizer cross-check: {macwilliams_checked} codes")

    assert sequence_check([math.comb(5, j) for j in range(6)])["c3"]["pass"]
    one_one_one = sequence_check([1, 1, 1])
    assert one_one_one["c2"]["pass"] and not one_one_one["c3"]["pass"]
    e2 = {tuple(1 if index in pair else 0 for index in range(4)): 1
          for pair in itertools.combinations(range(4), 2)}
    assert c4_check(e2)["pass"]
    crossed = {(1, 1, 0, 0): 1, (0, 0, 1, 1): 1}
    assert not c4_check(crossed)["pass"]
    crossed_hessian = hessian_check(crossed, 2)
    assert not crossed_hessian["pass"]
    positive_product = polynomial_product([
        {(1, 0, 0, 0): 1, (0, 1, 0, 0): 2},
        {(1, 0, 0, 0): 3, (0, 0, 1, 0): 1},
        {(0, 1, 0, 0): 1, (0, 0, 0, 1): 1},
    ])
    assert c4_check(positive_product)["pass"]
    bell_v1 = sequence_check([1, 0, 3])
    bell_v2 = variants([1, 0, 3])["V2"]
    assert not bell_v1["c2"]["pass"] and bell_v1["c2"]["first_violating_index"] == 1
    assert bell_v2 == [3]
    print("  PASS Branden-Huh checker self-tests and Bell-pair sanity")
    print("validation gate: PASS")
    return {
        "passed": True,
        "a000088": {"pass": True, "counts": counts},
        "graph_state_closed_form": {"pass": True, "n_graphs": graph_crosschecks},
        "macwilliams_vs_centralizer": {"pass": True, "n_codes": macwilliams_checked},
        "branden_huh_self_tests": {"pass": True, "tests": 6},
        "named_code_parameters": {"pass": True, "parameters": named_parameters},
    }


def make_core_rows(specs: list[CodeSpec]) -> list[dict[str, object]]:
    rows = []
    last_progress = time.monotonic()
    for index, spec in enumerate(specs, 1):
        k = validate_generators(spec.n, spec.generators)
        elements, a, complete = enumerate_stabilizer(spec.n, spec.generators)
        b = macwilliams(a, len(spec.generators))
        logical = [right - left for left, right in zip(a, b, strict=True)]
        assert all(value >= 0 for value in logical)
        flags = structural_flags(spec, k, elements, a)
        rows.append({"spec": spec, "k": k, "elements": elements, "A": a, "B": b,
                     "BA": logical, "complete": complete, "flags": flags,
                     "fingerprint": fingerprint(spec.n, k, a, b, complete)})
        if time.monotonic() - last_progress >= 30:
            print(f"  catalog core: {index}/{len(specs)} codes processed")
            last_progress = time.monotonic()
    print(f"  catalog core: {len(specs)} codes processed")
    return rows


def process_rows(core_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    order: list[tuple[object, ...]] = []
    for row in core_rows:
        fp = row["fingerprint"]
        assert isinstance(fp, tuple)
        if fp not in groups:
            groups[fp] = []
            order.append(fp)
        groups[fp].append(row)

    check_cache: dict[tuple[object, ...], tuple[dict[str, object], dict[str, object]]] = {}
    dedup_rows = []
    last_progress = time.monotonic()
    for class_index, fp in enumerate(order):
        members = groups[fp]
        representative = members[0]
        spec = representative["spec"]
        assert isinstance(spec, CodeSpec)
        k = int(representative["k"])
        distance = code_distance(spec.n, k, spec.generators)
        best = SELFDUAL_MAX_DISTANCE[spec.n] if k == 0 else BEST_KNOWN_DISTANCE[spec.n][k]

        aggregate_flags = dict(representative["flags"])
        for flag in ("graph_state", "css_as_given", "named", "random_control", "gf4_linear"):
            aggregate_flags[flag] = any(bool(member["flags"][flag]) for member in members)
        aggregate_flags["distance_optimal"] = distance == best

        primary = representative["A"] if k == 0 else representative["BA"]
        primary_v2 = variants(primary)["V2"]
        aggregate_flags["trivial"] = spec.n <= 2 or len(primary_v2) <= 2

        if fp not in check_cache:
            enumerator_checks: dict[str, object] = {"A": all_sequence_checks(representative["A"])}
            if k > 0:
                enumerator_checks["B"] = all_sequence_checks(representative["B"])
                enumerator_checks["B-A"] = all_sequence_checks(representative["BA"])
            complete = complete_checks(representative["complete"], spec.n)
            if complete["V2"]["pass"]:
                # Specializing complete V2=P-x_I^n preserves homogeneous degree n:
                # its coefficient vector is (0,A_1,...,A_n), not the separately
                # reported lower-degree univariate V2 slice.
                specialized_v2 = sequence_check([0, *representative["A"][1:]])
                assert specialized_v2["c3"]["pass"] and specialized_v2["c2"]["pass"], \
                    f"C4=>C3=>C2 consistency failed for {spec.id}"
            check_cache[fp] = enumerator_checks, complete
        enumerator_checks, complete = check_cache[fp]

        representative_id = spec.id
        for member_index, member in enumerate(members):
            member["flags"]["distance_optimal"] = aggregate_flags["distance_optimal"]
            member["flags"]["trivial"] = aggregate_flags["trivial"]
            member["checks"] = enumerator_checks
            member["complete_checks"] = complete
            member["representative_id"] = representative_id
            member["is_representative"] = member_index == 0
            member["distance"] = distance if member_index == 0 else None
        representative["dedup_flags"] = aggregate_flags
        representative["distance"] = distance
        dedup_rows.append(representative)
        if time.monotonic() - last_progress >= 30:
            print(f"  dedup/checks: {class_index + 1}/{len(order)} fingerprints")
            last_progress = time.monotonic()
    print(f"  dedup/checks: {len(order)} fingerprints from {len(core_rows)} raw codes")

    json_rows = []
    for row in core_rows:
        spec = row["spec"]
        assert isinstance(spec, CodeSpec)
        entry = {
            "id": spec.id, "class": spec.code_class, "n": spec.n, "k": row["k"],
            "d": row["distance"], "flags": row["flags"],
            "generators": [[hex(x), hex(z)] for x, z in spec.generators],
            "graph_edges": spec.graph_edges, "derived_seed": spec.derived_seed,
            "A": row["A"], "B": row["B"], "checks": row["checks"],
            "complete": row["complete_checks"],
            "dedup_representative": row["representative_id"],
            "complete_A": ([[*exponent, count] for exponent, count in sorted(row["complete"].items())]
                           if row["is_representative"] else None),
        }
        if row["is_representative"]:
            entry["dedup_flags"] = row["dedup_flags"]
        json_rows.append(entry)
    return json_rows, dedup_rows


def available_tests(rows: list[dict[str, object]]) -> list[tuple[str, str, str]]:
    tests = set()
    for row in rows:
        for enumerator, variant_map in row["checks"].items():
            for variant, result in variant_map.items():
                for check in ("c1", "c2", "c3"):
                    if check in result:
                        tests.add((enumerator, variant, check))
        for variant in ("V1", "V2"):
            tests.add(("complete_A", variant, "c4"))
    return sorted(tests)


def row_passes(row: dict[str, object], enumerator: str, variant: str, check: str) -> bool | None:
    if enumerator == "complete_A":
        result = row["complete_checks"].get(variant)
        return bool(result["pass"]) if result is not None else None
    variants_map = row["checks"].get(enumerator)
    if variants_map is None or variant not in variants_map:
        return None
    return bool(variants_map[variant][check]["pass"])


def build_crosstab(rows: list[dict[str, object]], deduplicated: bool) -> dict[str, object]:
    output = {}
    for enumerator, variant, check in available_tests(rows):
        key = f"{enumerator}/{variant}/{check}"
        populations: dict[str, list[dict[str, object]]] = {name: [] for name in SINGLE_SUBCLASSES}
        for row in rows:
            flags = row["dedup_flags"] if deduplicated else row["flags"]
            if flags["trivial"] or row_passes(row, enumerator, variant, check) is None:
                continue
            memberships = subclass_memberships(flags)
            for name, belongs in memberships.items():
                if belongs:
                    populations[name].append(row)
        for left, right in itertools.combinations(SINGLE_SUBCLASSES, 2):
            intersection = [row for row in rows
                            if not (row["dedup_flags"] if deduplicated else row["flags"])["trivial"]
                            and row_passes(row, enumerator, variant, check) is not None
                            and subclass_memberships(row["dedup_flags"] if deduplicated else row["flags"])[left]
                            and subclass_memberships(row["dedup_flags"] if deduplicated else row["flags"])[right]]
            if len(intersection) >= 20:
                populations[f"{left}&{right}"] = intersection
        table = {}
        for name, population in sorted(populations.items()):
            failures = sum(not row_passes(row, enumerator, variant, check) for row in population)
            table[name] = {"n_codes": len(population), "n_fail": failures,
                           "fail_frac": failures / len(population) if population else None}
        output[key] = table
    return output


def build_criterion(rows: list[dict[str, object]]) -> dict[str, object]:
    populations: dict[str, list[dict[str, object]]] = {name: [] for name in SINGLE_SUBCLASSES}
    for row in rows:
        flags = row["dedup_flags"]
        if flags["trivial"]:
            continue
        memberships = subclass_memberships(flags)
        for name, belongs in memberships.items():
            if belongs:
                populations[name].append(row)
    for left, right in itertools.combinations(SINGLE_SUBCLASSES, 2):
        intersection = [row for row in rows if not row["dedup_flags"]["trivial"]
                        and subclass_memberships(row["dedup_flags"])[left]
                        and subclass_memberships(row["dedup_flags"])[right]]
        if len(intersection) >= 20:
            populations[f"{left}&{right}"] = intersection

    per_subclass = {}
    for name, population in sorted(populations.items()):
        failures = 0
        for row in population:
            enumerator = "A" if row["k"] == 0 else "B-A"
            failures += not row["checks"][enumerator]["V2"]["c2"]["pass"]
        per_subclass[name] = {"n_codes": len(population), "n_fail": failures,
                              "fail_frac": failures / len(population) if population else None,
                              "eligible": len(population) >= 20,
                              "role": "control" if "random_control" in name else "candidate"}

    eligible_candidates = [item for name, item in per_subclass.items()
                           if item["eligible"] and item["role"] == "candidate"
                           and "random_control" not in name]
    control = per_subclass["random_control"]
    fired = bool(eligible_candidates) and all(item["fail_frac"] >= 0.10 for item in eligible_candidates) \
        and all(item["fail_frac"] != 0 for item in eligible_candidates)
    survival = any(item["fail_frac"] == 0 for item in eligible_candidates) \
        and control["eligible"] and control["fail_frac"] >= 0.10
    if fired:
        reason = "FIRED: every eligible candidate subclass fails at >= theta=0.10 and none has zero failures."
    elif survival:
        reason = "SURVIVAL TRIGGER: an eligible candidate has zero failures while random_control fails at >= theta=0.10."
    elif not eligible_candidates:
        reason = "NOT FIRED: no candidate subclass reaches the deduplicated non-trivial floor of 20."
    else:
        reason = "NOT FIRED: at least one eligible candidate is below theta=0.10 or has zero failures."
    return {"fired": fired, "survival_trigger": survival, "reason": reason,
            "per_subclass": per_subclass}


def conventions() -> dict[str, object]:
    return {
        "paulis": "n-qubit Paulis modulo phase are symplectic bit pairs (x,z); phases do not affect any weight statistic",
        "enumerators": {
            "A": "unnormalized stabilizer weight counts, always tested",
            "B": "integer MacWilliams transform A(x+3y,x-y)/2^(n-k), tested for k>0",
            "B-A": "non-stabilizer centralizer/logical counts, tested for k>0",
            "complete_A": "counts indexed by (nI,nX,nY,nZ)",
        },
        "variants": {
            "V1": "raw sequence or complete polynomial",
            "V2": "sequence from first nonzero weight >=1 through last nonzero; complete polynomial minus x_I^n; PRIMARY",
            "V3": "for even nonzero support, (a_0,a_2,a_4,...) reindexed",
            "V2oV3": "V2 slicing applied after V3 reindexing",
        },
        "checks": {
            "C1": "support is a contiguous index interval; first gap recorded",
            "C2": "a_j^2 >= a_(j-1) a_(j+1), exact integers",
            "C3": "ULC / exact bivariate Lorentzianity using binomial cross-multiplication, plus C1",
            "C4": "M-convex support plus every degree-2 coordinate partial Hessian has at most one positive eigenvalue; exact integer characteristic polynomials and Descartes sign changes",
        },
        "flags": {
            "selfdual": "k==0", "even": "all nonzero A support weights are even",
            "gf4_linear": "k=0 and stabilizer span closed under (x,z)->(z,x XOR z)",
            "css_decomposable": "|S_X|*|S_Z|=|S| (basis-independent operational CSS flag)",
            "css_as_given": "constructed as CSS / all supplied generators pure X or pure Z",
            "graph_state": "graph construction provenance", "named": "named-code provenance",
            "distance_optimal": "d equals the hard-coded n<=8 best-known table",
            "trivial": "n<=2 or registered-primary V2 sequence length<=2",
        },
        "dedup": "fingerprint=(n,k,A,B,sorted complete_A); first seen is representative; provenance flags OR across members; gf4_linear means any member has it",
        "cross_tabs": "raw and deduplicated; trivial codes excluded; pairwise intersections emitted when population >=20",
        "criterion_registration": {
            "primary": "A/V2/C2 for k=0; B-A/V2/C2 for k>0",
            "theta": 0.10, "minimum_deduplicated_nontrivial_members": 20,
            "fires": "every eligible candidate subclass has fail_frac>=0.10 and none has fail_frac==0",
            "survival": "some eligible candidate has zero failures while random_control fail_frac>=0.10",
        },
        "random_controls": "seeded commuting-completion ensemble; generic control, not a uniform census",
    }


def print_primary_summary(criterion: dict[str, object]) -> None:
    print("\nPrimary deduplicated cross-tab (registered mixed enumerator, V2/C2):")
    print(f"{'subclass':42s} {'n':>7s} {'fail':>7s} {'fraction':>10s}")
    for name, item in criterion["per_subclass"].items():
        if "&" in name and not item["eligible"]:
            continue
        fraction = "--" if item["fail_frac"] is None else f"{item['fail_frac']:.3f}"
        print(f"{name:42s} {item['n_codes']:7d} {item['n_fail']:7d} {fraction:>10s}")
    print(f"\nKill criterion 1: {'FIRED' if criterion['fired'] else 'NOT FIRED'}")
    print(f"  {criterion['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-n", type=int, default=8, choices=range(1, 9))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    started = time.perf_counter()
    phase_started = started
    output_path = args.out or Path(__file__).resolve().parent / f"results-seed{args.seed}.json"
    print(f"seed={args.seed}")
    print(f"python={platform.python_version()}")
    print(f"platform={platform.platform()}")
    print(f"max_n={args.max_n}")

    classes = graph_classes(args.max_n)
    graph_code_specs = [graph_spec(n, mask, index) for n in range(1, args.max_n + 1)
                        for index, mask in enumerate(classes[n])]
    print(f"phase graph enumeration: {time.perf_counter() - phase_started:.3f} s")

    phase_started = time.perf_counter()
    named_all = named_specs()
    specs = list(graph_code_specs)
    specs += exhaustive_css_specs(args.max_n)
    specs += random_css_specs(args.max_n, args.seed)
    specs += [spec for spec in named_all if spec.n <= args.max_n]
    specs += random_control_specs(args.max_n, args.seed)
    core_rows = make_core_rows(specs)
    print(f"phase catalog setup: {time.perf_counter() - phase_started:.3f} s")

    phase_started = time.perf_counter()
    validation = validation_gate(classes, graph_code_specs, named_all, core_rows, args.max_n)
    print(f"phase validation gate: {time.perf_counter() - phase_started:.3f} s")

    phase_started = time.perf_counter()
    codes, dedup_rows = process_rows(core_rows)
    crosstab = build_crosstab(core_rows, False)
    crosstab_dedup = build_crosstab(dedup_rows, True)
    criterion = build_criterion(dedup_rows)
    print(f"phase experiments/checks: {time.perf_counter() - phase_started:.3f} s")

    elapsed = time.perf_counter() - started
    raw_counts = Counter(spec.code_class for spec in specs)
    dedup_counts = Counter(row["spec"].code_class for row in dedup_rows)
    output = {
        "metadata": {
            "seed": args.seed, "python": platform.python_version(), "platform": platform.platform(),
            "command_line": sys.argv, "wall_seconds": elapsed, "max_n": args.max_n,
            "counts_per_class": {"raw": dict(sorted(raw_counts.items())),
                                 "dedup_first_seen": dict(sorted(dedup_counts.items())),
                                 "raw_total": len(specs), "dedup_total": len(dedup_rows)},
        },
        "conventions": conventions(), "validation": validation, "codes": codes,
        "crosstab": crosstab, "crosstab_dedup": crosstab_dedup,
        "criterion_mapping": criterion,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    print_primary_summary(criterion)
    print(f"\nWall-clock time: {elapsed:.3f} s")
    print(f"JSON: {output_path} ({os.path.getsize(output_path) / (1024 * 1024):.2f} MiB)")


if __name__ == "__main__":
    main()
