#!/usr/bin/env python3
"""Exact Danielsen--Parker n<=12 extension test for the frozen H1 lead.

The implementation is Python-stdlib-only.  It streams the 1.3-million-record
database and uses exact integer arithmetic throughout.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import platform
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path


BASE_URL = "https://www.codetables.de/larsed/vncorbits/"
BIG_FILE = "thebigselfdualfile.txt.gz"
GRAPH_FILES = {
    **{n: f"vncorbits{n}.g6" for n in range(1, 12)},
    12: "vncorbits12.g6.gz",
    14: "vncorbits14.g6",
}
REQUIRED_FILES = (BIG_FILE, *(GRAPH_FILES[n] for n in range(1, 13)), GRAPH_FILES[14])

EXPECTED_SHA256 = {
    "thebigselfdualfile.txt.gz": "75af3203e86e6ac5726795c84bdacd32f1d13d7c0f1f84b8e3a664724b8d5855",
    "vncorbits1.g6": "ecf5de1a2ecc66a1876a832804c64f6b5125784e94c82285d9720621c613ab46",
    "vncorbits2.g6": "fae4bfc454bd04363dcd5222772f2973b1193e1ff6f676e822a427323a677ef9",
    "vncorbits3.g6": "881159da90c6f28631b6a3eafd6d6d13cda0d0e4cc09d828374719d272f3da34",
    "vncorbits4.g6": "9879efc8c9b3235f2c57306a13c1f9548cf56e9795671a542f04b2a4dfc3c547",
    "vncorbits5.g6": "cb031d9b7c45046642715d9456b22b909624185e3abb0103e7e79cf8c33d53af",
    "vncorbits6.g6": "5a6dba6aec9a4ad3c02e0abcdca6af9589d8cd5cca44714c0a07cc60430ed222",
    "vncorbits7.g6": "db980752c571699473a557f689321bbd499e4c12ff75b38da8b3bed3bb6fda80",
    "vncorbits8.g6": "f8a6c82c4293a57352f83c8dda2248fb8d02fefcfba6a883ae5f329b1437321f",
    "vncorbits9.g6": "4a15f367e53ae2cdd6bd715d3570f44a3ac0e38fcec5caf945c4a3da51512ab0",
    "vncorbits10.g6": "57f6ef1769d7fc20114e1c9a996c23523b90e36635e051f95e81f1a09e354f5f",
    "vncorbits11.g6": "115b53faf9069946fb8760315f4acc5f0ff33e8a8f2f524a7fd7677a5bb9bcbc",
    "vncorbits12.g6.gz": "3c795d8325fea274b1b75cf495d860c33bd31f422c0d488ac959062a8fda907c",
    "vncorbits14.g6": "e86a9589a1cd615c2f1286c60814e74081e3a3db53cb34fc9f07ddf662e6b9ee",
}

# Danielsen--Parker, J. Combin. Theory Ser. A 113(7):1351--1367 (2006),
# arXiv:math.CO/0504522, classification tables.  The total sequence is also
# OEIS A094927 and the indecomposable sequence is OEIS A090899.
EXPECTED_TOTAL = {
    1: 1, 2: 2, 3: 3, 4: 6, 5: 11, 6: 26,
    7: 59, 8: 182, 9: 675, 10: 3990, 11: 45144, 12: 1323363,
}
EXPECTED_INDECOMPOSABLE = {
    1: 1, 2: 1, 3: 1, 4: 2, 5: 4, 6: 11,
    7: 26, 8: 101, 9: 440, 10: 3132, 11: 40457, 12: 1274068,
}
EXPECTED_RUN2_DISTINCT_A = {
    3: (0, 3), 4: (1, 5), 5: (6, 10),
    6: (15, 23), 7: (39, 46), 8: (101, 116),
}
MASK256 = (1 << 256) - 1


class Progress:
    def __init__(self, interval: float = 30.0) -> None:
        self.interval = interval
        self.last = time.monotonic()

    def maybe(self, message: str) -> None:
        now = time.monotonic()
        if now - self.last >= self.interval:
            print(f"progress: {message}", flush=True)
            self.last = now


class MultisetFingerprint:
    """Order-independent, count-sensitive SHA-256 fingerprint."""

    def __init__(self) -> None:
        self.count = 0
        self.xor = 0
        self.sum = 0

    def add(self, value: str) -> None:
        digest = int.from_bytes(hashlib.sha256(value.encode("ascii")).digest(), "big")
        self.count += 1
        self.xor ^= digest
        self.sum = (self.sum + digest) & MASK256

    def as_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "sha256_xor": f"{self.xor:064x}",
            "sha256_sum_mod_2^256": f"{self.sum:064x}",
        }

    def equals(self, other: "MultisetFingerprint") -> bool:
        return (self.count, self.xor, self.sum) == (other.count, other.xor, other.sum)


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="ascii", newline="")
    return path.open("rt", encoding="ascii", newline="")


def download_missing(data_dir: Path, requested: bool) -> dict[str, object]:
    data_dir.mkdir(parents=True, exist_ok=True)
    missing = [name for name in REQUIRED_FILES if not (data_dir / name).is_file()]
    report: dict[str, object] = {
        "flag_requested": requested,
        "network_attempted": bool(missing),
        "policy": "auto-download missing files; never replace an existing staged file",
        "initially_missing": missing,
        "downloaded": [],
        "errors": {},
    }
    if not missing:
        report["status"] = "skipped_all_files_present"
        report["skip_reason"] = "all required files already present; network was not attempted"
        return report
    for name in missing:
        destination = data_dir / name
        temporary = data_dir / f".{name}.part"
        try:
            print(f"downloading {BASE_URL + name}", flush=True)
            with urllib.request.urlopen(BASE_URL + name, timeout=60) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            os.replace(temporary, destination)
            report["downloaded"].append(name)
        except Exception as exc:  # best effort: offline containers are expected
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            report["errors"][name] = f"{type(exc).__name__}: {exc}"
    still_missing = [name for name in REQUIRED_FILES if not (data_dir / name).is_file()]
    report["still_missing"] = still_missing
    report["status"] = "complete" if not still_missing else "incomplete"
    return report


def sha256_file(path: Path, progress: Progress) -> str:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            progress.maybe(f"hashing {path.name}: {size / (1024 * 1024):.1f} MiB")
    return digest.hexdigest()


def decode_graph6(graph6: str) -> tuple[int, tuple[int, ...]]:
    """Decode the n<=62 graph6 form into symmetric adjacency bit rows."""
    if not graph6:
        raise ValueError("empty graph6 string")
    values = [ord(char) - 63 for char in graph6]
    if any(value < 0 or value > 63 for value in values):
        raise ValueError(f"invalid graph6 byte in {graph6!r}")
    n = values[0]
    if n == 63:
        raise ValueError("multi-byte graph6 vertex counts are not supported (n>62)")
    n_bits = n * (n - 1) // 2
    needed = (n_bits + 5) // 6
    if len(values) != needed + 1:
        raise ValueError(f"graph6 length mismatch for n={n}: {graph6!r}")
    bits: list[int] = []
    for value in values[1:]:
        bits.extend((value >> shift) & 1 for shift in range(5, -1, -1))
    if any(bits[n_bits:]):
        raise ValueError(f"nonzero graph6 padding bits: {graph6!r}")
    rows = [0] * n
    position = 0
    for j in range(1, n):
        for i in range(j):
            if bits[position]:
                rows[i] |= 1 << j
                rows[j] |= 1 << i
            position += 1
    return n, tuple(rows)


def graph_connected(rows: tuple[int, ...]) -> bool:
    n = len(rows)
    if n <= 1:
        return True
    reached = 1
    frontier = 1
    while frontier:
        neighbours = 0
        pending = frontier
        while pending:
            bit = pending & -pending
            neighbours |= rows[bit.bit_length() - 1]
            pending ^= bit
        frontier = neighbours & ~reached
        reached |= frontier
    return reached.bit_count() == n


def graph_weight_distribution(rows: tuple[int, ...]) -> list[int]:
    """Enumerate the graph-state stabilizer span using Gray-code updates."""
    n = len(rows)
    mask = (1 << n) - 1
    generators = tuple((1 << vertex) | (rows[vertex] << n) for vertex in range(n))
    counts = [0] * (n + 1)
    counts[0] = 1
    current = 0
    for index in range(1, 1 << n):
        current ^= generators[(index & -index).bit_length() - 1]
        counts[((current & mask) | (current >> n)).bit_count()] += 1
    return counts


def graph6_self_tests() -> dict[str, object]:
    cases = {
        "@": (1, (0,)),
        "A?": (2, (0, 0)),
        "A_": (2, (2, 1)),
        "B?": (3, (0, 0, 0)),
        "Bo": (3, (6, 1, 1)),
    }
    results = {}
    for encoded, expected in cases.items():
        actual = decode_graph6(encoded)
        passed = actual == expected
        results[encoded] = {"pass": passed, "n": actual[0], "adjacency_rows": list(actual[1])}
        if not passed:
            raise AssertionError(f"graph6 self-test failed for {encoded!r}: {actual} != {expected}")
    enumerator_cases = {"A?": [1, 2, 1], "A_": [1, 0, 3], "Bo": [1, 0, 3, 4]}
    for encoded, expected_a in enumerator_cases.items():
        actual_a = graph_weight_distribution(decode_graph6(encoded)[1])
        passed = actual_a == expected_a
        results[encoded]["enumerator_pass"] = passed
        results[encoded]["enumerator"] = actual_a
        if not passed:
            raise AssertionError(f"enumerator self-test failed for {encoded!r}")
    return {"pass": True, "cases": results}


def parse_distribution(field: str, n: int) -> list[int]:
    if len(field) < 2 or field[0] != "{" or field[-1] != "}":
        raise ValueError(f"invalid distribution field {field!r}")
    values = [int(value) for value in field[1:-1].split(",")]
    if len(values) != n + 1 or any(value < 0 for value in values):
        raise ValueError(f"invalid distribution for n={n}: {field!r}")
    return values


def v2(sequence: list[int]) -> list[int]:
    support = [index for index in range(1, len(sequence)) if sequence[index]]
    return sequence[support[0]:support[-1] + 1] if support else []


def halved_v2ov3(sequence: list[int]) -> list[int]:
    support = [index for index in range(1, len(sequence)) if sequence[index]]
    if not support:
        return []
    if any(index & 1 for index in support):
        raise AssertionError("V2oV3 requested for a sequence with odd nonzero support")
    first, last = support[0], support[-1]
    return [sequence[index] for index in range(first, last + 1, 2)]


def c2_pass(sequence: list[int]) -> bool:
    return all(sequence[j] ** 2 >= sequence[j - 1] * sequence[j + 1]
               for j in range(1, len(sequence) - 1))


def exact_checks(sequence: list[int]) -> dict[str, object]:
    support = [index for index, value in enumerate(sequence) if value]
    gaps = ([index for index in range(support[0], support[-1] + 1) if not sequence[index]]
            if support else [])
    c2_violations = []
    c3_violations = []
    degree = len(sequence) - 1
    for j in range(1, len(sequence) - 1):
        triple = [sequence[j - 1], sequence[j], sequence[j + 1]]
        left2 = sequence[j] ** 2
        right2 = sequence[j - 1] * sequence[j + 1]
        if left2 < right2:
            c2_violations.append({"index": j, "triple": triple, "left": left2, "right": right2})
        left3 = left2 * math.comb(degree, j - 1) * math.comb(degree, j + 1)
        right3 = right2 * math.comb(degree, j) ** 2
        if left3 < right3:
            c3_violations.append({"index": j, "triple": triple, "left": left3, "right": right3})
    c1_pass = not gaps
    return {
        "c1": {"pass": c1_pass, "internal_zero_indices": gaps},
        "c2": {"pass": not c2_violations, "violations": c2_violations},
        "c3": {
            "pass": c1_pass and not c3_violations,
            "c1_required": True,
            "violations": c3_violations,
        },
        "pass_all": c1_pass and not c2_violations and not c3_violations,
    }


def fraction(n_fail: int, n_codes: int) -> dict[str, object]:
    return {
        "n_codes": n_codes,
        "n_fail": n_fail,
        "fail_fraction": n_fail / n_codes if n_codes else None,
    }


def should_recompute(n: int, type_label: str, subset_position: int) -> bool:
    return n <= 10 or type_label == "II" or subset_position % 100 == 0


def optimal_code_record(record_id: str, graph6: str, d: int, sequence: list[int],
                        checks: dict[str, object]) -> dict[str, object]:
    return {
        "id": record_id,
        "graph6": graph6,
        "d": d,
        "halved_V2oV3": sequence,
        "checks": checks,
        "pass": checks["pass_all"],
    }


def parse_database(data_dir: Path, max_n: int, progress: Progress) -> dict[str, object]:
    total: Counter[int] = Counter()
    indecomposable: Counter[int] = Counter()
    type_counts: dict[int, Counter[str]] = defaultdict(Counter)
    type_positions: dict[tuple[int, str], int] = defaultdict(int)
    gate2_stats: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    gate2_examples: list[dict[str, object]] = []
    semantic_examples: list[dict[str, object]] = []
    semantic_mismatches: dict[int, Counter[str]] = defaultdict(Counter)
    decomposability_mismatches = Counter()
    fingerprints = {n: MultisetFingerprint() for n in (*range(1, max_n + 1), 14)}
    n14_stored: dict[str, tuple[int, ...]] = {}
    line_count = 0

    with open_text(data_dir / BIG_FILE) as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line_count += 1
            fields = raw_line.rstrip("\r\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"{BIG_FILE}:{line_number}: expected 9 tab-separated fields")
            n = int(fields[0])
            record_position = total[n]
            total[n] += 1
            if fields[2] == "I":
                indecomposable[n] += 1
            elif fields[2] != "D":
                raise ValueError(f"{BIG_FILE}:{line_number}: bad D/I flag {fields[2]!r}")
            type_label = {"1": "I", "2": "II"}.get(fields[3])
            if type_label is None:
                raise ValueError(f"{BIG_FILE}:{line_number}: bad type {fields[3]!r}")
            type_counts[n][type_label] += 1

            # --max-n deliberately excludes intermediate lengths from all gates
            # and census work, but n=14 is retained for its separate cross-check.
            if n > max_n and n != 14:
                progress.maybe(f"parsed {line_count:,} database records")
                continue

            d = int(fields[1])
            distribution = parse_distribution(fields[4], n)
            graph6 = fields[8]
            graph_n, rows = decode_graph6(graph6)
            if graph_n != n:
                raise ValueError(f"{BIG_FILE}:{line_number}: graph6 n={graph_n}, stored n={n}")
            if sum(distribution) != 1 << n or distribution[0] != 1:
                semantic_mismatches[n]["distribution_size_or_identity"] += 1
            detected_type = "II" if all(not distribution[j] for j in range(1, n + 1, 2)) else "I"
            support = [j for j in range(1, n + 1) if distribution[j]]
            detected_d = min(support) if support else None
            record_id = f"bigfile:n={n}:index={record_position}"
            if detected_type != type_label:
                semantic_mismatches[n]["type"] += 1
                if len(semantic_examples) < 20:
                    semantic_examples.append({"id": record_id, "field": "type", "stored": type_label,
                                              "recomputed": detected_type})
            if detected_d != d:
                semantic_mismatches[n]["distance"] += 1
                if len(semantic_examples) < 20:
                    semantic_examples.append({"id": record_id, "field": "d", "stored": d,
                                              "recomputed": detected_d})
            connected = graph_connected(rows)
            expected_connected = fields[2] == "I"
            if connected != expected_connected:
                decomposability_mismatches[n] += 1

            if n == 14:
                fingerprints[14].add(graph6)
                if graph6 in n14_stored:
                    semantic_mismatches[n]["duplicate_graph6"] += 1
                n14_stored[graph6] = tuple(distribution)
                progress.maybe(f"parsed {line_count:,} database records")
                continue

            if fields[2] == "I":
                fingerprints[n].add(graph6)

            subset_position = type_positions[(n, type_label)]
            type_positions[(n, type_label)] += 1
            selected = should_recompute(n, type_label, subset_position)
            stats = gate2_stats[(n, type_label)]
            stats["eligible"] += 1
            if selected:
                stats["recomputed"] += 1
                recomputed = graph_weight_distribution(rows)
                if recomputed != distribution:
                    stats["mismatches"] += 1
                    if len(gate2_examples) < 20:
                        gate2_examples.append({
                            "id": record_id, "graph6": graph6, "stored": distribution,
                            "recomputed": recomputed, "subset_position": subset_position,
                        })
            else:
                stats["used_stored_without_recompute"] += 1

            progress.maybe(f"parsed {line_count:,} database records; gate-(ii) recomputations ongoing")

    return {
        "total": total,
        "indecomposable": indecomposable,
        "type_counts": type_counts,
        "gate2_stats": gate2_stats,
        "gate2_examples": gate2_examples,
        "semantic_mismatches": semantic_mismatches,
        "semantic_examples": semantic_examples,
        "decomposability_mismatches": decomposability_mismatches,
        "fingerprints": fingerprints,
        "n14_stored": n14_stored,
        "line_count": line_count,
    }


def run_completed_range_experiments(data_dir: Path, max_n: int,
                                    progress: Progress) -> dict[str, object]:
    """Run H1 and census only after the validation gates have passed."""
    total: Counter[int] = Counter()
    type_counts: dict[int, Counter[str]] = defaultdict(Counter)
    dmax: dict[int, int] = defaultdict(lambda: -1)
    dmax_ii: dict[int, int] = defaultdict(lambda: -1)
    optimal_ii: dict[int, list[dict[str, object]]] = defaultdict(list)
    census: dict[int, Counter[str]] = defaultdict(Counter)
    distinct_a: dict[int, set[tuple[int, ...]]] = defaultdict(set)

    with open_text(data_dir / BIG_FILE) as handle:
        for line_number, raw_line in enumerate(handle, 1):
            fields = raw_line.rstrip("\r\n").split("\t")
            n = int(fields[0])
            if n > max_n:
                break  # the authoritative file is length-sorted, validated in phase one
            record_position = total[n]
            total[n] += 1
            d = int(fields[1])
            type_label = {"1": "I", "2": "II"}[fields[3]]
            type_counts[n][type_label] += 1
            distribution = parse_distribution(fields[4], n)
            graph6 = fields[8]
            record_id = f"bigfile:n={n}:index={record_position}"

            dmax[n] = max(dmax[n], d)
            census[n]["total"] += 1
            fails_v2_c2 = not c2_pass(v2(distribution))
            census[n]["fail_A_V2_C2"] += fails_v2_c2
            if type_label == "I":
                census[n]["type_I"] += 1
                census[n]["type_I_fail_A_V2_C2"] += fails_v2_c2
            if n <= 8:
                distinct_a[n].add(tuple(distribution))

            if type_label == "II":
                half = halved_v2ov3(distribution)
                checks = exact_checks(half)
                census[n]["even_support"] += 1
                census[n]["fail_A_V2oV3_C2"] += not checks["c2"]["pass"]
                for check in ("c1", "c2", "c3"):
                    census[n][f"typeII_fail_{check}"] += not checks[check]["pass"]
                if d > dmax_ii[n]:
                    dmax_ii[n] = d
                    optimal_ii[n] = [optimal_code_record(record_id, graph6, d, half, checks)]
                elif d == dmax_ii[n]:
                    optimal_ii[n].append(optimal_code_record(record_id, graph6, d, half, checks))
            progress.maybe(f"experiment pass: processed {line_number:,} completed-range records")

    return {
        "total": total,
        "type_counts": type_counts,
        "dmax": dmax,
        "dmax_ii": dmax_ii,
        "optimal_ii": optimal_ii,
        "census": census,
        "distinct_a": distinct_a,
    }


def read_graph_file(path: Path, expected_n: int, progress: Progress) -> dict[str, object]:
    fingerprint = MultisetFingerprint()
    disconnected = 0
    duplicate_count = 0
    seen: set[str] | None = set() if expected_n <= 10 else None
    with open_text(path) as handle:
        for index, raw_line in enumerate(handle):
            graph6 = raw_line.rstrip("\r\n")
            graph_n, rows = decode_graph6(graph6)
            if graph_n != expected_n:
                raise ValueError(f"{path.name}:{index + 1}: graph has n={graph_n}, expected {expected_n}")
            if not graph_connected(rows):
                disconnected += 1
            if seen is not None:
                duplicate_count += graph6 in seen
                seen.add(graph6)
            fingerprint.add(graph6)
            progress.maybe(f"checking {path.name}: {index + 1:,} graphs")
    return {
        "fingerprint_object": fingerprint,
        "fingerprint": fingerprint.as_dict(),
        "line_count": fingerprint.count,
        "disconnected": disconnected,
        "duplicate_count": duplicate_count if seen is not None else None,
        "duplicate_check_policy": "exact set for n<=10; omitted for larger files",
    }


def build_gate1(parsed: dict[str, object], graph_sources: dict[int, dict[str, object]],
                max_n: int) -> dict[str, object]:
    per_n = {}
    for n in range(1, max_n + 1):
        total = parsed["total"][n]
        indecomposable = parsed["indecomposable"][n]
        source = graph_sources[n]
        fingerprint_match = parsed["fingerprints"][n].equals(source["fingerprint_object"])
        passed = (
            total == EXPECTED_TOTAL[n]
            and indecomposable == EXPECTED_INDECOMPOSABLE[n]
            and source["line_count"] == EXPECTED_INDECOMPOSABLE[n]
            and source["disconnected"] == 0
            and parsed["decomposability_mismatches"][n] == 0
            and fingerprint_match
        )
        per_n[str(n)] = {
            "pass": passed,
            "total": total,
            "expected_total": EXPECTED_TOTAL[n],
            "indecomposable": indecomposable,
            "expected_indecomposable": EXPECTED_INDECOMPOSABLE[n],
            "graph_file_lines": source["line_count"],
            "graph_file_all_connected": source["disconnected"] == 0,
            "bigfile_D_I_connectivity_mismatches": parsed["decomposability_mismatches"][n],
            "indecomposable_graph_multiset_fingerprint_match": fingerprint_match,
            "bigfile_indecomposable_fingerprint": parsed["fingerprints"][n].as_dict(),
            "graph_file_fingerprint": source["fingerprint"],
        }
    return {
        "pass": all(item["pass"] for item in per_n.values()),
        "per_n": per_n,
        "published_counts_source": (
            "Danielsen and Parker, On the classification of all self-dual additive codes "
            "over GF(4) of length up to 12, JCTA 113(7):1351-1367 (2006), "
            "arXiv:math.CO/0504522; totals OEIS A094927, indecomposables OEIS A090899"
        ),
    }


def build_gate2(parsed: dict[str, object], max_n: int) -> dict[str, object]:
    per_n = {}
    mismatch_total = 0
    for n in range(1, max_n + 1):
        by_type = {}
        n_mismatch = 0
        n_recomputed = 0
        n_eligible = 0
        for type_label in ("I", "II"):
            stats = parsed["gate2_stats"][(n, type_label)]
            expected_recomputed = (
                stats["eligible"] if n <= 10 or type_label == "II"
                else (stats["eligible"] + 99) // 100
            )
            item = {
                "eligible": stats["eligible"],
                "recomputed": stats["recomputed"],
                "expected_recomputed_by_policy": expected_recomputed,
                "selection_count_ok": stats["recomputed"] == expected_recomputed,
                "used_stored_without_recompute": stats["used_stored_without_recompute"],
                "mismatches": stats["mismatches"],
            }
            by_type[type_label] = item
            n_mismatch += stats["mismatches"]
            n_recomputed += stats["recomputed"]
            n_eligible += stats["eligible"]
        policy_count_ok = all(item["selection_count_ok"] for item in by_type.values())
        per_n[str(n)] = {
            "pass": n_mismatch == 0 and policy_count_ok,
            "eligible": n_eligible,
            "recomputed": n_recomputed,
            "mismatches": n_mismatch,
            "full_recomputation_required": n <= 10,
            "policy_count_ok": policy_count_ok,
            "by_type": by_type,
        }
        mismatch_total += n_mismatch
    semantic_count = sum(sum(parsed["semantic_mismatches"][n].values())
                         for n in range(1, max_n + 1))
    return {
        "pass": mismatch_total == 0 and semantic_count == 0
                and all(item["pass"] for item in per_n.values()),
        "per_n": per_n,
        "enumerator_mismatch_total": mismatch_total,
        "enumerator_mismatch_examples": parsed["gate2_examples"],
        "stored_field_consistency": {
            "pass": semantic_count == 0,
            "mismatch_counts_per_n": {
                str(n): dict(sorted(parsed["semantic_mismatches"][n].items()))
                for n in range(1, max_n + 1)
            },
            "examples": parsed["semantic_examples"],
            "checks": "sum(A)=2^n, A_0=1, stored Type I/II vs even support, stored d vs min nonzero weight",
        },
        "policy": {
            "n_le_10": "recompute every code, decomposable and indecomposable",
            "n_11_12_type_II": "recompute every Type II code",
            "n_11_12_type_I": (
                "deterministic 1% stride: recompute subset positions 0,100,200,... "
                "within each (n,Type I) subset; use stored A for all other census checks"
            ),
        },
    }


def build_h1(parsed: dict[str, object], max_n: int) -> dict[str, object]:
    per_n = {}
    fired = False
    for n in range(2, max_n + 1, 2):
        codes = parsed["optimal_ii"][n]
        failures = [code for code in codes if not code["pass"]]
        fired |= bool(failures)
        per_n[str(n)] = {
            "dmaxII": parsed["dmax_ii"][n],
            "n_optimal": len(codes),
            "n_fail": len(failures),
            "optimal_codes": codes,
            "failures": failures,
            "verdict": "K1 FIRED" if failures else "K1 NOT FIRED",
        }
    return {
        "hypothesis": (
            "Every dmaxII-attaining Type II self-dual additive GF(4) code has a "
            "V2oV3 A-enumerator passing exact C1, C2, and C3"
        ),
        "kill_criterion": "K1 fires if any optimal code at any completed length fails C1, C2, or C3",
        "completed_range": f"n <= {max_n}",
        "per_even_n": per_n,
        "k1_fired": fired,
        "verdict": "K1 FIRED" if fired else "K1 NOT FIRED",
    }


def build_census(parsed: dict[str, object], max_n: int) -> dict[str, object]:
    per_n = {}
    for n in range(1, max_n + 1):
        counts = parsed["census"][n]
        type_ii = parsed["type_counts"][n]["II"]
        per_n[str(n)] = {
            "total_codes": parsed["total"][n],
            "type_I_count": parsed["type_counts"][n]["I"],
            "type_II_count": type_ii,
            "dmax_overall": parsed["dmax"][n],
            "dmaxII": parsed["dmax_ii"][n] if type_ii else None,
            "n_dmaxII_attainers": len(parsed["optimal_ii"][n]),
            "all_codes_A_V2_C2": fraction(counts["fail_A_V2_C2"], counts["total"]),
            "type_I_codes_A_V2_C2": fraction(
                counts["type_I_fail_A_V2_C2"], counts["type_I"]),
            "even_support_codes_A_V2oV3_C2": fraction(
                counts["fail_A_V2oV3_C2"], counts["even_support"]),
            "all_type_II_halved": {
                check: fraction(counts[f"typeII_fail_{check}"], type_ii)
                for check in ("c1", "c2", "c3")
            },
        }
    return {"per_n": per_n}


def build_run2_consistency(parsed: dict[str, object], max_n: int) -> dict[str, object]:
    per_n = {}
    passed = True
    for n in range(3, min(max_n, 8) + 1):
        distributions = parsed["distinct_a"][n]
        n_fail = sum(not c2_pass(v2(list(distribution))) for distribution in distributions)
        expected_fail, expected_total = EXPECTED_RUN2_DISTINCT_A[n]
        item_pass = (n_fail, len(distributions)) == (expected_fail, expected_total)
        passed &= item_pass
        per_n[str(n)] = {
            "pass": item_pass,
            "n_fail_A_V2_C2": n_fail,
            "n_distinct_A": len(distributions),
            "expected_n_fail_A_V2_C2": expected_fail,
            "expected_n_distinct_A": expected_total,
        }
    return {
        "pass": passed,
        "per_n": per_n,
        "comparison": "Entry 4 run-2 per-distinct-A self-dual graph-isomorphism-class table",
        "note": "The bivariate A-enumerator is invariant on each LC orbit.",
    }


def analyze_n14(data_dir: Path, stored: dict[str, tuple[int, ...]],
                big_fingerprint: MultisetFingerprint, big_field_mismatches: Counter[str],
                big_decomposability_mismatches: int, progress: Progress) -> dict[str, object]:
    source = read_graph_file(data_dir / GRAPH_FILES[14], 14, progress)
    fingerprints_match = big_fingerprint.equals(source["fingerprint_object"])
    failures = []
    stored_mismatches = []
    stored_mismatch_count = 0
    distance_counts: Counter[int] = Counter()
    sequences: Counter[tuple[int, ...]] = Counter()
    type_failures = 0
    with open_text(data_dir / GRAPH_FILES[14]) as handle:
        for index, raw_line in enumerate(handle):
            graph6 = raw_line.rstrip("\r\n")
            rows = decode_graph6(graph6)[1]
            distribution = graph_weight_distribution(rows)
            if graph6 not in stored or tuple(distribution) != stored[graph6]:
                stored_mismatch_count += 1
                if len(stored_mismatches) < 20:
                    stored_mismatches.append({"index": index, "graph6": graph6,
                                              "recomputed": distribution,
                                              "stored": list(stored[graph6]) if graph6 in stored else None})
            support = [j for j in range(1, 15) if distribution[j]]
            d = min(support)
            distance_counts[d] += 1
            if any(distribution[j] for j in range(1, 15, 2)):
                type_failures += 1
                continue
            half = halved_v2ov3(distribution)
            sequences[tuple(half)] += 1
            checks = exact_checks(half)
            if not checks["pass_all"]:
                failures.append({"index": index, "graph6": graph6, "d": d,
                                 "halved_V2oV3": half, "checks": checks})
            progress.maybe(f"n=14 extremal recomputation: {index + 1:,}/{source['line_count']:,}")
    distinct_sequences = [
        {"halved_V2oV3": list(sequence), "n_codes": count, "checks": exact_checks(list(sequence))}
        for sequence, count in sorted(sequences.items())
    ]
    count_ok = source["line_count"] == 1020 and len(stored) == 1020
    passed = (count_ok and fingerprints_match and not source["disconnected"]
              and not stored_mismatch_count and not big_field_mismatches
              and not big_decomposability_mismatches
              and not type_failures and not failures
              and set(distance_counts) == {6})
    return {
        "label": "n=14 extremal, indecomposable only — outside the frozen completed-range but decisive if it fails",
        "pass": passed,
        "n_graphs": source["line_count"],
        "expected_n_graphs": 1020,
        "bigfile_n14_records": len(stored),
        "bigfile_graph_multiset_match": fingerprints_match,
        "all_graphs_connected": source["disconnected"] == 0,
        "distance_counts": {str(key): value for key, value in sorted(distance_counts.items())},
        "type_II_failures": type_failures,
        "bigfile_stored_field_mismatch_counts": dict(sorted(big_field_mismatches.items())),
        "bigfile_D_I_connectivity_mismatches": big_decomposability_mismatches,
        "stored_enumerator_mismatch_count": stored_mismatch_count,
        "stored_enumerator_mismatch_examples": stored_mismatches,
        "n_fail": len(failures),
        "failures": failures,
        "distinct_halved_sequences": distinct_sequences,
        "verdict": "DECISIVE FAILURE" if failures else "NO FAILURE (outside completed range)",
    }


def conventions() -> dict[str, object]:
    return {
        "V2": "slice from first nonzero coefficient at weight >=1 through last nonzero coefficient",
        "V3": "for all-even nonidentity support, retain A_0,A_2,A_4,... and reindex",
        "V2oV3": "V2 applied to V3; equivalently for Type II, every other term of the V2 slice",
        "C1": "no internal zeros",
        "C2": "a_j^2 >= a_(j-1)*a_(j+1), exact integer arithmetic",
        "C3": (
            "ULC / bivariate Lorentzianity: a_j^2*C(m,j-1)*C(m,j+1) >= "
            "a_(j-1)*a_(j+1)*C(m,j)^2 by exact integer cross-multiplication; C1 required"
        ),
        "type_II": "all nonzero weights even; independently recomputed from every stored A",
        "graph_state_generators": "generator v has x=e_v and z=adjacency row v; enumerate its 2^n span",
    }


def remove_internal_objects(graph_sources: dict[int, dict[str, object]]) -> None:
    for source in graph_sources.values():
        source.pop("fingerprint_object", None)


def print_summary(gate1: dict[str, object], gate2: dict[str, object], h1: dict[str, object],
                  n14: dict[str, object], consistency: dict[str, object], max_n: int) -> None:
    print("\nData gate (i): published totals + indecomposables + graph-source cross-check")
    for n, item in gate1["per_n"].items():
        print(f"  n={n:>2}: {'PASS' if item['pass'] else 'FAIL'} "
              f"total={item['total']}/{item['expected_total']} "
              f"indecomposable={item['indecomposable']}/{item['expected_indecomposable']}")
    print("Data gate (ii): graph-state A recomputation")
    for n, item in gate2["per_n"].items():
        print(f"  n={n:>2}: {'PASS' if item['pass'] else 'FAIL'} "
              f"recomputed={item['recomputed']}/{item['eligible']} mismatches={item['mismatches']}")
    print("H1 exact optimal-Type-II test")
    for n, item in h1["per_even_n"].items():
        print(f"  n={n:>2}: dmaxII={item['dmaxII']} optimal={item['n_optimal']} "
              f"fail={item['n_fail']} — {item['verdict']}")
    print(f"Run-2 distinct-A consistency: {'PASS' if consistency['pass'] else 'FAIL'}")
    print(f"n=14 extremal (outside completed range): {n14['verdict']}; "
          f"graphs={n14['n_graphs']}, fail={n14['n_fail']}")
    print(f"\n{'K1 FIRED' if h1['k1_fired'] else 'K1 NOT FIRED'} "
          f"(completed range n <= {max_n})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-n", type=int, choices=range(1, 13), default=12,
                        help="limit completed-range gates, census, and H1 (default: 12)")
    parser.add_argument("--data-dir", type=Path,
                        default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent / "results-extend.json")
    parser.add_argument("--download", action="store_true",
                        help="ensure missing data files are downloaded; existing files are never replaced")
    args = parser.parse_args()

    started = time.perf_counter()
    progress = Progress()
    print(f"python={platform.python_version()}")
    print(f"platform={platform.platform()}")
    print(f"max_n={args.max_n}")
    print("numeric_backend=Python stdlib exact integers (numpy not used)")

    download = download_missing(args.data_dir, args.download)
    missing = [name for name in REQUIRED_FILES if not (args.data_dir / name).is_file()]
    if missing:
        print(f"ERROR: required data files are missing after best-effort download: {missing}", file=sys.stderr)
        raise SystemExit(2)

    hash_report = {}
    for name in REQUIRED_FILES:
        actual = sha256_file(args.data_dir / name, progress)
        hash_report[name] = {
            "url": BASE_URL + name,
            "sha256": actual,
            "expected_sha256": EXPECTED_SHA256[name],
            "match": actual == EXPECTED_SHA256[name],
            "bytes": (args.data_dir / name).stat().st_size,
        }
    hash_gate_pass = all(item["match"] for item in hash_report.values())
    self_tests = graph6_self_tests()

    print("phase: streaming authoritative database and running data gate (ii)", flush=True)
    parsed = parse_database(args.data_dir, args.max_n, progress)
    print("phase: secondary indecomposable graph-file cross-checks", flush=True)
    graph_sources = {
        n: read_graph_file(args.data_dir / GRAPH_FILES[n], n, progress)
        for n in range(1, args.max_n + 1)
    }
    gate1 = build_gate1(parsed, graph_sources, args.max_n)
    gate2 = build_gate2(parsed, args.max_n)
    data_gates_pass = hash_gate_pass and self_tests["pass"] and gate1["pass"] and gate2["pass"]
    if not data_gates_pass:
        remove_internal_objects(graph_sources)
        elapsed = time.perf_counter() - started
        failure_output = {
            "metadata": {
                "python": platform.python_version(), "platform": platform.platform(),
                "numeric_backend": "Python standard library; exact arbitrary-precision integers; numpy not used",
                "command_line": sys.argv, "max_n": args.max_n, "wall_seconds": elapsed,
                "data_directory": str(args.data_dir.resolve()), "output_path": str(args.out.resolve()),
                "download": download, "download_base_url": BASE_URL, "files": hash_report,
            },
            "conventions": conventions(),
            "gates": {
                "file_sha256": {"pass": hash_gate_pass, "files": hash_report},
                "graph6_decoder_self_test": self_tests,
                "gate_i_counts_and_graph_sources": gate1,
                "gate_ii_enumerator_recomputation": gate2,
                "all_completed_range_gates_pass": False,
            },
            "h1": {"status": "not run: completed-range data gate failure"},
            "n14_extremal": {"status": "not run: completed-range data gate failure"},
            "census_tables": {"status": "not run: completed-range data gate failure"},
            "consistency_vs_run2": {"status": "not run: completed-range data gate failure"},
            "secondary_graph_sources": {str(n): source for n, source in graph_sources.items()},
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(failure_output, sort_keys=True, separators=(",", ":")) + "\n",
                            encoding="utf-8")
        print("ERROR: a completed-range data gate failed; H1 and census were not run", file=sys.stderr)
        raise SystemExit(1)

    print("phase: data gates passed; running frozen completed-range experiments", flush=True)
    experiments = run_completed_range_experiments(args.data_dir, args.max_n, progress)
    consistency = build_run2_consistency(experiments, args.max_n)
    h1 = build_h1(experiments, args.max_n)
    census = build_census(experiments, args.max_n)
    print("phase: running separate n=14 extremal analysis", flush=True)
    n14 = analyze_n14(args.data_dir, parsed["n14_stored"], parsed["fingerprints"][14],
                      parsed["semantic_mismatches"][14],
                      parsed["decomposability_mismatches"][14], progress)
    validation_pass = data_gates_pass and consistency["pass"]
    elapsed = time.perf_counter() - started

    remove_internal_objects(graph_sources)
    output = {
        "metadata": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numeric_backend": "Python standard library; exact arbitrary-precision integers; numpy not used",
            "command_line": sys.argv,
            "max_n": args.max_n,
            "wall_seconds": elapsed,
            "data_directory": str(args.data_dir.resolve()),
            "output_path": str(args.out.resolve()),
            "download": download,
            "download_base_url": BASE_URL,
            "files": hash_report,
            "parse_counts": {
                "all_records": parsed["line_count"],
                "per_length": {str(n): parsed["total"][n] for n in sorted(parsed["total"])},
                "per_length_type": {
                    str(n): dict(sorted(parsed["type_counts"][n].items()))
                    for n in sorted(parsed["type_counts"])
                },
            },
            "recomputation_policy": gate2["policy"],
            "progress_policy": "print a progress line after approximately every 30 seconds",
        },
        "conventions": conventions(),
        "gates": {
            "file_sha256": {"pass": hash_gate_pass, "files": hash_report},
            "graph6_decoder_self_test": self_tests,
            "gate_i_counts_and_graph_sources": gate1,
            "gate_ii_enumerator_recomputation": gate2,
            "all_completed_range_gates_pass": data_gates_pass,
            "all_validation_checks_pass": validation_pass,
        },
        "h1": h1,
        "n14_extremal": n14,
        "census_tables": census,
        "consistency_vs_run2": consistency,
        "secondary_graph_sources": {str(n): source for n, source in graph_sources.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")) + "\n",
                        encoding="utf-8")
    print_summary(gate1, gate2, h1, n14, consistency, args.max_n)
    print(f"Wall-clock time: {elapsed:.3f} s")
    print(f"JSON: {args.out} ({args.out.stat().st_size / (1024 * 1024):.2f} MiB)")

    if not validation_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
