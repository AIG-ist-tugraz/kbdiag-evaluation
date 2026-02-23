#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Generate Table 3 and Table 4 from evaluation results as markdown + LaTeX.

Reads a TOML config specifying algorithms, KBs, and table settings.
Parses result files, averages across iterations, and outputs formatted tables.

Usage:
    python -m apps.results_table_gen apps/conf/table_gen.toml
"""

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AlgorithmConfig:
    key: str
    display_name: str
    lam: int = 0  # lambda parameter (0 = not applicable)


@dataclass
class KBConfig:
    name: str
    display_name: str
    num_constraints: int = 0
    total_diagnoses: int = 0
    table4_test_size: int = 25


@dataclass
class Table3Config:
    enabled: bool
    test_sizes: List[int]
    groups: List[List[str]]


@dataclass
class Table4Config:
    enabled: bool
    leading_diagnoses: List[int]


@dataclass
class TableGenConfig:
    result_path: Path
    output_path: Path
    table3: Table3Config
    table4: Table4Config
    algorithms: List[AlgorithmConfig]
    kbs: List[KBConfig]


def load_config(config_path: str) -> TableGenConfig:
    """Load and validate TOML config."""
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    general = raw["general"]
    result_path = ROOT_PROJECT_FOLDER / general["result_path"]
    output_path = ROOT_PROJECT_FOLDER / general["output_path"]

    t3 = raw["table3"]
    table3 = Table3Config(
        enabled=t3["enabled"],
        test_sizes=t3["test_sizes"],
        groups=t3["groups"],
    )

    t4 = raw["table4"]
    table4 = Table4Config(
        enabled=t4["enabled"],
        leading_diagnoses=t4["leading_diagnoses"],
    )

    algorithms = []
    for a in raw["algorithm"]:
        algorithms.append(AlgorithmConfig(
            key=a["key"],
            display_name=a["display_name"],
            lam=a.get("lambda", 0),
        ))

    kbs = []
    for k in raw["kb"]:
        kbs.append(KBConfig(
            name=k["name"],
            display_name=k["display_name"],
            num_constraints=k.get("num_constraints", 0),
            total_diagnoses=k.get("total_diagnoses", 0),
            table4_test_size=k.get("table4_test_size", 25),
        ))

    return TableGenConfig(
        result_path=result_path,
        output_path=output_path,
        table3=table3,
        table4=table4,
        algorithms=algorithms,
        kbs=kbs,
    )


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

@dataclass
class Task1Result:
    kb: str
    testcases_file: str
    cc: int
    runtime_s: float
    timeout: bool = False


@dataclass
class TaskAllResult:
    kb: str
    testcases_file: str
    diagnosis_times: List[float]  # per-diagnosis t= values (seconds)
    num_diagnoses: int
    cc: int
    runtime_s: float
    timeout: bool = False


# Regex patterns
HEADER_RE = re.compile(r"^(\S+)\s+(\S+\.testcases)\s*$")
CC_RE = re.compile(r"^\tCC:\s+(\d+)")
RUNTIME_RE = re.compile(r"^\t.+runtime:\s+([\d.]+)\s+s")
DIAG_TIME_RE = re.compile(r"^\tDiagnosis\s+\d+\s+\(.*?t=([\d.]+)s\)")
NUM_DIAG_RE = re.compile(r"^\t#Diagnoses:\s+(\d+)")
TIMEOUT_RE = re.compile(r"^\t(Diag:\s*TO|Time:.*timeout)", re.IGNORECASE)


def _split_into_blocks(filepath: Path) -> List[List[str]]:
    """Split a result file into blocks, each starting with a header line."""
    blocks: List[List[str]] = []
    current: List[str] = []

    with open(filepath) as f:
        for line in f:
            line = line.rstrip("\n")
            if HEADER_RE.match(line):
                if current:
                    blocks.append(current)
                current = [line]
            else:
                current.append(line)

    if current:
        blocks.append(current)
    return blocks


def parse_task1_file(filepath: Path) -> List[Task1Result]:
    """Parse a task=1 result file into a list of per-iteration results."""
    if not filepath.exists():
        return []

    results = []
    for block in _split_into_blocks(filepath):
        m = HEADER_RE.match(block[0])
        if not m:
            continue
        kb, tc_file = m.group(1), m.group(2)

        cc, runtime, is_timeout = 0, 0.0, False
        for line in block[1:]:
            if TIMEOUT_RE.match(line):
                is_timeout = True
                continue
            cm = CC_RE.match(line)
            if cm:
                cc = int(cm.group(1))
            rm = RUNTIME_RE.match(line)
            if rm:
                runtime = float(rm.group(1))

        results.append(Task1Result(kb=kb, testcases_file=tc_file,
                                   cc=cc, runtime_s=runtime, timeout=is_timeout))
    return results


def parse_task_all_file(filepath: Path) -> List[TaskAllResult]:
    """Parse a task=all result file into a list of per-iteration results."""
    if not filepath.exists():
        return []

    results = []
    for block in _split_into_blocks(filepath):
        m = HEADER_RE.match(block[0])
        if not m:
            continue
        kb, tc_file = m.group(1), m.group(2)

        diag_times: List[float] = []
        num_diag, cc, runtime, is_timeout = 0, 0, 0.0, False

        for line in block[1:]:
            if TIMEOUT_RE.match(line):
                is_timeout = True
                continue
            dm = DIAG_TIME_RE.match(line)
            if dm:
                diag_times.append(float(dm.group(1)))
                continue
            nm = NUM_DIAG_RE.match(line)
            if nm:
                num_diag = int(nm.group(1))
                continue
            cm = CC_RE.match(line)
            if cm:
                cc = int(cm.group(1))
                continue
            rm = RUNTIME_RE.match(line)
            if rm:
                runtime = float(rm.group(1))

        results.append(TaskAllResult(
            kb=kb, testcases_file=tc_file,
            diagnosis_times=diag_times, num_diagnoses=num_diag,
            cc=cc, runtime_s=runtime, timeout=is_timeout,
        ))
    return results


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _extract_test_size(tc_file: str) -> int:
    """Extract test size from filename like 'DELL_c25_0.testcases'."""
    m = re.search(r"_c(\d+)_", tc_file)
    return int(m.group(1)) if m else 0


def _result_file_path(config: TableGenConfig, algo: AlgorithmConfig,
                      kb_name: str, task: str) -> Path:
    """Build path to a result file."""
    suffix = "_m2" if algo.key == "kbdiag_m2" else ""
    algo_key = "kbdiag" if algo.key == "kbdiag_m2" else algo.key
    filename = f"results_{algo_key}_{kb_name}{suffix}_{task}.txt"
    return config.result_path / task / filename


TIMEOUT_SENTINEL = (float("inf"), float("inf"))

# key: (algo_key, kb_name, test_size), value: (avg_cc, avg_runtime_ms) or TIMEOUT_SENTINEL
Task1Data = Dict[Tuple[str, str, int], Tuple[float, float]]


def aggregate_task1(config: TableGenConfig) -> Task1Data:
    """Parse all task=1 files and average across iterations."""
    data: Task1Data = {}

    for algo in config.algorithms:
        for kb in config.kbs:
            filepath = _result_file_path(config, algo, kb.name, "1")
            results = parse_task1_file(filepath)
            if not results:
                continue

            # Group consecutive blocks by testcases_file (n_iter per group)
            groups: Dict[str, List[Task1Result]] = {}
            for r in results:
                groups.setdefault(r.testcases_file, []).append(r)

            for tc_file, iters in groups.items():
                size = _extract_test_size(tc_file)
                if any(r.timeout for r in iters):
                    data[(algo.key, kb.name, size)] = TIMEOUT_SENTINEL
                else:
                    avg_cc = sum(r.cc for r in iters) / len(iters)
                    avg_runtime_ms = sum(r.runtime_s for r in iters) / len(iters) * 1000
                    data[(algo.key, kb.name, size)] = (avg_cc, avg_runtime_ms)

    return data


def _is_cumulative(times: List[float]) -> bool:
    """Check if per-diagnosis times are cumulative (monotonically non-decreasing)."""
    if len(times) <= 1:
        return True
    return all(times[i] <= times[i + 1] * 1.01 for i in range(len(times) - 1))


def _time_for_n_leading(diag_times: List[float], n: int,
                        cumulative: bool) -> float:
    """Get wall-clock time (seconds) for first n diagnoses."""
    if n > len(diag_times):
        return float("nan")
    if cumulative:
        return diag_times[n - 1]
    else:
        return sum(diag_times[:n])


# key: (algo_key, kb_name, n_leading), value: avg_runtime_ms
TaskAllData = Dict[Tuple[str, str, int], float]


def aggregate_task_all(config: TableGenConfig) -> TaskAllData:
    """Parse all task=all files and compute n-leading-diagnosis times."""
    data: TaskAllData = {}
    leading_ns = config.table4.leading_diagnoses

    for algo in config.algorithms:
        for kb in config.kbs:
            filepath = _result_file_path(config, algo, kb.name, "all")
            results = parse_task_all_file(filepath)
            if not results:
                continue

            # Use per-KB test_size
            test_size = kb.table4_test_size

            # Filter to target test_size, skip timeouts
            target_results = [r for r in results
                              if _extract_test_size(r.testcases_file) == test_size
                              and not r.timeout]
            if not target_results:
                continue

            # Auto-detect cumulative vs incremental from first iteration
            cumulative = _is_cumulative(target_results[0].diagnosis_times)

            for n in leading_ns:
                times_per_iter = []
                for r in target_results:
                    t = _time_for_n_leading(r.diagnosis_times, n, cumulative)
                    if not math.isnan(t):
                        times_per_iter.append(t)

                if times_per_iter:
                    avg_ms = sum(times_per_iter) / len(times_per_iter) * 1000
                    data[(algo.key, kb.name, n)] = avg_ms

    return data


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_value(val: float, decimals: int = 2) -> str:
    """Format a numeric value: NaN -> '-', >=100 -> int, else -> *decimals* places."""
    if math.isnan(val):
        return "-"
    if decimals == 0 or val >= 100:
        return str(round(val))
    return f"{val:.{decimals}f}"


def _is_timeout(cc: float, runtime_ms: float) -> bool:
    """Check if values represent a timeout sentinel."""
    return cc == float("inf") or runtime_ms == float("inf")


def format_cell_table3(cc: float, runtime_ms: float) -> str:
    """Format as 'CC / runtime' or 'T/O' for timeouts."""
    if _is_timeout(cc, runtime_ms):
        return "T/O"
    return f"{format_value(cc, 0)} / {format_value(runtime_ms)}"


# ---------------------------------------------------------------------------
# Table 3 generators
# ---------------------------------------------------------------------------

def _algo_col_header(algo: AlgorithmConfig) -> str:
    """Short column header for an algorithm."""
    if algo.lam:
        return f"{algo.display_name} λ={algo.lam}"
    return algo.display_name


def _is_bold_algo(algo: AlgorithmConfig) -> bool:
    """MSD λ=1 gets bold formatting."""
    return algo.display_name == "MSD" and algo.lam == 1


def generate_table3_md(data: Task1Data, kb_names: List[str],
                       config: TableGenConfig, suffix: str) -> None:
    """Generate Table 3 markdown for a group of KBs."""
    kbs = [kb for kb in config.kbs if kb.name in kb_names]
    algos = config.algorithms
    lines: List[str] = []

    # Header row 1: KB grouping
    header1 = f"| |T_π|"
    for kb in kbs:
        label = kb.display_name
        if kb.num_constraints:
            label += f" (|C|={kb.num_constraints})"
        span = len(algos)
        header1 += f" | {label}" + " |" * (span - 1)
    header1 += " |"

    # Header row 2: algorithm columns
    header2 = "| |T_π|"
    for kb in kbs:
        for algo in algos:
            header2 += f" | {_algo_col_header(algo)}"
    header2 += " |"

    # Separator
    sep = "|---:" + "|---:" * (len(kbs) * len(algos)) + "|"

    lines.append(header1)
    lines.append(header2)
    lines.append(sep)

    # Data rows
    for size in config.table3.test_sizes:
        row = f"| {size}"
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, size)
                if key in data:
                    cc, rt = data[key]
                    cell = format_cell_table3(cc, rt)
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell not in ("-", "T/O"):
                    cell = f"**{cell}**"
                row += f" | {cell}"
        row += " |"
        lines.append(row)

    outfile = config.output_path / f"table3{suffix}.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table3_tex(data: Task1Data, kb_names: List[str],
                        config: TableGenConfig, suffix: str) -> None:
    """Generate Table 3 LaTeX for a group of KBs."""
    kbs = [kb for kb in config.kbs if kb.name in kb_names]
    algos = config.algorithms
    algo_cols = "r" * len(algos)
    col_spec = "r" + "|".join([algo_cols] * len(kbs))

    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append(f"\\begin{{tabular}}{{|{col_spec}|}}")
    lines.append("\\hline")

    # Header row 1: multicolumn KB grouping
    hdr1 = "\\rotatebox{90}{$|T_\\pi|$}"
    for kb in kbs:
        label = kb.display_name
        if kb.num_constraints:
            label += f" ($|C|$={kb.num_constraints})"
        hdr1 += f" & \\multicolumn{{{len(algos)}}}{{c|}}{{{label}}}"
    hdr1 += " \\\\"
    lines.append(hdr1)

    # Header row 2: algorithm columns
    hdr2 = ""
    for kb in kbs:
        for algo in algos:
            hdr2 += f" & \\rotatebox{{90}}{{{_algo_col_header(algo)}}}"
    hdr2 += " \\\\"
    lines.append(hdr2)
    lines.append("\\hline")

    # Data rows
    for size in config.table3.test_sizes:
        row = str(size)
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, size)
                if key in data:
                    cc, rt = data[key]
                    cell = format_cell_table3(cc, rt)
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell not in ("-", "T/O"):
                    cell = f"\\textbf{{{cell}}}"
                row += f" & {cell}"
        row += " \\\\"
        lines.append(row)

    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append(f"\\caption{{Table 3{suffix}: One minimal diagnosis}}")
    lines.append(f"\\label{{tab:table3{suffix}}}")
    lines.append("\\end{table}")

    outfile = config.output_path / f"table3{suffix}.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# ---------------------------------------------------------------------------
# Table 4 generators
# ---------------------------------------------------------------------------

def generate_table4_md(data: TaskAllData, config: TableGenConfig) -> None:
    """Generate Table 4 markdown."""
    kbs = config.kbs
    algos = config.algorithms
    lines: List[str] = []

    # Header row 1: KB grouping with per-KB |T_π|
    header1 = "| n"
    for kb in kbs:
        parts = [f"|T_π|={kb.table4_test_size}"]
        if kb.num_constraints:
            parts.append(f"|C|={kb.num_constraints}")
        if kb.total_diagnoses:
            parts.append(f"|Δ|={kb.total_diagnoses}")
        label = f"{kb.display_name} ({', '.join(parts)})"
        header1 += f" | {label}" + " |" * (len(algos) - 1)
    header1 += " |"

    # Header row 2: algorithm columns
    header2 = "| n"
    for kb in kbs:
        for algo in algos:
            header2 += f" | {_algo_col_header(algo)}"
    header2 += " |"

    sep = "|---:" + "|---:" * (len(kbs) * len(algos)) + "|"

    lines.append(header1)
    lines.append(header2)
    lines.append(sep)

    # Data rows
    for n in config.table4.leading_diagnoses:
        row = f"| {n}"
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, n)
                if key in data:
                    cell = format_value(data[key])
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell != "-":
                    cell = f"**{cell}**"
                row += f" | {cell}"
        row += " |"
        lines.append(row)

    outfile = config.output_path / "table4.md"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


def generate_table4_tex(data: TaskAllData, config: TableGenConfig) -> None:
    """Generate Table 4 LaTeX."""
    kbs = config.kbs
    algos = config.algorithms
    algo_cols = "r" * len(algos)
    col_spec = "r" + "|".join([algo_cols] * len(kbs))

    lines: List[str] = []
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\scriptsize")
    lines.append(f"\\begin{{tabular}}{{|{col_spec}|}}")
    lines.append("\\hline")

    # Header row 1: multicolumn KB grouping with per-KB |T_π|
    hdr1 = "\\rotatebox{90}{$n$}"
    for kb in kbs:
        # parts = [f"$|T_\\pi|$={kb.table4_test_size}"]
        # if kb.num_constraints:
        #     parts.append(f"$|C|$={kb.num_constraints}")
        # if kb.total_diagnoses:
        #     parts.append(f"$|\\Delta|$={kb.total_diagnoses}")
        label = f"{kb.display_name}"
        hdr1 += f" & \\multicolumn{{{len(algos)}}}{{c|}}{{{label}}}"
    hdr1 += " \\\\"
    lines.append(hdr1)

    # Sub header row 1 - test size, constraints, diagnoses
    sub_hdr1 = ""
    for kb in kbs:
        parts = [f"$|T_\\pi|$={kb.table4_test_size}"]
        if kb.num_constraints:
            parts.append(f"$|C|$={kb.num_constraints}")
        if kb.total_diagnoses:
            parts.append(f"$|\\Delta|$={kb.total_diagnoses}")
        label = f"({', '.join(parts)})"
        sub_hdr1 += f" & \\multicolumn{{{len(algos)}}}{{c|}}{{{label}}}"
    sub_hdr1 += " \\\\"
    lines.append(sub_hdr1)

    # Header row 2: algorithm columns
    hdr2 = ""
    for kb in kbs:
        for algo in algos:
            hdr2 += f" & \\rotatebox{{90}}{{{_algo_col_header(algo)}}}"
    hdr2 += " \\\\"
    lines.append(hdr2)
    lines.append("\\hline")

    # Data rows
    for n in config.table4.leading_diagnoses:
        row = str(n)
        for kb in kbs:
            for algo in algos:
                key = (algo.key, kb.name, n)
                if key in data:
                    cell = format_value(data[key])
                else:
                    cell = "-"
                if _is_bold_algo(algo) and cell != "-":
                    cell = f"\\textbf{{{cell}}}"
                row += f" & {cell}"
        row += " \\\\"
        lines.append(row)

    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("\\caption{Table 4: $n$ leading diagnoses}")
    lines.append("\\label{tab:table4}")
    lines.append("\\end{table}")

    outfile = config.output_path / "table4.tex"
    outfile.write_text("\n".join(lines) + "\n")
    print(f"  Written: {outfile}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m apps.results_table_gen <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    config.output_path.mkdir(parents=True, exist_ok=True)

    if config.table3.enabled:
        print("Generating Table 3...")
        data1 = aggregate_task1(config)
        for i, group in enumerate(config.table3.groups):
            s = chr(97 + i)  # 'a', 'b', ...
            generate_table3_md(data1, group, config, suffix=s)
            generate_table3_tex(data1, group, config, suffix=s)

    if config.table4.enabled:
        print("Generating Table 4...")
        data_all = aggregate_task_all(config)
        generate_table4_md(data_all, config)
        generate_table4_tex(data_all, config)

    print("Done.")


if __name__ == "__main__":
    main()
