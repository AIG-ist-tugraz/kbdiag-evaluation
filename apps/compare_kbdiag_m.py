#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Compare KBDiag diagnoses between m=1 and m=2 using FlexDiag quality metrics.

Computes minimality and accuracy per scenario (Felfernig et al. 2018):
    minimality(Δ) = |Δ_min| / |Δ|        (Formula 1)
    accuracy(Δ)   = |Δ ∩ Δ_min| / |Δ_min| (Formula 2)

Where Δ_min = diagnosis with m=1, Δ = diagnosis with m=2.

Usage:
    # TOML config mode (recommended)
    python -m apps.compare_kbdiag_m apps/conf/cognitive/compare_kbdiag_m.toml

    # Legacy positional arg mode
    python -m apps.compare_kbdiag_m [results_dir]

    # Default (no args) — uses data/jiis/results/1
    python -m apps.compare_kbdiag_m
"""

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from apps.verify_diagnosis_quality import (
    extract_first_diagnoses, ROOT_PROJECT_FOLDER, DEFAULT_KB_NAMES, TeeWriter,
)

KB_NAMES_EXTENDED = list(DEFAULT_KB_NAMES)  # public artifact: 6 paper FMs only

TC_SIZE_RE = re.compile(r"_c(\d+)_")


def extract_tc_size(tc_file: str) -> Optional[int]:
    """Extract testcase size from filename like 'DELL_c25_0.testcases'."""
    m = TC_SIZE_RE.search(tc_file)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Metrics (FlexDiag paper, Felfernig et al. 2018)
# ---------------------------------------------------------------------------

def minimality(diag_min: FrozenSet[str], diag: FrozenSet[str]) -> float:
    """Formula (1): minimality(Δ) = |Δ_min| / |Δ|."""
    if len(diag) == 0:
        return 1.0
    return len(diag_min) / len(diag)


def accuracy(diag_min: FrozenSet[str], diag: FrozenSet[str]) -> float:
    """Formula (2): accuracy(Δ) = |Δ ∩ Δ_min| / |Δ_min|."""
    if len(diag_min) == 0:
        return 1.0
    return len(diag & diag_min) / len(diag_min)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str) -> Dict[str, Any]:
    """Parse and validate a TOML comparison config.

    Required schema:
        [comparison]
        results_dir = "..."   # folder with KBDiag first-diag result files (task=1)

        [[kb]]
        name = "DELL"

    Optional:
        [comparison]
        output_dir      = "data/jiis/results-cognitive"
        output_filename = "compare-kbdiag-m.txt"
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p, "rb") as f:
        raw = tomllib.load(f)

    if "comparison" not in raw:
        raise ValueError("Missing required section: [comparison]")
    c = raw["comparison"]
    if "results_dir" not in c:
        raise ValueError("Missing required field: comparison.results_dir")
    if "kb" not in raw or not raw["kb"]:
        raise ValueError("Missing required entries: [[kb]] (at least one)")
    for kb in raw["kb"]:
        if "name" not in kb:
            raise ValueError("Each [[kb]] entry must have a 'name' field")
    has_dir = "output_dir" in c
    has_filename = "output_filename" in c
    if has_dir != has_filename:
        raise ValueError(
            "output_dir and output_filename must both be set or both omitted"
        )
    return raw


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_kb_m(kb_name: str, results_dir: Path) -> List[dict]:
    """Compare m=1 vs m=2 diagnoses for a single KB. Returns per-scenario metrics."""
    m1_file = results_dir / f"results_kbdiag_{kb_name}_1.txt"
    m2_file = results_dir / f"results_kbdiag_{kb_name}_m2_1.txt"

    m1_diags = extract_first_diagnoses(m1_file)
    m2_diags = extract_first_diagnoses(m2_file)

    if not m1_diags:
        print(f"  WARNING: m=1 file not found: {m1_file}")
        return []
    if not m2_diags:
        print(f"  WARNING: m=2 file not found: {m2_file}")
        return []

    results = []
    all_scenarios = sorted(set(m1_diags.keys()) | set(m2_diags.keys()))

    for tc_file in all_scenarios:
        d_min = m1_diags.get(tc_file)  # Δ_min (m=1)
        d = m2_diags.get(tc_file)      # Δ (m=2)

        if d_min is None or d is None:
            results.append({
                "tc_file": tc_file, "skipped": True,
            })
            continue

        results.append({
            "tc_file": tc_file,
            "skipped": False,
            "d_min_size": len(d_min),
            "d_size": len(d),
            "intersection_size": len(d_min & d),
            "minimality": minimality(d_min, d),
            "accuracy": accuracy(d_min, d),
            "match": d_min == d,
            "only_m1": d_min - d,
            "only_m2": d - d_min,
        })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _avg(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def run_comparison(results_dir: Path, kb_names: List[str]) -> None:
    """Run m=1 vs m=2 comparison across given KBs."""
    print(f"Results directory: {results_dir}")
    print(f"Comparing KBDiag m=1 (Δ_min) vs m=2 (Δ)")
    print(f"Metrics: minimality = |Δ_min|/|Δ|, accuracy = |Δ∩Δ_min|/|Δ_min|")
    print("=" * 90)

    total_matched = 0
    total_mismatched = 0
    total_skipped = 0
    by_size: Dict[int, List[Tuple[float, float]]] = defaultdict(list)

    for kb in kb_names:
        print(f"\n--- {kb} ---")
        scenarios = compare_kb_m(kb, results_dir)

        if not scenarios:
            continue

        kb_min_vals: List[float] = []
        kb_acc_vals: List[float] = []
        matched = 0
        mismatched = 0
        skipped = 0

        print(f"  {'Scenario':<30} | {'|Δ_min|':>7} | {'|Δ|':>5} | {'|Δ∩Δ_min|':>9} "
              f"| {'minim':>6} | {'accur':>6} | Status")
        print(f"  {'-'*30}-+-{'-'*7}-+-{'-'*5}-+-{'-'*9}-+-{'-'*6}-+-{'-'*6}-+-------")

        for s in scenarios:
            if s["skipped"]:
                skipped += 1
                print(f"  {s['tc_file']:<30} | {'---':>7} | {'---':>5} | {'---':>9} "
                      f"| {'---':>6} | {'---':>6} | SKIP")
                continue

            status = "OK" if s["match"] else "DIFF"
            print(f"  {s['tc_file']:<30} | {s['d_min_size']:>7} | {s['d_size']:>5} "
                  f"| {s['intersection_size']:>9} | {s['minimality']:>6.3f} "
                  f"| {s['accuracy']:>6.3f} | {status}")

            if s["match"]:
                matched += 1
            else:
                mismatched += 1
                if s["only_m1"]:
                    print(f"    Only in m=1: {sorted(list(s['only_m1'])[:3])}{'...' if len(s['only_m1']) > 3 else ''}")
                if s["only_m2"]:
                    print(f"    Only in m=2: {sorted(list(s['only_m2'])[:3])}{'...' if len(s['only_m2']) > 3 else ''}")

            kb_min_vals.append(s["minimality"])
            kb_acc_vals.append(s["accuracy"])

            tc_size = extract_tc_size(s["tc_file"])
            if tc_size is not None:
                by_size[tc_size].append((s["minimality"], s["accuracy"]))

        if kb_min_vals:
            print(f"\n  Summary: matched={matched} mismatch={mismatched} skip={skipped}"
                  f" | avg_minimality={_avg(kb_min_vals):.3f}"
                  f" avg_accuracy={_avg(kb_acc_vals):.3f}")

        total_matched += matched
        total_mismatched += mismatched
        total_skipped += skipped

    print("\n" + "=" * 90)
    print(f"TOTAL  Matched: {total_matched}  |  Mismatch: {total_mismatched}"
          f"  |  Skipped: {total_skipped}")

    print(f"\nAverage Minimality & Accuracy by testcase size:")
    print(f"  {'|TC|':>6} | {'#scenarios':>10} | {'avg_minim':>10} | {'avg_accur':>10}")
    print(f"  {'-'*6}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}")
    all_min: List[float] = []
    all_acc: List[float] = []
    for size in sorted(by_size.keys()):
        vals = by_size[size]
        mins = [v[0] for v in vals]
        accs = [v[1] for v in vals]
        all_min.extend(mins)
        all_acc.extend(accs)
        print(f"  {size:>6} | {len(vals):>10} | {_avg(mins):>10.3f} | {_avg(accs):>10.3f}")
    if all_min:
        print(f"  {'ALL':>6} | {len(all_min):>10} | {_avg(all_min):>10.3f} | {_avg(all_acc):>10.3f}")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    # TOML config mode
    if arg and arg.endswith(".toml"):
        raw = load_config(arg)
        c = raw["comparison"]
        results_dir = ROOT_PROJECT_FOLDER / c["results_dir"]
        kb_names = [kb["name"] for kb in raw["kb"]]

        if "output_dir" in c:
            out_path = ROOT_PROJECT_FOLDER / c["output_dir"] / c["output_filename"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                old_stdout = sys.stdout
                sys.stdout = TeeWriter(old_stdout, f)
                try:
                    run_comparison(results_dir, kb_names)
                finally:
                    sys.stdout = old_stdout
            print(f"\nReport saved to: {out_path}")
        else:
            run_comparison(results_dir, kb_names)
        return

    # Legacy positional arg mode
    results_dir = Path(arg) if arg else (
        ROOT_PROJECT_FOLDER / "data" / "jiis" / "results" / "1"
    )
    run_comparison(results_dir, KB_NAMES_EXTENDED)


if __name__ == "__main__":
    main()
