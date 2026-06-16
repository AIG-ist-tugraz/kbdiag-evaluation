#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Verify mismatched constraints from first-diagnosis comparison.

For each mismatched scenario (KBDiag vs HSDAG, m=1), checks whether
constraints "Only in KBDiag" appear in at least one HSDAG all-diagnosis.
This validates that KBDiag's constraints are indeed faulty (part of some
minimal diagnosis found by HSDAG).

Ranks reported reflect HSDAG's emission order (#1 = first diagnosis emitted
by HSDAG, which corresponds to its top-preference cardinality-minimal
diagnosis). A KBDiag exact match at rank #5 means HSDAG also considers that
diagnosis valid, but ranks it 5th in preference — supporting the argument
that any difference is in preference ordering, not validity.

Outputs (to console and optionally to file):
  - Per-scenario verification with rank info
  - Summary counts: exact_match, verified (constraint-level), not_found
  - Ranking summary table: for paper / response letter

Usage:
    # TOML config mode (recommended) — see apps/conf/diagnosis-verify/diagnosis_quality_verify.toml
    python -m apps.verify_diagnosis_quality apps/conf/diagnosis-verify/diagnosis_quality_verify.toml

    # Default mode (rev1 baseline, all KBs, no file output)
    python -m apps.verify_diagnosis_quality
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from apps.results_table_gen import HEADER_RE, TIMEOUT_RE, _split_into_blocks

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent

# Default KB list (used when no TOML config — backward-compat with rev1 baseline scan)
DEFAULT_KB_NAMES = ["REAL-FM-11", "DELL", "REAL-FM-4", "windows8", "CNNl", "linux"]

# Regex patterns for diagnosis content
DIAGNOSIS_RE = re.compile(r"^\tDiagnosis:\s+\[(.+)\]\s*$")
DIAGNOSIS_N_RE = re.compile(r"^\tDiagnosis \d+ \(.*\):\s+\[(.+)\]\s*$")


# ---------------------------------------------------------------------------
# Result file parsers (inlined from former compare_diagnoses.py)
# ---------------------------------------------------------------------------

def parse_diagnosis_elements(diag_content: str) -> FrozenSet[str]:
    """Parse diagnosis content string into a frozenset of constraint names.

    Splits on comma followed by '(' to handle commas inside brackets safely
    (e.g., `c1(x in [1,1]), c2(...)` won't break on the inner comma).
    """
    elements = [e.strip() for e in re.split(r",\s*(?=\()", diag_content)]
    return frozenset(elements)


def extract_first_diagnoses(filepath: Path) -> Dict[str, Optional[FrozenSet[str]]]:
    """Extract the first iteration's diagnosis per scenario from a result file.

    Returns dict mapping testcases_file -> frozenset of constraints.
    Timeout scenarios map to None.
    """
    if not filepath.exists():
        return {}
    seen: set = set()
    diagnoses: Dict[str, Optional[FrozenSet[str]]] = {}
    for block in _split_into_blocks(filepath):
        m = HEADER_RE.match(block[0])
        if not m:
            continue
        tc_file = m.group(2)
        if tc_file in seen:
            continue
        seen.add(tc_file)
        is_timeout = False
        diag: Optional[FrozenSet[str]] = None
        for line in block[1:]:
            if TIMEOUT_RE.match(line):
                is_timeout = True
                break
            dm = DIAGNOSIS_RE.match(line)
            if dm:
                diag = parse_diagnosis_elements(dm.group(1))
        diagnoses[tc_file] = None if is_timeout else diag
    return diagnoses


def extract_all_diagnoses_ordered(
    filepath: Path,
) -> Dict[str, Optional[Tuple[FrozenSet[str], ...]]]:
    """Extract ALL diagnoses preserving HSDAG emission order (task=all format).

    Returns dict mapping testcases_file -> tuple of frozensets, where the
    position in the tuple reflects HSDAG's enumeration rank (#1 = first
    emitted, typically smallest cardinality). Timeout scenarios map to None.
    """
    if not filepath.exists():
        return {}
    seen: set = set()
    result: Dict[str, Optional[Tuple[FrozenSet[str], ...]]] = {}
    for block in _split_into_blocks(filepath):
        m = HEADER_RE.match(block[0])
        if not m:
            continue
        tc_file = m.group(2)
        if tc_file in seen:
            continue
        seen.add(tc_file)
        is_timeout = False
        diags: List[FrozenSet[str]] = []
        for line in block[1:]:
            if TIMEOUT_RE.match(line):
                is_timeout = True
                break
            dm = DIAGNOSIS_N_RE.match(line) or DIAGNOSIS_RE.match(line)
            if dm:
                diags.append(parse_diagnosis_elements(dm.group(1)))
        result[tc_file] = None if is_timeout else tuple(diags)
    return result


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------

def _find_exact_rank(
    target: FrozenSet[str],
    ordered_diags: Tuple[FrozenSet[str], ...],
) -> Optional[int]:
    """Return 1-based rank of target in HSDAG's emission order, or None."""
    for i, d in enumerate(ordered_diags, 1):
        if d == target:
            return i
    return None


def _find_constraint_ranks(
    constraint: str,
    ordered_diags: Tuple[FrozenSet[str], ...],
) -> List[int]:
    """Return 1-based ranks (HSDAG emission order) containing constraint."""
    return [i for i, d in enumerate(ordered_diags, 1) if constraint in d]


# ---------------------------------------------------------------------------
# Output multiplexer (console + optional file)
# ---------------------------------------------------------------------------

class TeeWriter:
    """Mirror writes to multiple streams (e.g., stdout + file)."""
    def __init__(self, *streams) -> None:
        self.streams = streams

    def write(self, data: str) -> None:
        for s in self.streams:
            s.write(data)

    def flush(self) -> None:
        for s in self.streams:
            s.flush()


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str) -> Dict[str, Any]:
    """Parse and validate a TOML verification config.

    Required schema:
        [verification]
        dir_1   = "..."   # folder with KBDiag/HSDAG first-diag result files
        dir_all = "..."   # folder with HSDAG all-diag result files

        [[kb]]
        name = "DELL"

    Optional:
        [verification]
        output_dir      = "plans/reports"
        output_filename = "c1-cap100-verify.txt"
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
    # output_dir + output_filename are coupled: both or neither
    has_dir = "output_dir" in v
    has_filename = "output_filename" in v
    if has_dir != has_filename:
        raise ValueError(
            "output_dir and output_filename must both be set or both omitted"
        )
    return raw


# ---------------------------------------------------------------------------
# Verification main loop
# ---------------------------------------------------------------------------

def run_verification(
    dir_1: Path,
    dir_all: Path,
    kb_names: List[str],
) -> None:
    """Run verification across given KBs.

    Args:
        dir_1: folder containing task=1 result files (KBDiag + HSDAG first-diag).
        dir_all: folder containing task=all result files (HSDAG enumeration).
        kb_names: list of KB names to check.
    """
    print(f"First-diag dir: {dir_1}")
    print(f"All-diag dir:   {dir_all}")
    print("Ranks reported in HSDAG emission order (#1 = first diagnosis emitted).")
    print("=" * 80)

    total_exact_match = 0
    total_verified = 0
    total_not_found = 0
    # (kb, tc_file, |KBDiag|, |HSDAG_all|, rank_info)
    ranking_summary: List[Tuple[str, str, int, int, str]] = []

    for kb in kb_names:
        kbdiag_first = extract_first_diagnoses(
            dir_1 / f"results_kbdiag_{kb}_1.txt"
        )
        hsdag_first = extract_first_diagnoses(
            dir_1 / f"results_quickxplain_with_testcases_{kb}_1.txt"
        )
        hsdag_all = extract_all_diagnoses_ordered(
            dir_all / f"results_quickxplain_with_testcases_{kb}_all.txt"
        )

        if not kbdiag_first or not hsdag_first or not hsdag_all:
            continue

        has_mismatch = False
        all_scenarios = sorted(
            set(kbdiag_first.keys()) & set(hsdag_first.keys())
        )

        for tc_file in all_scenarios:
            kd = kbdiag_first.get(tc_file)
            hd = hsdag_first.get(tc_file)
            if kd is None or hd is None or kd == hd:
                continue

            only_kbdiag = kd - hd
            if not only_kbdiag:
                continue

            if not has_mismatch:
                print(f"\n--- {kb} ---")
                has_mismatch = True

            hsdag_all_diags = hsdag_all.get(tc_file)
            if hsdag_all_diags is None:
                print(f"  {tc_file}: HSDAG all-diags not available (timeout?)")
                continue

            n_all = len(hsdag_all_diags)
            print(
                f"  {tc_file} (|KBDiag|={len(kd)}, |HSDAG_first|={len(hd)}, "
                f"#HSDAG_all={n_all}):"
            )

            # Tier 1: exact match in HSDAG enumeration
            exact_rank = _find_exact_rank(kd, hsdag_all_diags)
            if exact_rank is not None:
                print(
                    f"    KBDiag first diag FOUND as HSDAG diagnosis "
                    f"#{exact_rank}/{n_all} (emission order)  ✓  (exact match)"
                )
                total_exact_match += 1
                ranking_summary.append(
                    (kb, tc_file, len(kd), n_all, f"exact #{exact_rank}/{n_all}")
                )
                continue

            # Tier 2: constraint-level fallback
            print(
                "    KBDiag first diag NOT found in HSDAG all-diagnoses — "
                "checking constraints:"
            )
            scenario_constraint_ranks: List[str] = []
            for constraint in sorted(only_kbdiag):
                found_in = _find_constraint_ranks(constraint, hsdag_all_diags)
                if found_in:
                    total_verified += 1
                    indices = found_in[:5]
                    suffix = (
                        f"... (+{len(found_in) - 5})"
                        if len(found_in) > 5 else ""
                    )
                    print(f"    {constraint[:70]}")
                    print(
                        f"      -> FOUND in {len(found_in)}/{n_all} "
                        f"HSDAG diagnoses at ranks {indices}{suffix}  ✓"
                    )
                    scenario_constraint_ranks.append(
                        f"{constraint[:30]}@{found_in[:3]}"
                    )
                else:
                    total_not_found += 1
                    print(f"    {constraint[:70]}")
                    print("      -> NOT found in any HSDAG diagnosis  ✗")
                    scenario_constraint_ranks.append(
                        f"{constraint[:30]}@NONE"
                    )

            ranking_summary.append((
                kb, tc_file, len(kd), n_all,
                "constraint-level: " + "; ".join(scenario_constraint_ranks),
            ))

    # =========================================================================
    # Final summary
    # =========================================================================
    print("\n" + "=" * 80)
    print(
        f"Exact match: {total_exact_match}  |  Verified: {total_verified}"
        f"  |  Not found: {total_not_found}"
    )

    if total_exact_match > 0:
        print(
            f"\n{total_exact_match} scenario(s): KBDiag first diag is an "
            f"exact HSDAG diagnosis."
        )

    if total_not_found == 0 and (total_verified > 0 or total_exact_match > 0):
        print(
            "All mismatched KBDiag constraints/diagnoses verified in HSDAG "
            "all-diagnoses."
        )
    elif total_not_found > 0:
        print(
            f"\nWARNING: {total_not_found} constraint(s) not found in any "
            f"HSDAG diagnosis!\n  (HSDAG may have max_diagnoses limit — "
            f"increase cap to find more)"
        )

    # =========================================================================
    # Ranking summary table (for paper / response letter)
    # =========================================================================
    if ranking_summary:
        print("\n" + "=" * 80)
        print("RANKING SUMMARY (for paper / response letter)")
        print("=" * 80)
        print(
            f"{'KB':<12} {'Scenario':<32} {'|KBDiag|':>9} {'#HSDAG':>7}  "
            f"Rank info"
        )
        print("-" * 80)
        for kb, tc, kd_size, n_all, rank_info in ranking_summary:
            tc_short = tc[:31]
            print(
                f"{kb:<12} {tc_short:<32} {kd_size:>9} {n_all:>7}  {rank_info}"
            )

        # Aggregate stats for exact-match ranks
        exact_ranks = []
        for kb, tc, kd_size, n_all, rank_info in ranking_summary:
            if rank_info.startswith("exact #"):
                rank_str = rank_info.split("#")[1].split("/")[0]
                exact_ranks.append(int(rank_str))

        if exact_ranks:
            avg = sum(exact_ranks) / len(exact_ranks)
            print("-" * 80)
            print(
                f"Exact-match ranks: {exact_ranks} (avg={avg:.1f}, "
                f"min={min(exact_ranks)}, max={max(exact_ranks)})"
            )
            print(
                "Interpretation: KBDiag's first diag appears in HSDAG's "
                "enumeration but"
            )
            print(
                "                NOT as #1 — confirms preference-ordering "
                "difference, not"
            )
            print("                validity difference.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Resolve config (TOML or defaults), set up output, run verification."""
    if len(sys.argv) >= 2 and sys.argv[1].endswith(".toml"):
        # TOML config mode
        cfg = load_config(sys.argv[1])
        v = cfg["verification"]
        dir_1 = ROOT_PROJECT_FOLDER / v["dir_1"]
        dir_all = ROOT_PROJECT_FOLDER / v["dir_all"]
        kb_names = [kb["name"] for kb in cfg["kb"]]
        output_dir = v.get("output_dir")
        output_filename = v.get("output_filename")
    else:
        # Default mode — rev1 baseline scan, console output only
        rev1 = (
            ROOT_PROJECT_FOLDER / "data" / "jiis"
            / "results"
        )
        dir_1 = rev1 / "1"
        dir_all = rev1 / "all"
        kb_names = DEFAULT_KB_NAMES
        output_dir = None
        output_filename = None

    # Resolve output file (if configured) and tee stdout to both console + file
    if output_dir and output_filename:
        out_path = ROOT_PROJECT_FOLDER / output_dir / output_filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            original_stdout = sys.stdout
            sys.stdout = TeeWriter(original_stdout, f)
            try:
                run_verification(dir_1, dir_all, kb_names)
            finally:
                sys.stdout = original_stdout
        print(f"\n>> Report saved to: {out_path}")
    else:
        run_verification(dir_1, dir_all, kb_names)


if __name__ == "__main__":
    main()
