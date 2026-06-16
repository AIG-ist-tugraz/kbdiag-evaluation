#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Verify whether m=2 overhead constraints are faulty.

Overhead = Δ_m2 \\ Δ_m1 (constraints in m=2 diagnosis but not in m=1).
Checks each overhead constraint against KBDiag all-diagnoses to determine
if it appears in at least one minimal diagnosis (i.e., is truly faulty).

Usage:
    # TOML config mode (recommended)
    python -m apps.verify_m2_overhead apps/conf/cognitive/verify_m2_overhead.toml

    # Legacy positional arg mode
    python -m apps.verify_m2_overhead [results_base_dir]

    # Default (no args) — uses data/jiis/results
    python -m apps.verify_m2_overhead
"""

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from apps.verify_diagnosis_quality import (
    ROOT_PROJECT_FOLDER, extract_first_diagnoses,
    extract_all_diagnoses_ordered, TeeWriter,
)
from apps.compare_kbdiag_m import KB_NAMES_EXTENDED, extract_tc_size


def _avg(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str) -> Dict[str, Any]:
    """Parse and validate a TOML verification config.

    Required schema:
        [verification]
        dir_1   = "..."   # folder with task=1 result files (m=1 + m=2)
        dir_all = "..."   # folder with task=all result files (all-diagnoses)

        [[kb]]
        name = "DELL"

    Optional:
        [verification]
        output_dir      = "data/jiis/results-cognitive"
        output_filename = "verify-m2-overhead.txt"
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(p, "rb") as f:
        raw = tomllib.load(f)

    if "verification" not in raw:
        raise ValueError("Missing required section: [verification]")
    v = raw["verification"]
    for required in ("dir_1", "dir_all"):
        if required not in v:
            raise ValueError(f"Missing required field: verification.{required}")
    if "kb" not in raw or not raw["kb"]:
        raise ValueError("Missing required entries: [[kb]] (at least one)")
    for kb in raw["kb"]:
        if "name" not in kb:
            raise ValueError("Each [[kb]] entry must have a 'name' field")
    has_dir = "output_dir" in v
    has_filename = "output_filename" in v
    if has_dir != has_filename:
        raise ValueError(
            "output_dir and output_filename must both be set or both omitted"
        )
    return raw


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def run_verification(
    dir_1: Path, dir_all: Path, kb_names: List[str],
    max_cardinality: int = 0,
) -> None:
    """Run overhead faulty verification across given KBs.

    Args:
        max_cardinality: if > 0, skip scenarios with TC size above this value.
    """
    print(f"First-diag dir: {dir_1}")
    print(f"All-diag dir:   {dir_all}")
    if max_cardinality > 0:
        print(f"Filter: TC size ≤ {max_cardinality}")
    print(f"Checking: overhead constraints (Δ_m2 \\ Δ_m1) in KBDiag all-diagnoses")
    print("=" * 80)

    total_overhead = 0
    total_faulty = 0
    total_not_faulty = 0
    total_skipped = 0
    by_size: Dict[int, List[float]] = defaultdict(list)

    for kb in kb_names:
        m1_file = dir_1 / f"results_kbdiag_{kb}_1.txt"
        m2_file = dir_1 / f"results_kbdiag_{kb}_m2_1.txt"
        all_file = dir_all / f"results_kbdiag_{kb}_all.txt"

        m1_diags = extract_first_diagnoses(m1_file)
        m2_diags = extract_first_diagnoses(m2_file)
        all_diags = extract_all_diagnoses_ordered(all_file)

        if not m1_diags or not m2_diags or not all_diags:
            continue

        has_output = False
        kb_overhead = 0
        kb_faulty = 0
        all_scenarios = sorted(set(m1_diags.keys()) & set(m2_diags.keys()))

        for tc_file in all_scenarios:
            tc_size = extract_tc_size(tc_file)
            if max_cardinality > 0 and tc_size is not None and tc_size > max_cardinality:
                continue

            d_m1 = m1_diags.get(tc_file)
            d_m2 = m2_diags.get(tc_file)

            if d_m1 is None or d_m2 is None:
                total_skipped += 1
                continue

            overhead = d_m2 - d_m1
            if not overhead:
                if tc_size is not None:
                    by_size[tc_size].append(1.0)
                continue

            if not has_output:
                print(f"\n--- {kb} ---")
                has_output = True

            kbdiag_all = all_diags.get(tc_file)
            if kbdiag_all is None:
                print(f"  {tc_file}: all-diags not available (timeout?)")
                total_skipped += 1
                continue

            faulty_count = 0
            not_faulty_count = 0

            print(f"  {tc_file} (|Δ_m1|={len(d_m1)}, |Δ_m2|={len(d_m2)}, "
                  f"overhead={len(overhead)}, #all_diags={len(kbdiag_all)}):")

            for constraint in sorted(overhead):
                found_in = sum(1 for diag in kbdiag_all if constraint in diag)

                if found_in > 0:
                    faulty_count += 1
                    total_faulty += 1
                    kb_faulty += 1
                    print(f"    {constraint[:70]}")
                    print(f"      -> faulty: in {found_in}/{len(kbdiag_all)} diagnoses  ✓")
                else:
                    not_faulty_count += 1
                    total_not_faulty += 1
                    print(f"    {constraint[:70]}")
                    print(f"      -> NOT in any diagnosis  ✗")

            total_overhead += len(overhead)
            kb_overhead += len(overhead)
            faulty_rate = faulty_count / len(overhead) if overhead else 1.0
            print(f"    Overhead faulty rate: {faulty_count}/{len(overhead)} = {faulty_rate:.1%}")

            tc_size = extract_tc_size(tc_file)
            if tc_size is not None:
                by_size[tc_size].append(faulty_rate)

        if kb_overhead > 0:
            kb_rate = kb_faulty / kb_overhead
            print(f"\n  {kb} summary: {kb_faulty}/{kb_overhead} overhead faulty = {kb_rate:.1%}")

    print("\n" + "=" * 80)
    print(f"TOTAL  Overhead: {total_overhead}  |  Faulty: {total_faulty}"
          f"  |  Not faulty: {total_not_faulty}  |  Skipped: {total_skipped}")
    if total_overhead > 0:
        print(f"Overall faulty rate: {total_faulty}/{total_overhead}"
              f" = {total_faulty/total_overhead:.1%}")

    if by_size:
        print(f"\nAverage overhead faulty rate by testcase size:")
        print(f"  {'|TC|':>6} | {'#scenarios':>10} | {'avg_faulty_rate':>16}")
        print(f"  {'-'*6}-+-{'-'*10}-+-{'-'*16}")
        all_rates: List[float] = []
        for size in sorted(by_size.keys()):
            rates = by_size[size]
            all_rates.extend(rates)
            print(f"  {size:>6} | {len(rates):>10} | {_avg(rates):>15.1%}")
        if all_rates:
            print(f"  {'ALL':>6} | {len(all_rates):>10} | {_avg(all_rates):>15.1%}")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    # TOML config mode
    if arg and arg.endswith(".toml"):
        raw = load_config(arg)
        v = raw["verification"]
        dir_1 = ROOT_PROJECT_FOLDER / v["dir_1"]
        dir_all = ROOT_PROJECT_FOLDER / v["dir_all"]
        kb_names = [kb["name"] for kb in raw["kb"]]

        max_card = v.get("max_cardinality", 0)

        if "output_dir" in v:
            out_path = ROOT_PROJECT_FOLDER / v["output_dir"] / v["output_filename"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                old_stdout = sys.stdout
                sys.stdout = TeeWriter(old_stdout, f)
                try:
                    run_verification(dir_1, dir_all, kb_names, max_card)
                finally:
                    sys.stdout = old_stdout
            print(f"\nReport saved to: {out_path}")
        else:
            run_verification(dir_1, dir_all, kb_names, max_card)
        return

    # Legacy positional arg mode
    base_dir = Path(arg) if arg else (
        ROOT_PROJECT_FOLDER / "data" / "jiis" / "results"
    )
    run_verification(base_dir / "1", base_dir / "all", KB_NAMES_EXTENDED)


if __name__ == "__main__":
    main()
